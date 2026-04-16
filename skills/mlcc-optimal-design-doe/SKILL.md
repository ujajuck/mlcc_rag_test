---
name: mlcc-optimal-design-doe
description: Reference LOT 기반 MLCC 설계 시뮬레이션 skill. 최적설계(DOE), 신뢰성 시뮬레이션, 또는 둘을 조합한 복합 분석을 수행한다. 사용자가 `lot_id 기준으로 최적설계 돌려줘`, `reference lot 검증해줘`, `부족인자 값 채워줘`, `신뢰성 시뮬레이션 돌려줘`, `여러 설계값으로 신뢰성 비교해줘`, `신뢰성 좋은 것 중에 최적설계 추천해줘`, `알아서 돌려보고 제일 좋은거 찾아줘`, `타겟 맞추면서 신뢰성도 확보해줘` 같은 요청을 할 때 사용한다.
---

# MLCC 설계 시뮬레이션

Reference LOT을 기준으로 최적설계(DOE)와 신뢰성 시뮬레이션을 오케스트레이션한다. 이 skill은 계산 자체가 아니라 **검증 → 입력 수집 → tool 호출 → 결과 비교 → 재시뮬레이션** 흐름을 유연하게 진행하는 것이 역할이다.

## 핵심 개념

| 개념 | 설명 | 예시 | 용도 |
|------|------|------|------|
| **chip_prod_id** | 제품 기종 코드 | `CL32A106KOY8NNE` (15~16자, CL로 시작) | 카탈로그 검색, 인접기종 탐색 |
| **lot_id** | 제조 LOT 식별자 | `AKB45A2` (짧은 영숫자) | DOE 시뮬레이션의 기준 LOT |

- **이전 단계 (spec-selector에서 넘어올 때)**: spec-selector가 인접기종 검색으로 chip_prod_id_list를 제공한다. 이것은 lot_id가 아니므로 반드시 `find_ref_lot_candidate`로 변환해야 한다.
- **다음 단계 (dispatch로 넘어갈 때)**: 최종 설계값이 확정되면 design-dispatch 스킬로 진행할 수 있다. 전달할 값: active_layer, cast_dsgn_thk, electrode_c_avg, ldn_avr_value, screen 치수, cover_sheet_thk + chip_prod_id, lot_id.

## 세션 상태

**읽는 키** (이전 스킬에서 전달됨):
- `mlcc_design.session.chip_prod_id_list` — `find_ref_lot_candidate` 입력으로 사용

**쓰는 키** (이 스킬이 갱신):
- `mlcc_design.session.active_lot_id` — REF LOT 확정 후 기록
- `mlcc_design.session.active_chip_prod_id` — REF LOT 확정 후 기록
- `mlcc_design.targets.{lot_id}` — 사용자로부터 수집한 target 5개
- `mlcc_design.params.{lot_id}` — DOE 탐색 범위 또는 재실행 단일값
- `mlcc_design.top_candidates.{lot_id}` — optimal_design 결과
- `mlcc_design.halt_conditions` — halt_voltage, halt_temperature (세션 내 유지)
- `mlcc_design.final_design.{lot_id}` — 사용자 확정 설계값 → mlcc-design-dispatch가 읽음

**초기화 규칙**: 새 lot_id가 들어오면 targets/params/top_candidates를 초기화한다. halt_conditions는 유지한다.

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
- `references/examples-lot-validation.md`: LOT 선정/검증/부족인자 보충 예시 (Examples 1-6)
- `references/examples-lot-doe.md`: 최적설계 DOE, 재실행 예시 (Examples 1-7)
- `references/examples-reliability.md`: 신뢰성 시뮬레이션 및 자율 반복 예시 (Examples 8-13)
- `references/examples-convergence.md`: 수렴 탐색 예시 (Examples 14-16)
- `references/prompt-examples.md`: 예시 파일 인덱스

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

**`optimal_design` 핵심 입력:**
- **targets** (5개, scalar): `target_electrode_c_avg`(uF), `target_grinding_l_avg`(um), `target_grinding_w_avg`(um), `target_grinding_t_avg`(um), `target_dc_cap`(uF)
- **params** (10개, list): `active_layer`, `ldn_avr_value`, `cast_dsgn_thk`, `screen_chip_size_leng`, `screen_mrgn_leng`, `screen_chip_size_widh`, `screen_mrgn_widh`, `cover_sheet_thk`, `total_cover_layer_num`, `gap_sheet_thk`

**params 형식:**
- 초기 실행(DOE 탐색): ref lot 기준 ±범위 다중 포인트 리스트. 예: cast_dsgn_thk=5.0, ±5% 11포인트 → `[4.75, 4.80, 4.85, 4.90, 4.95, 5.00, 5.05, 5.10, 5.15, 5.20, 5.25]`
- 재실행(특정 후보 기반): 단일 값 리스트 `[value]`. 예: 3번 후보에서 cast_dsgn_thk만 5.2로 → `cast_dsgn_thk: [5.2]`

1. targets 5개 수집 (빠진 값만 한 번에 묻는다)
2. params 수집 — 위 형식에 맞게 리스트로 구성
3. `optimal_design` 호출 → top 5 제시
4. 공정검사표준 검증 후 결과 제시
5. 사용자 수정 지시 시 override 재실행

### 신뢰성 패턴

> 실행 전 `references/pattern-reliability.md`와 `references/tool-contracts.md`를 반드시 참고한다.

**`reliability_simulation` 핵심 입력:**
- 설계값은 **scalar** (list 아님) — `optimal_design`과 다르다
- `halt_voltage`: 시험 전압. **기본값을 사용하지 말고 반드시 사용자에게 한 번 확인한다.** 배수(예: 1.5Vr) 또는 절대전압(V)으로 받는다.
- `halt_temperature`: 시험 온도(°C). **마찬가지로 사용자에게 확인한다.**

1. halt_voltage, halt_temperature를 사용자에게 한 번 확인
2. 설계값 확보 (직접 입력 또는 기존 optimal_design 후보에서 가져옴)
3. `reliability_simulation` 호출 → 통과확률 반환
4. 여러 조건 비교 시 반복 호출 필요

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
- 세션 상태에 이미 기록된 값(lot_id, targets, params, top_candidates, halt 조건)은 다시 묻지 않는다.

## 실패 처리

- `fully_satisfied_versions`가 비어있으면 어떤 인자가 부족한지 보여주고, 값을 채울지 다른 lot을 쓸지 묻는다. 한 버전이라도 충족되면 바로 진행한다.
- `optimal_design` 실행 실패 시 payload를 추측 수정하지 말고, tool 오류 메시지 기준으로 부족/잘못된 필드만 바로잡아 재시도한다.
- 존재하지 않는 후보 번호 참조 시 현재 보이는 번호 범위를 다시 안내한다.
- 공정검사표준 RAG 검색 실패 시 `공정검사표준 미확인` 표시를 달고 결과를 제시한다. 표준 확인 실패가 시뮬레이션 자체를 차단하지는 않는다.
- 시뮬레이션 결과가 기대에 못 미칠 때는 파라미터 범위를 변경하거나 다른 lot으로 전환하여 재시도를 제안한다. 한 번의 실패로 종료하지 않는다.
- 수렴 탐색 Phase 3에서 3회 반복 후 미수렴: 중간 결과를 사용자에게 보고하고 타겟 완화 또는 범위 변경 협의.
- 타겟+신뢰성 상충이 명확해지면 즉시 사용자에게 trade-off를 보고하고 우선순위 협의.
