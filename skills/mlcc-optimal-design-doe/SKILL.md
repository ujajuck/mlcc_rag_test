---
name: mlcc-optimal-design-doe
description: Reference LOT 기반 MLCC 설계 시뮬레이션 skill. 최적설계(DOE), 신뢰성 시뮬레이션, 또는 둘을 조합한 복합 분석을 수행한다. 사용자가 `lot_id 기준으로 최적설계 돌려줘`, `reference lot 검증해줘`, `부족인자 값 채워줘`, `신뢰성 시뮬레이션 돌려줘`, `여러 설계값으로 신뢰성 비교해줘`, `신뢰성 좋은 것 중에 최적설계 추천해줘`, `알아서 돌려보고 제일 좋은거 찾아줘` 같은 요청을 할 때 사용한다.
---

# MLCC 설계 시뮬레이션

Reference LOT을 기준으로 최적설계(DOE)와 신뢰성 시뮬레이션을 오케스트레이션한다. 이 skill은 계산 자체가 아니라 **검증 → 입력 수집 → tool 호출 → 결과 비교 → 재시뮬레이션** 흐름을 유연하게 진행하는 것이 역할이다.

## 핵심 개념

| 개념 | 설명 | 예시 | 용도 |
|------|------|------|------|
| **chip_prod_id** | 제품 기종 코드 | `CL32A106KOY8NNE` (15~16자, CL로 시작) | 카탈로그 검색, 인접기종 탐색 |
| **lot_id** | 제조 LOT 식별자 | `AKB45A2` (짧은 영숫자) | DOE 시뮬레이션의 기준 LOT |

## 세션 상태 읽기/쓰기

> 필드 정의와 타입/단위는 `../session-state.md`를 참고한다.

**읽는 필드** (이전 스킬에서 전달됨):
- `chip_prod_id_list` ← mlcc-rag-spec-selector 출력. `find_ref_lot_candidate` 입력으로 사용.

**쓰는 필드** (이 스킬이 갱신):
- `lot_id`, `chip_prod_id` — REF LOT 확정 후 기록
- `targets` — 사용자로부터 수집 후 기록
- `params` — DOE 탐색 범위 또는 재실행 단일값 기록
- `top_candidates` — optimal_design 결과 기록
- `halt_voltage`, `halt_temperature` — 사용자 확인 후 기록, 세션 내 유지
- `final_design` — 사용자가 후보를 확정하면 기록 → mlcc-design-dispatch가 읽음

**상태 초기화 규칙**: 새 lot_id가 들어오면 targets, params, top_candidates를 초기화한다. halt 조건은 유지한다.

**이전 단계 (spec-selector에서 넘어올 때)**: chip_prod_id_list는 lot_id가 아니므로 반드시 `find_ref_lot_candidate`로 변환해야 한다.
**다음 단계 (dispatch로 넘어갈 때)**: 사용자가 후보를 확정하면 final_design을 기록하고 mlcc-design-dispatch로 진행한다.

## 실행 원칙

- tool 호출이 실패하거나 결과가 0건이어도 즉시 포기하지 않는다. 파라미터 범위를 변경하거나, 다른 조건으로 재시도하거나, 사용자에게 대안을 제시한다.
- 사용자가 "다시 해봐", "다른 방법으로", "범위 바꿔서" 등 재시도를 요청하면 반드시 응한다. 이미 시도한 조건을 변경하여 최소 2~3회는 다른 접근을 시도한다.
- "안됩니다"로 끝내지 말고, 항상 다음에 시도할 수 있는 대안(다른 lot, 범위 변경, 조건 완화 등)을 함께 제시한다.
- **tool이 에러를 반환하면 절대 성공한 것처럼 응답하지 마라.** 에러 원인을 파악하고, 선행 단계를 수행한 뒤, 원래 tool을 반드시 재실행하라.

## 필수 실행 순서 — 절대 건너뛰지 마라

| 순서 | Tool | 선행 조건 | 출력 |
|------|------|-----------|------|
| ① | `find_ref_lot_candidate(chip_prod_id_list)` | chip_prod_id_list 있음 | **lot_id** |
| ② | `get_first_lot_detail(lot_id)` | ①에서 lot_id 확보됨 | state 로드 (세션에 lot 데이터 저장) |
| ③ | `check_optimal_design(lot_id)` | ②번 완료 | fully_satisfied_versions, 부족인자 |
| ④ | `optimal_design` 또는 `reliability_simulation` | ③번 완료 + fully_satisfied_versions 있음 | 설계 후보 또는 신뢰성 통과확률 |

