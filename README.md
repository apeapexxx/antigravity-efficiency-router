# ⚡ Antigravity Efficiency Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)]()
[![Platform: Antigravity](https://img.shields.io/badge/Platform-Google%20Antigravity-4285F4.svg)]()

> **Maximized intelligence per quota unit for Google Antigravity.**  
> Automatically protect your scarce Claude Opus/Sonnet quota by delegating mechanical tasks to Gemini Flash, keeping your premium reasoning capacity for the problems that actually need it.

---

[한국어 문서 (README.ko.md)](README.ko.md)

---

## 📌 The Problem

Google Antigravity provides access to top-tier reasoning models like **Claude Opus 5.5**, but non-Gemini models operate under strict, non-transparent rolling 5-hour and weekly quotas. 

Without intelligent routing:
* Simple mechanical tasks (searching files, reading logs, boilerplate formatting, codebase survey) drain the exact same expensive quota as complex architecture design.
* Developers hit rate limits unexpectedly in the middle of deep engineering sessions.
* Subagents inadvertently spawn under the premium model, burning quota exponentially.

## 💡 The Solution

**Antigravity Efficiency Router** is a zero-dependency, plug-and-play global plugin for Google Antigravity that:

1. **Zero-Token Task Classification**: Evaluates every user prompt with a lightweight heuristic classifier (0 tokens, 0ms latency) into 4 tiers:
   - **T0 (Trivial)**: Chit-chat, quick questions.
   - **T1 (Mechanical)**: File search, log review, formatting, research.
   - **T2 (Standard)**: Feature implementation, regular bug fixes.
   - **T3 (Hard)**: Architecture, concurrency, subtle bugs, security.
2. **Quota-Aware Lifecycle Hook**: Intercepts model calls before invocation (`PreInvocation`), records rolling 5h / 7d usage in a local ledger, and injects real-time budget status (`GREEN` / `YELLOW` / `RED`).
3. **Smart Delegation**: Automatically delegates T1 tasks to ultra-cheap `gemini_flash` subagents and T2 tasks to `gemini_pro`, shielding your Claude budget.
4. **Context-Preserving Escalation Protocol**: When you work with Gemini Flash as your default and hit a truly difficult task (T3), the router prepares a 5-bullet handoff brief and recommends switching to Claude. You switch the dropdown, type `"continue"`, and Claude immediately tackles the problem without losing any context.
5. **Generative UI Dashboard**: View your real-time usage and savings directly inside the chat interface by simply typing `"show usage"` or `"사용량 보여줘"`.

---

## 🚀 Quick Start (1-Minute Install)

Clone this repository into your global Antigravity plugins directory:

### macOS / Linux
```bash
git clone https://github.com/your-username/antigravity-efficiency-router.git ~/.gemini/config/plugins/efficiency-router
```

### Windows (PowerShell)
```powershell
git clone https://github.com/your-username/antigravity-efficiency-router.git "$HOME\.gemini\config\plugins\efficiency-router"
```

Restart Antigravity or open a new conversation. The plugin is **enabled automatically**.

---

## 🖥️ In-Chat Usage

Once installed, the router works entirely in the background. You can interact with it naturally:

| What you say | What happens |
|---|---|
| `"사용량 보여줘"` or `"show usage"` | Renders an interactive Generative UI dashboard inline in your chat. |
| *"Hit a rate limit!"* | Run calibration so thresholds match your actual account caps. |
| Normal coding | The agent silently delegates mechanical subtasks to save your quota. |

---

## 📊 In-Chat Generative UI Dashboard

Ask the agent for usage status anytime to see:
* Real-time 5-hour rolling & 7-day quota gauge per model tier.
* Hourly usage trends (last 24 hours).
* 7-day Offload Ratio (% of tasks handled outside of expensive Claude quota).
* Automated status recommendations (`GREEN` / `YELLOW` / `RED`).

---

## 🛠️ CLI & Calibration

You can also inspect or tune budgets directly from your terminal:

```bash
# Check current status
python scripts/router.py status

# Calibrate budgets immediately after hitting a real provider limit
python scripts/router.py calibrate claude 5h

# Map a new or preview model name to a budget bucket
python scripts/router.py alias "gemini-4-argon" gemini_pro

# Clear local usage ledger
python scripts/router.py reset
```

---

## 🔮 Future-Proof (Adding New Models)

When new frontier models (e.g., **Gemini 4.0 Argon**, Claude 5, etc.) are released, you can adapt the router in seconds via `router_config.json`:

```json
{
  "buckets": {
    "gemini_argon": {
      "tier": "strong",
      "patterns": ["argon", "gemini-4"],
      "budget_5h": 20000000,
      "budget_7d": 200000000
    }
  }
}
```

---

## 🛡️ Architecture & Safety

* **Fail-Safe**: If any hook fails or encounters malformed data, it prints `{}` and exits with code 0. **It will never crash or interrupt your Antigravity agent loop.**
* **Zero Dependencies**: Built strictly using the Python 3.9+ standard library (`json`, `re`, `time`, `os`, `sys`). No `pip install` required.
* **Privacy**: Usage data and conversation IDs are stored strictly on your local machine (`data/`) and excluded from Git via `.gitignore`.

---

## 📄 License

[MIT License](LICENSE) © 2026
