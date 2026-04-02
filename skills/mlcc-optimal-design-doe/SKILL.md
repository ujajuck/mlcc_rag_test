---
name: mlcc-optimal-design-doe
description: Reference LOT 기반 MLCC 설계 시뮬레이션 skill. 최적설계(DOE), 신뢰성 시뮬레이션, 또는 둘을 조합한 복합 분석을 수행한다. 사용자가 `lot_id 기준으로 최적설계 돌려줘`, `reference lot 검증해줘`, `부족인자 값 채워줘`, `신뢰성 시뮬레이션 돌려줘`, `여러 설계값으로 신뢰성 비교해줘`, `신뢰성 좋은 것 중에 최적설계 추천해줘`, `알아서 돌려보고 제일 좋은거 찾아줘` 같은 요청을 할 때 사용한다.
---

# MLCC 설계 시뮬레이션

Reference LOT을 기준으로 최적설계(DOE)와 신뢰성 시뮬레이션을 오케스트레이션한다. 이 skill은 계산 자체가 아니라 **검증 → 입력 수집 → tool 호출 → 결과 비교 → 재시뮬레이션** 흐름을 유연하게 진행하는 것이 역할이다.

필요할 때 아래 reference를 읽는다.

- `references/tool-contracts.md`: 6개 tool의 입출력 계약
- `references/pattern-validation.md`: LOT 검증 + 부족인자 보충 패턴
- `references/pattern-optimal.md`: 최적설계 DOE 패턴
- `references/pattern-reliability.md`: 신뢰성 시뮬레이션 패턴
- `references/pattern-autonomous.md`: 자율 반복/비교/추천 패턴 (단일 목표)
- `references/pattern-convergence.md`: 수렴 탐색 패턴 (타겟 + 신뢰성 동시 만족)
- `references/prompt-examples.md`: 한국어 사용자 질의와 응답 패턴

## 핵심 원칙

- `lot_id`가 없으면 가장 먼저 요청한다.
- 새 `lot_id`가 들어오면 반드시 `get_first_lot_detail`로 설계정보를 state에 로드한 뒤, `check_optimal_design`을 호출한다.
- `부족인자`가 있으면 사용자에게 값을 받아 `update_lot_reference`로 채울 수 있다. 무조건 다른 lot을 요구하지 않는다.
- `optimal_design`의 params는 **list** 형태다. DOE 탐색은 다중 포인트 리스트, 재실행은 단일 값 `[value]` 리스트.
- `reliability_simulation`은 **단일 설계값(scalar)**만 받는다. optimal_design과 다르다.
- 시뮬레이션 결과 제시 전에 `search_rag`로 공정검사표준을 검증한다.
- 이미 알고 있는 값은 다시 묻지 않는다.
- 사용자가 `3번 후보에서 cast_dsgn_thk만 5.2로`처럼 말하면 해당 후보를 base로 override해서 재실행한다.

## 패턴 라우팅

사용자 요청을 분석해 아래 패턴을 하나 이상 조합한다. 패턴은 자유롭게 체이닝할 수 있다.

| 요청 유형 | 패턴 조합 |
|---|---|
| "lot 검증해줘" / "부족인자 채워줘" | 검증 패턴 |
| "최적설계 돌려줘" / "DOE 범위 잡아서" | 검증 → 최적설계 패턴 |
| "신뢰성 시뮬레이션 돌려줘" | 검증 → 신뢰성 패턴 |
| "후보 3번에서 cast_dsgn_thk만 바꿔서 다시" | 최적설계 패턴 (rerun) |
| "후보 3번으로 신뢰성 돌려봐" | 신뢰성 패턴 (기존 후보 활용) |
| "여러번 돌려보고 제일 좋은거 추천해줘" | 검증 → 자율 반복 패턴 |
| "신뢰성 좋은걸로 최적설계 돌려줘" | 검증 → 신뢰성 → 최적설계 (체이닝) |
| "타겟 맞추면서 신뢰성도 확보해줘" / "둘 다 만족하는 설계 찾아줘" | 검증 → **수렴 탐색 패턴** |

