#!/usr/bin/env python3
"""Efficiency Router for Google Antigravity.

Two roles:
  1. `hook`  - PreInvocation hook. Logs every model call (model, estimated tokens)
               to a local ledger and injects a one-line budget status so the agent
               can route work to cheaper models when quota gets tight.
  2. CLI     - status / calibrate / set / alias / reset for the ledger and budgets.

Token counts are ESTIMATES (transcript size / bytes_per_token + overhead).
Antigravity does not expose real quota numbers, so budgets should be calibrated
with `calibrate` the moment you actually hit a limit.

Python 3.9 compatible, stdlib only. The hook must never crash the agent loop:
any failure prints `{}` and exits 0.
"""
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "router_config.json")
DATA_DIR = os.path.join(ROOT, "data")
LOG_PATH = os.path.join(DATA_DIR, "usage.jsonl")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
LAST_PAYLOAD_PATH = os.path.join(DATA_DIR, "last_payload.json")

H5 = 5 * 3600
D7 = 7 * 86400


# --------------------------------------------------------------------------- io
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_config():
    cfg = load_json(CONFIG_PATH, None)
    if not cfg or "buckets" not in cfg:
        raise RuntimeError("router_config.json missing or invalid: " + CONFIG_PATH)
    return cfg


def read_ledger(now):
    entries = []
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if now - e.get("ts", 0) <= D7:
                    entries.append(e)
    except OSError:
        pass
    return entries


