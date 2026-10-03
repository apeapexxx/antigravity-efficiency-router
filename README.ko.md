# ⚡ Antigravity 효율성 라우터 (Efficiency Router)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)]()
[![Platform: Antigravity](https://img.shields.io/badge/Platform-Google%20Antigravity-4285F4.svg)]()

> **구글 안티그래비티(Antigravity)를 위한 쿼터 대비 효율 극대화 플러그인.**  
> 기계적이고 단순한 작업은 초저비용 Gemini Flash로 자동 위임하고, 귀중한 Claude Opus/Sonnet 쿼터는 진짜 깊은 사고가 필요한 고난도 문제에만 집중 투입합니다.

---

[English Documentation (README.md)](README.md)

---

## 📌 왜 필요한가요?

구글 안티그래비티는 **Claude Opus 5.5** 등 최고 수준의 모델을 제공하지만, Claude 같은 서드파티 모델은 제미나이와 달리 엄격한 5시간 롤링 윈도우 및 주간 한도가 걸려 있습니다.

기존 방식의 문제점:
* 파일 검색, 로그 확인, 단순 코드 포맷팅 같은 사소한 작업도 Claude의 비싼 쿼터를 동일하게 갉아먹습니다.
* 정작 깊은 아키텍처 설계나 디버깅이 필요할 때 쿼터가 고갈되어 작업이 멈춥니다.
* 서브에이전트가 무분별하게 프리미엄 모델로 생성되어 쿼터 소모가 가속화됩니다.

## 💡 해결책

**효율성 라우터(Efficiency Router)**는 별도 외부 라이브러리 없이 순수 파이썬 표준 라이브러리만으로 동작하는 안티그래비티 전역 플러그인입니다:

1. **0-토큰 작업 난이도 분류**: 매 턴 사용자의 요청을 0토큰/0ms 휴리스틱으로 4단계 자동 분류
   - **T0 (단순 잡담/질문)**: 1줄 답변, 도구 미사용.
   - **T1 (기계적 반복)**: 파일 탐색, 로그 요약, 웹 리서치, 보일러플레이트.
   - **T2 (표준 개발)**: 일반적인 기능 구현, 버그 수정.
   - **T3 (고난도 문제)**: 대규모 아키텍처, 동시성/보안 버그, 심층 원인 분석.
2. **5시간/7일 롤링 쿼터 추적 훅 (`PreInvocation`)**: 모델 호출 직전 로컬 장부에 토큰을 기록하고, 실시간 잔여 상태(`GREEN` / `YELLOW` / `RED`)를 에이전트에게 주입.
3. **스마트 서브에이전트 위임**: T1 작업은 무료에 가까운 `gemini_flash`로, T2 작업은 `gemini_pro`로 자동 위임하여 Claude 쿼터를 완벽 보호.
4. **완전 무인 자동 승격 (Zero-Touch Escalation)**: 평소 빠른 Gemini Flash를 메인으로 쓰다가 고난도 문제(T3)를 만나면, 사용자에게 드롭다운을 바꾸라고 귀찮게 하지 않고 **백그라운드에서 `Gemini Pro` 서브에이전트를 즉시 자동 호출**하여 해결한 뒤 완성된 결과물을 바로 제공합니다.
5. **인라인 대시보드 (Generative UI)**: 채팅창에서 `"사용량 보여줘"`라고 말하면 인터랙티브 HTML 대시보드가 즉시 렌더링됩니다.

---

## 🚀 빠른 시작 (1분 설치)

안티그래비티 전역 플러그인 디렉터리에 본 레포지토리를 클론하세요:

### macOS / Linux
```bash
git clone https://github.com/apeapexxx/antigravity-efficiency-router.git ~/.gemini/config/plugins/efficiency-router
```

### Windows (PowerShell)
```powershell
git clone https://github.com/apeapexxx/antigravity-efficiency-router.git "$HOME\.gemini\config\plugins\efficiency-router"
```

안티그래비티를 재시작하거나 새 대화를 열면 **플러그인이 자동으로 활성화**됩니다.

---

## 🖥️ 사용 방법

설치 후 별도의 설정 없이 평소처럼 대화하면 됩니다:

| 입력 예시 | 동작 |
|---|---|
| `"사용량 보여줘"` | 채팅창 안에 현재 5시간/7일 쿼터 현황, 절약 비율이 담긴 UI 대시보드 렌더링 |
| *"한도에 걸렸어"* | 실제 공급자 한도에 도달했을 때 캘리브레이션을 진행하여 임계치를 본인 계정에 정확히 맞춤 |
| 평소 코딩 | 에이전트가 백그라운드에서 단순 작업을 Flash 서브에이전트로 위임하여 쿼터 절약 |

---

## 🛠️ CLI 및 캘리브레이션 (보정)

터미널에서 직접 사용량을 조회하거나 한도를 보정할 수 있습니다:

```bash
# 현재 사용량 상태 조회
python scripts/router.py status

# 실제로 Claude 한도에 도달했을 때 즉시 실행 (기준값 계정 맞춤 보정)
python scripts/router.py calibrate claude 5h

# 신규 모델이나 별칭 매핑
python scripts/router.py alias "gemini-4-argon" gemini_pro

# 로컬 사용량 기록 초기화
python scripts/router.py reset
```

---

## 🔮 미래 신규 모델 대응 (Gemini 4.0 Argon 등)

새로운 최상위 모델이 출시되면 `router_config.json`에 정규식 패턴만 추가하면 즉시 적용됩니다:

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

## 🛡️ 안정성 및 개인정보 보호

* **절대 뻗지 않는 안전 설계 (Fail-Safe)**: 훅 실행 중 어떤 예외나 파싱 오류가 발생하더라도 빈 JSON(`{}`)을 출력하고 정상 종료(exit 0)되므로, 안티그래비티 에이전트 루프가 중단되는 일이 없습니다.
* **외부 의존성 제로 (Zero Dependencies)**: Python 3.9+ 표준 라이브러리만 사용하므로 `pip install` 과정이 전혀 필요 없습니다.
* **로컬 데이터 보장**: 모든 사용량 로그와 대화 세션 정보는 로컬 머신의 `data/` 디렉터리에만 저장되며 Git 추적에서 제외됩니다.

---

## 📄 라이선스

[MIT License](LICENSE) © 2026