**규칙:**
- ①은 lot_id가 이미 직접 주어졌으면 생략 가능
- **②③은 절대 생략 불가.** ②를 안 하면 ③이 에러, ③을 안 하면 ④가 에러난다.
- ④가 에러나면: 에러 메시지 확인 → ②③ 재실행 → ④ 재실행. **에러 결과를 성공으로 보고하지 마라.**

## Tool 입출력 계약 요약

전체 계약은 `references/tool-contracts.md`에 있다. 아래는 혼동하기 쉬운 핵심 주의사항만 요약한다.

- `get_first_lot_detail`에 **chip_prod_id를 넣으면 에러**. 반드시 lot_id를 넣는다.
- `optimal_design`의 params는 **list**, `reliability_simulation`의 params는 **scalar**. 절대 혼동하지 마라.
- `halt_voltage/halt_temperature`: **기본값(5)을 쓰지 마라.** 사용자에게 반드시 한 번 확인받아라.
- `fully_satisfied_versions`가 **한 개라도** 있으면 시뮬레이션 진행 가능. 모든 버전 충족을 기다리지 않는다.

## 보충 Reference 문서

아래 reference에 상세 예시와 추가 가이드가 있으며, 필요할 때 최우선으로 참고한다.

- `references/tool-contracts.md`: tool 입출력 상세
- `references/pattern-ref-lot-selection.md`: REF LOT 선정 필터 매핑, 대화 예시
- `references/pattern-validation.md`: LOT 검증 버전별 판정 상세
- `references/pattern-optimal.md`: 최적설계 params 리스트 생성법, rerun 규칙
- `references/pattern-reliability.md`: halt 조건 확인 절차, 설계값 경로
- `references/pattern-autonomous.md`: 자율 반복 4가지 패턴(A~D)
- `references/pattern-convergence.md`: 수렴 탐색 4-Phase 방법론
- `references/prompt-examples.md`: 한국어 질의/응답 예시

## 패턴 라우팅

사용자 요청을 분석해 아래 패턴을 하나 이상 조합한다. 패턴은 자유롭게 체이닝할 수 있다.

| 요청 유형 | 패턴 조합 |
|---|---|
| "인접기종에서 ref lot 찾아줘" / "S등급만 골라줘" | **REF LOT 선정 패턴** |
| "lot 검증해줘" / "부족인자 채워줘" | 검증 패턴 |
| "최적설계 돌려줘" / "DOE 범위 잡아서" | REF LOT 선정 → 검증 → 최적설계 패턴 |
| "신뢰성 시뮬레이션 돌려줘" | 검증 → 신뢰성 패턴 |
| "후보 3번에서 cast_dsgn_thk만 바꿔서 다시" | 최적설계 패턴 (rerun) |
| "후보 3번으로 신뢰성 돌려봐" | 신뢰성 패턴 (기존 후보 활용) |
| "여러번 돌려보고 제일 좋은거 추천해줘" | 검증 → 자율 반복 패턴 |
| "신뢰성 좋은걸로 최적설계 돌려줘" | 검증 → 신뢰성 → 최적설계 (체이닝) |
| "타겟 맞추면서 신뢰성도 확보해줘" / "둘 다 만족하는 설계 찾아줘" | 검증 → **수렴 탐색 패턴** |

각 패턴의 상세 흐름은 해당 reference 문서에 있다. 아래는 패턴별 요약과 핵심 정보이다.

### REF LOT 선정 패턴

> 실행 전 `references/pattern-ref-lot-selection.md`를 반드시 참고한다.

1. 인접기종 chip_prod_id 목록 확보
2. `find_ref_lot_candidate(chip_prod_id_list, ...)` 호출 → 11개 품질지표 기반 상위 LOT 반환
3. 사용자에게 REF LOT 브리핑 및 확인
4. 확인 후 → 검증 패턴으로 이어짐

사용자가 품질 필터를 지정하면 (예: "S등급만", "신뢰성 NG 허용") 해당 파라미터를 적용한다. 파라미터 매핑 테이블은 reference 문서에 있다.

### 검증 패턴

> 실행 전 `references/pattern-validation.md`를 반드시 참고한다.