def append_ledger(entry):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def compact_ledger(entries):
    """Rewrite the ledger keeping only the last 7 days."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, LOG_PATH)


# ---------------------------------------------------------------------- logic
def classify(model, cfg):
    raw = (model or "").strip()
    aliases = cfg.get("aliases", {})
    if raw in aliases:
        return aliases[raw]
    low = raw.lower()
    for name, bucket in cfg["buckets"].items():
        for pat in bucket.get("patterns", []):
            if re.search(pat, low):
                return name
    return "unknown"


def estimate_tokens(payload, cfg):
    """Approximate input tokens of this invocation from transcript size."""
    base = int(cfg.get("base_overhead_tokens", 12000))
    tp = payload.get("transcriptPath") or ""
    candidates = []
    if tp:
        candidates.append(os.path.join(os.path.dirname(tp), "transcript_full.jsonl"))
        candidates.append(tp)
    for c in candidates:
        try:
            size = os.path.getsize(c)
        except OSError:
            continue
        est = base + int(size / float(cfg.get("bytes_per_token", 4)))
        return min(est, int(cfg.get("max_context_tokens", 1000000)))
    return base


def last_user_request(payload, tail_bytes=262144):
    """Return the most recent USER_REQUEST text, reading only the transcript tail."""
    tp = payload.get("transcriptPath") or ""
    if not tp:
        return ""
    try:
        with open(tp, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - tail_bytes))
            chunk = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    for line in reversed(chunk.splitlines()):
        if '"USER_INPUT"' not in line:
            continue
        try:
            step = json.loads(line)
        except ValueError:
            continue
        if step.get("type") != "USER_INPUT":
            continue
        text = step.get("content") or ""
        m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, re.S)
        return (m.group(1) if m else text).strip()
    return ""


_T3 = re.compile(
    r"아키텍처|설계|구조를? ?잡|architect|design|보안|security|취약|vulnerab|race cond|동시성|concurren|"
    r"deadlock|데드락|메모리 ?누수|memory leak|성능 ?최적화|optimi[sz]|마이그레이션|migrat|"
    r"원인 ?분석|root cause|trade-?off|어떤 방식이|best approach|scalab|확장성|고효율화|"
    r"전략|strategy|접근 ?방식|어떻게 하면|how should|모델 ?(?:배치|분배)",
    re.I)
_T2 = re.compile(
    r"구현|만들어|추가해|개발|implement|\badd\b|build|create|수정해|고쳐|\bfix|bug|버그|에러|error|"
    r"테스트 ?작성|feature|기능|refactor|리팩",
    re.I)
_T1 = re.compile(
    r"찾아|검색|search|find|grep|어디|where|요약|summar|번역|translat|변환|convert|정리해|목록|"
    r"\blist\b|읽어|rename|포맷|format|로그|\blogs?\b|조사|리서치|research|알아봐|비교해",
    re.I)


def classify_task(text):
    """Heuristic complexity tier T0..T3 (zero tokens). The main model may override."""
    if not text:
        return "T?"
    n = len(text)
    if _T3.search(text):
        s = 3
    elif _T2.search(text):
        s = 2
    elif _T1.search(text):
        s = 1
    else:
        s = 0 if n < 40 else 1
    if s in (1, 2) and (n > 1500 or text.count("```") >= 2):
        s += 1
    return "T%d" % s


def window_usage(entries, bucket, now):
    u = {"t5": 0, "t7": 0, "n5": 0, "n7": 0}
    for e in entries:
        if e.get("bucket") != bucket:
            continue
        age = now - e.get("ts", 0)
        if age <= D7:
            u["t7"] += e.get("tok", 0)
            u["n7"] += 1
        if age <= H5:
            u["t5"] += e.get("tok", 0)
            u["n5"] += 1
    return u


def level_for(u, bcfg, cfg):
    p5 = u["t5"] / float(max(bcfg.get("budget_5h", 1), 1))
    p7 = u["t7"] / float(max(bcfg.get("budget_7d", 1), 1))
    th = cfg.get("thresholds", {})
    worst = max(p5, p7)
    if worst >= th.get("red", 0.85):
        lvl = "RED"
    elif worst >= th.get("yellow", 0.6):
        lvl = "YELLOW"
    else:
        lvl = "GREEN"
    return lvl, p5, p7


# ----------------------------------------------------------------------- hook
def run_hook():
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    payload = json.loads(raw) if raw.strip() else {}
    cfg = load_config()
    if not cfg.get("enabled", True):
        print("{}")
        return

    now = time.time()
    model = payload.get("modelName") or ""
    bucket = classify(model, cfg)
    bcfg = cfg["buckets"].get(bucket, cfg["buckets"].get("unknown", {}))
    tier = bcfg.get("tier", "premium")
    tok = estimate_tokens(payload, cfg)

    # Debug aid: keep the latest payload shape (small fields only).
    save_json(LAST_PAYLOAD_PATH, {k: v for k, v in payload.items() if not isinstance(v, (dict, list)) or k == "workspacePaths"})

    entry = {
        "ts": round(now, 1),
        "conv": payload.get("conversationId", ""),
        "model": model,
        "bucket": bucket,
        "tok": tok,
        "hint": classify_task(last_user_request(payload)),
    }
    append_ledger(entry)

    entries = read_ledger(now)
    state = load_json(STATE_PATH, {})
    # Occasional compaction keeps the ledger small (~once per 500 calls).
    if state.get("since_compact", 0) >= 500:
        compact_ledger(entries)
        state["since_compact"] = 0
    else:
        state["since_compact"] = state.get("since_compact", 0) + 1
    save_json(STATE_PATH, state)

    u = window_usage(entries, bucket, now)
    lvl, p5, p7 = level_for(u, bcfg, cfg)

    hint = entry["hint"]
    dispatch = ""
    if tier == "cheap" and hint == "T3":
        dispatch = " | ESCALATE?"
    elif tier == "premium" and hint in ("T0", "T1"):
        dispatch = " | DOWNSHIFT-OK"
    msg = "[router] main={b}/{t} | 5h {p5:.0%} . 7d {p7:.0%} (est) | {lvl} | task~{h}{d}".format(
        b=bucket, t=tier, p5=p5, p7=p7, lvl=lvl, h=hint, d=dispatch
    )
    print(json.dumps({"injectSteps": [{"ephemeralMessage": msg}]}, ensure_ascii=False))


# ------------------------------------------------------------------------ cli
def fmt_tok(n):
    if n >= 1000000:
        return "{:.1f}M".format(n / 1e6)
    if n >= 1000:
        return "{:.0f}k".format(n / 1e3)
    return str(int(n))


def cmd_status():
    cfg = load_config()
    now = time.time()
    entries = read_ledger(now)
    print("Efficiency Router  (estimates; calibrate when you hit a real limit)")
    print("{:<13} {:<8} {:>16} {:>6} {:>17} {:>6} {:>7}".format(
        "bucket", "tier", "5h used/budget", "5h%", "7d used/budget", "7d%", "level"))
    total7 = 0
    by_bucket7 = {}
    for name, b in cfg["buckets"].items():
        u = window_usage(entries, name, now)
        by_bucket7[name] = u["t7"]
        total7 += u["t7"]
        if u["n7"] == 0 and name == "unknown":
            continue
        lvl, p5, p7 = level_for(u, b, cfg)
        print("{:<13} {:<8} {:>16} {:>6} {:>17} {:>6} {:>7}".format(
            name, b.get("tier", "?"),
            "{}/{}".format(fmt_tok(u["t5"]), fmt_tok(b.get("budget_5h", 0))), "{:.0%}".format(p5),
            "{}/{}".format(fmt_tok(u["t7"]), fmt_tok(b.get("budget_7d", 0))), "{:.0%}".format(p7),
            lvl))
    if total7:
        prem = sum(v for k, v in by_bucket7.items() if cfg["buckets"].get(k, {}).get("tier") == "premium")
        print("\nOffload ratio (7d, non-premium share of tokens): {:.0%}".format(1 - prem / float(total7)))
    unknown = sorted({e.get("model", "") for e in entries if e.get("bucket") == "unknown"})
    if unknown:
        print("Unmapped model names (map with `alias`): " + ", ".join(repr(m) for m in unknown))
    convs = len({e.get("conv") for e in entries})
    print("Calls logged (7d): {}  across {} conversations".format(len(entries), convs))


BUCKET_COLORS = {"claude": "#d97757", "gemini_pro": "#4285f4", "gemini_flash": "#34a853", "unknown": "#9aa0a6"}

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3">
<div class="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 shadow-sm space-y-3">
  <div class="flex items-center justify-between">
    <div>
      <div class="font-semibold">Efficiency Router</div>
      <div class="text-xs text-[var(--muted-foreground)]" id="gen"></div>
    </div>
    <span id="lvl" class="text-xs font-semibold px-2 py-1 rounded-full"></span>
  </div>
  <div id="buckets" class="space-y-2"></div>
  <div>
    <div class="text-xs text-[var(--muted-foreground)] mb-1">최근 24시간 (시간별 추정 토큰)</div>
    <div id="chart" class="flex items-end gap-[2px] h-16"></div>
    <div id="legend" class="flex gap-3 mt-1 text-xs text-[var(--muted-foreground)]"></div>
  </div>
  <div class="grid grid-cols-3 gap-2 text-center">
    <div class="rounded-lg border border-[var(--border)] p-2"><div class="text-lg font-semibold" id="off"></div><div class="text-xs text-[var(--muted-foreground)]">Claude 외 처리 비율 (7일)</div></div>
    <div class="rounded-lg border border-[var(--border)] p-2"><div class="text-lg font-semibold" id="calls"></div><div class="text-xs text-[var(--muted-foreground)]">호출 수 (7일)</div></div>
    <div class="rounded-lg border border-[var(--border)] p-2"><div id="mix" class="flex h-3 rounded overflow-hidden mt-1"></div><div class="text-xs text-[var(--muted-foreground)] mt-2" id="mixl"></div></div>
  </div>
  <div id="rec" class="text-sm rounded-lg p-2 border border-[var(--border)]"></div>
</div>
<script>
const D = __DATA__;
const LV = {GREEN:["#34a853","여유"],YELLOW:["#f9ab00","절약 모드"],RED:["#ea4335","한도 임박"]};
const fmt = n => n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?Math.round(n/1e3)+"k":String(n);
const pct = p => Math.round(p*100)+"%";
document.getElementById("gen").textContent = D.generated + " 기준 · 추정치";
const lv = LV[D.level]; const b = document.getElementById("lvl");
b.textContent = D.level+" · "+lv[1]; b.style.background = lv[0]+"26"; b.style.color = lv[0];
const bar = (p,c) => `<div class="h-1.5 rounded bg-[var(--border)] overflow-hidden"><div class="h-full rounded" style="width:${Math.min(100,p*100)}%;background:${c}"></div></div>`;
document.getElementById("buckets").innerHTML = D.buckets.map(x => `
  <div class="grid grid-cols-[110px_1fr_1fr] gap-3 items-center text-xs">
    <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:${x.color}"></span>${x.name}</div>
    <div><div class="flex justify-between text-[var(--muted-foreground)]"><span>5h ${fmt(x.t5)}/${fmt(x.b5)}</span><span>${pct(x.p5)}</span></div>${bar(x.p5,x.color)}</div>
    <div><div class="flex justify-between text-[var(--muted-foreground)]"><span>7d ${fmt(x.t7)}/${fmt(x.b7)}</span><span>${pct(x.p7)}</span></div>${bar(x.p7,x.color)}</div>
  </div>`).join("");
const mx = Math.max(1, ...D.hourly.map(h => D.order.reduce((s,k)=>s+(h[k]||0),0)));
document.getElementById("chart").innerHTML = D.hourly.map(h => {
  const segs = D.order.filter(k=>h[k]).map(k=>`<div style="height:${h[k]/mx*64}px;background:${D.colors[k]}"></div>`).join("");
  return `<div class="flex-1 flex flex-col-reverse rounded-sm overflow-hidden bg-[var(--border)]/30" title="${h.label}">${segs}</div>`;
}).join("");
document.getElementById("legend").innerHTML = D.order.map(k=>`<span><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:${D.colors[k]}"></span>${k}</span>`).join("");
document.getElementById("off").textContent = D.offload===null?"-":pct(D.offload);
document.getElementById("calls").textContent = D.calls;
const MC = {T0:"#9aa0a6",T1:"#34a853",T2:"#4285f4",T3:"#d97757"};
const tot = Object.values(D.mix).reduce((a,c)=>a+c,0)||1;
document.getElementById("mix").innerHTML = ["T0","T1","T2","T3"].map(t=>`<div style="width:${(D.mix[t]||0)/tot*100}%;background:${MC[t]}"></div>`).join("");
document.getElementById("mixl").textContent = "작업 난이도 " + ["T0","T1","T2","T3"].map(t=>t+":"+(D.mix[t]||0)).join(" ");
document.getElementById("rec").textContent = D.rec;
</script>
</body></html>
"""