각 패턴의 상세 흐름은 해당 reference 문서에 있다. 아래는 패턴별 요약이다.

### 검증 패턴 (references/pattern-validation.md)

1. `get_first_lot_detail(lot_id)` → ref lot 설계정보를 state에 로드
2. `check_optimal_design(lot_id)` → 충족/부족인자 확인
3. 부족인자가 있으면 사용자에게 값을 받아 `update_lot_reference`로 반영
4. 모든 인자가 채워지면 시뮬레이션 진행 가능

### 최적설계 패턴 (references/pattern-optimal.md)

1. targets 5개 수집 (타겟용량(uF), 타겟 연마L사이즈(um), 타겟 연마W사이즈(um), 타겟 연마T사이즈(um), 타겟DC용량(uF))
2. params 수집 — 초기 실행: ref lot 기준 ±범위 다중 포인트 리스트 / 재실행: 단일 값 리스트
3. `optimal_design` 호출 → top 5 제시
4. 공정검사표준 검증 후 결과 제시
5. 사용자 수정 지시 시 override 재실행

### 신뢰성 패턴 (references/pattern-reliability.md)

1. 신뢰성 시험 조건 확보 — `halt_voltage`(시험 전압)와 `halt_temperature`(시험 온도)를 사용자에게 한 번 확인. 전압은 스펙전압 대비 배수(예: 1.5Vr) 또는 절대전압(V)으로 받는다.
2. 설계값 확보 (직접 입력 또는 기존 optimal_design 후보에서 가져옴)
3. `reliability_simulation` 호출 → 통과확률 반환
4. 단일 설계 기준이므로 여러 조건을 비교하려면 반복 호출 필요

### 자율 반복 패턴 (references/pattern-autonomous.md)

단일 목표 최적화 또는 단순 비교 요청에 사용한다. "신뢰성 좋은 설계 찾아줘", "여러 조건 비교해줘" 등. 최적설계와 신뢰성을 자유롭게 조합할 수 있다.

### 수렴 탐색 패턴 (references/pattern-convergence.md)

사용자가 **타겟 적중 + 신뢰성 통과를 동시에** 요구하면 이 패턴을 사용한다. 4-Phase 체계(감도 분석 → 실현 가능 영역 탐색 → 타겟 수렴 → 최종 검증)로 설계값을 조정하며, 파라미터 조정 룰 테이블에 따라 전문가 수준으로 수렴해 나간다.

## 대화 규칙

- targets는 5개이므로 빠진 값만 한 번에 묻는다.
- params는 약 10개이므로 너무 길면 두세 묶음으로 나눠 묻되, 이미 있는 값은 제외한다.
- 질문은 항상 "지금 실행을 위해 무엇이 빠졌는지" 기준으로만 한다.
- 결과를 보여줄 때는 각 후보의 번호, 핵심 설계값, 예측 결과, target과의 차이를 함께 요약한다.
- 내부적으로 최신 lot_id, targets, params, top_candidates를 유지한다고 가정하고 대화를 이어간다.

## 실패 처리

- `부족인자`가 있으면 어떤 인자가 부족한지 보여주고, 값을 채울지 다른 lot을 쓸지 묻는다.
- `optimal_design` 실행 실패 시 payload를 추측 수정하지 말고, tool 오류 메시지 기준으로 부족/잘못된 필드만 바로잡는다.
- 존재하지 않는 후보 번호 참조 시 현재 보이는 번호 범위를 다시 안내한다.
- 공정검사표준 RAG 검색 실패 시 `공정검사표준 미확인` 표시를 달고 결과를 제시한다. 표준 확인 실패가 시뮬레이션 자체를 차단하지는 않는다.