1. `get_first_lot_detail(lot_id)` → ref lot 설계정보를 state에 로드
2. `check_optimal_design(lot_id)` → 버전별 충족/부족인자 확인
3. **`fully_satisfied_versions`가 있으면 바로 시뮬레이션 진행 가능** — 모든 버전이 충족될 때까지 기다리지 않는다
4. 나머지 버전의 부족인자는 참고 정보로 안내. 사용자가 원하면 `update_lot_reference`로 보충하여 추가 버전 활성화

### 최적설계 패턴

> 실행 전 `references/pattern-optimal.md`와 `references/tool-contracts.md`를 반드시 참고한다.

targets 5개(scalar) 수집 → params 10개(**list**) 수집 → `optimal_design` 호출 → 공정검사표준 검증 → top 5 제시 → 필요 시 override 재실행. params 리스트 생성법(범위·포인트 수)과 rerun 규칙은 `pattern-optimal.md`에 있다.

### 신뢰성 패턴

> 실행 전 `references/pattern-reliability.md`와 `references/tool-contracts.md`를 반드시 참고한다.

params는 **scalar** (`optimal_design`의 list와 다름). halt_voltage/halt_temperature는 **기본값(5) 사용 금지** — 반드시 사용자에게 먼저 확인한다. 설계값 확보 경로(직접 입력/후보 활용/ref lot 기준)와 반복 비교 호출 방법은 `pattern-reliability.md`에 있다.

### 자율 반복 패턴

> 실행 전 `references/pattern-autonomous.md`를 반드시 참고한다.

단일 목표 최적화 또는 단순 비교 요청에 사용한다. "신뢰성 좋은 설계 찾아줘", "여러 조건 비교해줘" 등. 최적설계와 신뢰성을 자유롭게 조합하며, 4가지 패턴(A~D)을 reference에서 확인한 후 적절한 조합을 사용한다.

### 수렴 탐색 패턴

> 실행 전 `references/pattern-convergence.md`를 반드시 참고한다. 4-Phase 방법론과 파라미터 조정 룰 테이블이 reference에 있다.

사용자가 **타겟 적중 + 신뢰성 통과를 동시에** 요구하면 이 패턴을 사용한다.

**4-Phase 개요:**
1. **Phase 1 — 감도 분석**: 각 파라미터가 타겟/신뢰성에 미치는 영향도 파악
2. **Phase 2 — 실현 가능 영역 탐색**: 신뢰성 통과 가능한 파라미터 범위 확인
3. **Phase 3 — 타겟 수렴**: 실현 가능 영역 내에서 타겟에 근접하도록 파라미터 조정
4. **Phase 4 — 최종 검증**: 수렴된 설계값의 타겟 적중 + 신뢰성 통과 동시 확인

## 대화 규칙

- targets는 5개이므로 빠진 값만 한 번에 묻는다.
- params는 약 10개이므로 너무 길면 두세 묶음으로 나눠 묻되, 이미 있는 값은 제외한다.
- 질문은 항상 "지금 실행을 위해 무엇이 빠졌는지" 기준으로만 한다.
- 결과를 보여줄 때는 각 후보의 번호, 핵심 설계값, 예측 결과, target과의 차이를 함께 요약한다.
- 세션 상태에 이미 기록된 값(lot_id, targets, params, top_candidates)은 다시 묻지 않는다. 사용자가 변경을 명시할 때만 해당 필드만 교체한다.

## 실패 처리

- `fully_satisfied_versions`가 비어있으면 어떤 인자가 부족한지 보여주고, 값을 채울지 다른 lot을 쓸지 묻는다. 한 버전이라도 충족되면 바로 진행한다.
- `optimal_design` 실행 실패 시 payload를 추측 수정하지 말고, tool 오류 메시지 기준으로 부족/잘못된 필드만 바로잡아 재시도한다.
- 존재하지 않는 후보 번호 참조 시 현재 보이는 번호 범위를 다시 안내한다.
- 공정검사표준 RAG 검색 실패 시 `공정검사표준 미확인` 표시를 달고 결과를 제시한다. 표준 확인 실패가 시뮬레이션 자체를 차단하지는 않는다.
- 시뮬레이션 결과가 기대에 못 미칠 때는 파라미터 범위를 변경하거나 다른 lot으로 전환하여 재시도를 제안한다. 한 번의 실패로 종료하지 않는다.