def build_dashboard_data(cfg, now):
    entries = read_ledger(now)
    order = [k for k in cfg["buckets"] if k != "unknown"]
    if any(e.get("bucket") == "unknown" for e in entries):
        order.append("unknown")
    buckets, worst = [], "GREEN"
    rank = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    premium_level = "GREEN"
    for name in order:
        b = cfg["buckets"][name]
        u = window_usage(entries, name, now)
        lvl, p5, p7 = level_for(u, b, cfg)
        if rank[lvl] > rank[worst]:
            worst = lvl
        if b.get("tier") == "premium" and rank[lvl] > rank[premium_level]:
            premium_level = lvl
        buckets.append({"name": name, "t5": u["t5"], "b5": b.get("budget_5h", 0), "p5": round(p5, 4),
                        "t7": u["t7"], "b7": b.get("budget_7d", 0), "p7": round(p7, 4),
                        "level": lvl, "color": BUCKET_COLORS.get(name, "#9aa0a6")})
    hourly = []
    start = int(now // 3600) * 3600 - 23 * 3600
    for i in range(24):
        h0 = start + i * 3600
        row = {"label": time.strftime("%m-%d %H시", time.localtime(h0))}
        for e in entries:
            if h0 <= e.get("ts", 0) < h0 + 3600:
                row[e.get("bucket", "unknown")] = row.get(e.get("bucket", "unknown"), 0) + e.get("tok", 0)
        hourly.append(row)
    total7 = sum(x["t7"] for x in buckets)
    prem7 = sum(x["t7"] for x in buckets if cfg["buckets"][x["name"]].get("tier") == "premium")
    mix = {}
    for e in entries:
        h = e.get("hint")
        if h in ("T0", "T1", "T2", "T3"):
            mix[h] = mix.get(h, 0) + 1
    if premium_level == "RED":
        rec = "🔴 Claude 한도 임박 — 모델 드롭다운에서 Gemini로 전환하세요. Claude는 최종 검토에만 쓰세요."
    elif premium_level == "YELLOW":
        rec = "🟡 절약 모드 — 단순·표준 작업은 Flash/Pro 서브에이전트로 자동 위임 중입니다."
    else:
        rec = "🟢 여유 있음 — 평소대로 쓰되 단순 작업은 Flash로 위임됩니다."
    return {"generated": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), "level": worst,
            "buckets": buckets, "hourly": hourly, "order": order, "colors": BUCKET_COLORS,
            "offload": (1 - prem7 / float(total7)) if total7 else None,
            "calls": len(entries), "mix": mix, "rec": rec}


