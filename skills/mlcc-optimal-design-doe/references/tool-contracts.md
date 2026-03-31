# Tool Contracts

이 reference는 설계 시뮬레이션 skill이 의존하는 5개 tool의 계약을 설명한다.

## Contents

- check_optimal_design
- update_lot_reference
- optimal_design
- reliability_simulation
- search_rag (공정검사표준 검증용)
- 공통 해석 규칙

## check_optimal_design

목적: 주어진 `lot_id`가 시뮬레이션 기준 reference로 사용 가능한지 확인한다.

입력:

- `lot_id`: string

출력:

- `충족인자`: dict — {인자명: 현재값} 형태로 reference에 이미 존재하는 인자와 그 값
- `부족인자`: list — reference에 없어서 현재 이 lot_id로는 시뮬레이션을 진행할 수 없는 인자 이름 목록
- `ref_values`: dict — 전체 인자 현황 (충족인자는 값, 부족인자는 null)

사용 규칙:

- 새 `lot_id`가 들어오면 가장 먼저 호출한다.
- `부족인자`가 있으면 두 가지 선택지를 제시한다:
  1. 사용자가 값을 직접 제공 → `update_lot_reference`로 반영
  2. 다른 `lot_id`로 교체
- `충족인자`의 값은 이후 params 기본값 제안에 활용할 수 있다.

## update_lot_reference

목적: `check_optimal_design`에서 확인된 부족인자에 사용자 지정 값을 반영한다.

입력:

- `lot_id`: string
- `factors`: dict — {인자명: 값} 형태. 예: `{"cast_dsgn_thk": 3.2, "cover_sheet_thk": 28}`

출력:

- `updated_factors`: 이번에 반영된 인자들
- `ref_values`: 업데이트 후 전체 인자 현황 (base + override 병합)
- `remaining_부족인자`: 아직 남아있는 부족인자 목록

사용 규칙:

- `check_optimal_design` 이후에만 호출한다.
- 사용자가 부족인자 값을 제공하면 이 tool로 반영한다.
- `remaining_부족인자`가 비어야 시뮬레이션을 진행할 수 있다.
- 한 번에 모든 부족인자를 채울 필요는 없다. 여러 번 호출해도 된다.

## optimal_design

목적: reference LOT과 사용자 target, DOE 입력값으로 최적 설계 후보를 계산한다.

입력:

- `lot_id`: string
- `target_electrode_c_avg`: float — 타겟용량 (uF)
- `target_grinding_l_avg`: float — 타겟 연마L사이즈 (mm)
- `target_grinding_w_avg`: float — 타겟 연마W사이즈 (mm)
- `target_grinding_t_avg`: float — 타겟 연마T사이즈 (mm)
- `target_dc_cap`: float — 타겟DC용량 (uF)
- `active_layer`: list[int] — 액티브 층수 (EA)
- `ldn_avr_value`: list[float] — 레이다운 평균
- `cast_dsgn_thk`: list[float] — Sheet T 두께 (um)
- `screen_chip_size_leng`: list[float] — 스크린 길이 (um)
- `screen_mrgn_leng`: list[float] — 스크린 마진 길이 (um)
- `screen_chip_size_widh`: list[float] — 스크린 너비 (um)
- `screen_mrgn_widh`: list[float] — 스크린 마진 너비 (um)
- `cover_sheet_thk`: list[float] — 커버 두께 (um)
- `total_cover_layer_num`: list[int] — 상+하 커버층수 (EA)
- `gap_sheet_thk`: list[float] — 갭시트 두께 (um)

### params 값 형식

**초기 실행 (DOE 탐색)**: 각 params 필드에 ref lot 값 중심 ±범위의 다중 포인트 리스트를 채운다.

예시 — ref lot의 cast_dsgn_thk = 5.0, 사용자가 ±5% 11포인트 요청:
- `cast_dsgn_thk`: `[4.75, 4.80, 4.85, 4.90, 4.95, 5.00, 5.05, 5.10, 5.15, 5.20, 5.25]`

**재실행 (특정 후보 기반)**: 선택 후보의 설계값을 각각 단일 값 리스트 `[value]`로 구성한다.

예시 — 3번 후보에서 cast_dsgn_thk만 5.2로 변경:
- `cast_dsgn_thk`: `[5.2]`, `active_layer`: `[158]`, ... (나머지는 3번 후보 값 그대로)

출력:

- `top_candidates`: 최적 설계 후보 5개. 각 후보에 `rank`, `design`, `predicted`, `gap` 포함.

## reliability_simulation

목적: 단일 설계 포인트에 대한 신뢰성 통과확률을 계산한다.

입력:

- `lot_id`: string
- `active_layer`: int — 액티브 층수 (EA), scalar, list가 아님
- `ldn_avr_value`: float — 레이다운 평균
- `cast_dsgn_thk`: float — Sheet T 두께 (um)
- `screen_chip_size_leng`: float — 스크린 길이 (um)
- `screen_mrgn_leng`: float — 스크린 마진 길이 (um)
- `screen_chip_size_widh`: float — 스크린 너비 (um)
- `screen_mrgn_widh`: float — 스크린 마진 너비 (um)
- `cover_sheet_thk`: float — 커버 두께 (um)
- `total_cover_layer_num`: int — 상+하 커버층수 (EA)
- `gap_sheet_thk`: float — 갭시트 두께 (um)

출력:

- `design`: 입력된 설계값
- `reliability_pass_rate`: float 0.0~1.0 (신뢰성 통과확률)

사용 규칙:

- optimal_design과 달리 **params가 scalar**다. list로 넣지 않는다.
- 여러 설계 조건을 비교하려면 이 tool을 **여러 번 호출**한다.
- optimal_design의 top 5 후보 각각에 대해 신뢰성을 확인할 때 유용하다.
- lot_id 검증(check_optimal_design)이 선행되어야 한다.

## search_rag (공정검사표준 검증용)

목적: 시뮬레이션 결과의 각 설계값이 공정검사표준 범위 안에 있는지 확인한다.

입력:

- `query`: 검증하려는 설계 항목 키워드. 예: `"공정검사표준 cast_dsgn_thk 범위"`, `"검사표준 screen_mrgn_leng 상한 하한"`
- `top_k`: 기본 3~5

출력:

- 관련 공정검사표준 청크 (표준 항목명, 상한/하한, 단위, 적용 조건 등)

사용 규칙:

- `optimal_design` 또는 `reliability_simulation` 결과가 나온 직후, 결과를 사용자에게 보여주기 **전에** 검증한다.
- 범위를 벗어나면 `⚠️ 공정검사표준 초과`로 표시한다.
- 표준 정보를 못 찾으면 `❓ 공정검사표준 미확인`으로 표시하고 넘어간다.

## 공통 해석 규칙

- 실제 field 이름은 tool schema를 우선한다.
- nested schema보다 flat schema를 우선 해석한다.
- `targets.*`, `params.*`는 개념적 그룹명이다.