def cmd_dashboard(args):
    cfg = load_config()
    out = args[0] if args else os.path.join(DATA_DIR, "dashboard.html")
    data = build_dashboard_data(cfg, time.time())
    html = DASHBOARD_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(os.path.abspath(out))


def cmd_calibrate(args):
    """Call right after you hit a real limit: sets budget = current usage."""
    cfg = load_config()
    if not args:
        sys.exit("usage: calibrate <bucket> [5h|7d]")
    bucket = args[0]
    window = args[1] if len(args) > 1 else "5h"
    if bucket not in cfg["buckets"]:
        sys.exit("unknown bucket: " + bucket)
    u = window_usage(read_ledger(time.time()), bucket, time.time())
    used = u["t5"] if window == "5h" else u["t7"]
    if used <= 0:
        sys.exit("no usage logged for {} in {} window; nothing to calibrate".format(bucket, window))
    key = "budget_" + window
    old = cfg["buckets"][bucket].get(key)
    cfg["buckets"][bucket][key] = int(used)
    # Keep the other window proportionate if it was never calibrated.
    if window == "5h" and not cfg["buckets"][bucket].get("calibrated_7d"):
        cfg["buckets"][bucket]["budget_7d"] = int(used * 10)
    cfg["buckets"][bucket]["calibrated_" + window] = time.strftime("%Y-%m-%d %H:%M")
    save_json(CONFIG_PATH, cfg)
    print("{} {}: {} -> {}".format(bucket, key, fmt_tok(old or 0), fmt_tok(used)))


def cmd_set(args):
    if len(args) != 3 or args[1] not in ("5h", "7d"):
        sys.exit("usage: set <bucket> <5h|7d> <tokens>")
    cfg = load_config()
    if args[0] not in cfg["buckets"]:
        sys.exit("unknown bucket: " + args[0])
    cfg["buckets"][args[0]]["budget_" + args[1]] = int(float(args[2]))
    save_json(CONFIG_PATH, cfg)
    print("ok")


def cmd_alias(args):
    if len(args) != 2:
        sys.exit("usage: alias <raw-model-name> <bucket>")
    cfg = load_config()
    if args[1] not in cfg["buckets"]:
        sys.exit("unknown bucket: " + args[1])
    cfg.setdefault("aliases", {})[args[0]] = args[1]
    save_json(CONFIG_PATH, cfg)
    # Re-bucket existing ledger entries for that model.
    entries = read_ledger(time.time())
    for e in entries:
        if e.get("model") == args[0]:
            e["bucket"] = args[1]
    compact_ledger(entries)
    print("ok")


def cmd_reset():
    for p in (LOG_PATH, STATE_PATH):
        if os.path.exists(p):
            os.remove(p)
    print("ledger cleared")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "status"
    if cmd == "hook":
        try:
            run_hook()
        except Exception as exc:  # never break the agent loop
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(os.path.join(DATA_DIR, "hook_errors.log"), "a", encoding="utf-8") as f:
                    f.write("{} {!r}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), exc))
            except Exception:
                pass
            print("{}")
        return
    if cmd == "status":
        cmd_status()
    elif cmd == "dashboard":
        cmd_dashboard(argv[1:])
    elif cmd == "calibrate":
        cmd_calibrate(argv[1:])
    elif cmd == "set":
        cmd_set(argv[1:])
    elif cmd == "alias":
        cmd_alias(argv[1:])
    elif cmd == "reset":
        cmd_reset()
    else:
        sys.exit("commands: status | calibrate <bucket> [5h|7d] | set <bucket> <5h|7d> <tokens> | alias <model> <bucket> | reset")


if __name__ == "__main__":
    main()
