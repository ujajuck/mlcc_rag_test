# Prompt Examples

이 reference는 한국어 사용자 요청 예시와 기대 동작을 보여준다.

## Contents

- 첫 실행 (최적설계)
- 부족인자 보충
- 재시뮬레이션
- 신뢰성 시뮬레이션
- 자율 반복 / 복합 요청
- Full Response Example

## 첫 실행 (최적설계)

### Example 1

`lot_id AKB45A2을 reference로 써서 최적설계 돌려줘.`

기대 동작:

- 먼저 `get_first_lot_detail`로 설계정보를 state에 로드
- `check_optimal_design` 실행
- 부족인자가 없으면 `targets.*`와 `params.*`를 수집
- `optimal_design` 실행 후 공정검사표준 검증 후 top 5 제시

### Example 2

`reference lot AKB45A2 기준으로 타겟용량 10uF, 타겟 연마T 0.8, 연마L 1.6, 연마W 0.8, DC용량 10.5uF 타겟 맞추는 설계 추천해줘.`

기대 동작:

- `get_first_lot_detail`로 설계정보 로드
- `check_optimal_design`으로 `lot_id` 검증
- 주어진 값은 `targets.*`에 채움
- 빠진 `params.*`만 질문

## 부족인자 보충

### Example 3

`이 lot으로 가능한지 먼저 봐줘. 안 되면 부족인자 보여줘.`

기대 동작:

- `get_first_lot_detail`로 설계정보 로드 후 `check_optimal_design` 실행
- `충족인자`(값 포함), `부족인자`를 분리해서 보여줌
- 부족인자가 있으면 값을 채울지 다른 lot을 쓸지 묻는다

### Example 4

`부족인자에 ldn_avr_value 3.0, cover_sheet_thk 28, gap_sheet_thk 1.2, screen_mrgn_widh 55 넣어줘.`

기대 동작:

- `update_lot_reference`로 값 반영
- `remaining_부족인자`가 비었으면 시뮬레이션 진행 가능 안내
- 남아있으면 나머지 인자 요청

### Example 5

`ldn_avr_value 3.0이랑 cover_sheet_thk 28만 먼저 넣어줘. 나머지는 좀 고민해볼게.`

기대 동작:

- `update_lot_reference`로 2개만 반영
- "gap_sheet_thk, screen_mrgn_widh가 아직 비어있습니다. 준비되면 알려주세요." 안내

## 재시뮬레이션

### Example 6

`3번째 설계값에서 cast_dsgn_thk만 5.2로 바꿔서 다시 시뮬레이션해줘.`

기대 동작:

- 최신 top 5의 3번 후보를 base로 사용
- `cast_dsgn_thk=5.2`만 override, 나머지는 그대로
- params를 각 항목 `[단일값]` 리스트로 구성
- `optimal_design` 재호출 후 결과 제시

### Example 7

`2번 후보는 그대로 두고 target_grinding_t_avg만 0.75로 바꿔서 다시 보고싶어.`

기대 동작:

- `target_grinding_t_avg=0.75`로 수정
- params는 2번 후보 설계값 기반 단일값 리스트
- 재실행

## 신뢰성 시뮬레이션

### Example 8

`ref lot 기준값 그대로 신뢰성 시뮬레이션 돌려봐.`

기대 동작:

- `check_optimal_design`의 `ref_values`에서 설계값 가져옴
- `reliability_simulation` 호출 (params는 **scalar**, list가 아님)
- 통과확률 제시

### Example 9

`3번 후보로 신뢰성 돌려봐.`

기대 동작:

- 최신 optimal_design top 5의 3번 후보 `design` dict에서 설계값 추출
- `reliability_simulation` 호출
- 통과확률 제시

### Example 10

`cover_sheet_thk를 28, 30, 32로 바꿔가면서 신뢰성 비교해줘. 나머지는 3번 후보 기준.`

기대 동작:

- 3번 후보의 설계값을 base로 사용
- cover_sheet_thk만 3가지로 바꿔서 `reliability_simulation` 3번 호출
- 비교 테이블 제시

## 수렴 탐색 (타겟 + 신뢰성 동시 만족)

### Example 14

`용량 10uF, 연마T 0.85mm 맞추면서 신뢰성 80% 이상 나오는 설계 찾아줘.`

기대 동작:

1. **수렴 탐색 패턴** 적용 (pattern-convergence)
2. Phase 1: 넓은 DOE → top 5 + 신뢰성 → 감도 분석
3. Phase 2: 신뢰성 핵심 축 스윕 → 실현 가능 영역 확보
4. Phase 3: 실현 가능 영역 내 DOE → gap 기반 파라미터 조정 → 수렴
5. Phase 4: 최종 검증 + 추천

### Example 15

`타겟 맞추면서 신뢰성도 확보해줘. 알아서 찾아봐.`

기대 동작:

1. targets와 신뢰성 기준 확인 (미지정 시 기본값 제안: 신뢰성 ≥80%, gap 허용 ±5%)
2. 사용자 컨펌 후 수렴 탐색 Phase 1부터 진행
3. 각 Phase 전환 시 중간 결과 보고

### Example 16

`지금 후보에서 신뢰성이 떨어지는데, 타겟 유지하면서 개선해줘.`

기대 동작:

1. 기존 후보를 base로 Phase 3부터 시작
2. 파라미터 조정 룰 테이블에 따라 신뢰성 핵심 축(cover_sheet_thk, screen_mrgn_leng) 증가 방향으로 조정
3. 타겟 gap 확인하면서 수렴

## 자율 반복 / 복합 요청

### Example 11

`너가 알아서 설계값 다르게 넣으면서 신뢰성 여러번 돌려보고 제일 좋은값 도출되면 나한테 추천해줘.`

기대 동작:

1. 탐색 전략 수립 후 사용자에게 공유
   - "핵심 파라미터(cover_sheet_thk, screen_mrgn_leng)를 축으로 5~6가지 조합을 시도하겠습니다. 진행할까요?"
2. 사용자 OK 후 `reliability_simulation` 반복 호출
3. 중간 진행 상황 보고
4. 비교 테이블 + 최종 추천 (근거 포함)

### Example 12

`신뢰성이 좋은애들중에 최적설계 돌려보고 그중에 용량 제일 높게 나오는 설계를 골라줘.`

기대 동작:

1. 탐색 전략 공유
   - "먼저 여러 설계 조건으로 신뢰성을 확인하고, 통과확률이 높은 조건의 범위로 최적설계 DOE를 돌리겠습니다."
2. `reliability_simulation` 여러 번 → 통과확률 기준 필터
3. 통과 조건을 params 범위로 삼아 `optimal_design` 실행
4. top 5 중 용량 최대 후보 추천

### Example 13

`top 5 후보 전부 신뢰성 돌려보고 비교해줘.`

기대 동작:

- 최신 top 5 각각에 `reliability_simulation` 호출 (5번)
- 비교 테이블 제시:

```
| 후보 | cast_dsgn_thk | cover_sheet_thk | active_layer | 예측용량 | 신뢰성 통과확률 |
|---|---|---|---|---|---|
| 1 | 5.0 | 30 | 162 | 10.12uF | 0.87 |
| 2 | 5.2 | 28 | 158 | 10.05uF | 0.91 |
| 3 | 4.8 | 32 | 166 | 10.21uF | 0.82 |
| 4 | 5.1 | 30 | 160 | 9.94uF | 0.85 |
| 5 | 5.3 | 25 | 155 | 9.88uF | 0.78 |
```

## Full Response Example

### Example: 부족인자 보충 후 최적설계까지

User prompt:

`lot_id AKB45A2 검증하고, 부족인자 있으면 내가 값 넣을게.`

---

**Step 1: 설계정보 로드**

`get_first_lot_detail(lot_id="AKB45A2")` → status: success. ref lot 설계정보가 state에 저장되었습니다.

**Step 2: Reference 검증**

`check_optimal_design(lot_id="AKB45A2")` 실행 결과:

✅ 충족인자:
| 인자 | 값 |
|---|---|
| cast_dsgn_thk (Sheet T 두께) | 4.8 um |
| active_layer (액티브 층수) | 158 EA |
| screen_mrgn_leng (스크린 마진 길이) | 80 um |
| screen_chip_size_leng (스크린 길이) | 1550 um |

❌ 부족인자: ldn_avr_value, cover_sheet_thk, gap_sheet_thk, screen_mrgn_widh

부족인자에 원하시는 값을 알려주시면 반영하겠습니다. 또는 다른 lot_id로 교체할 수도 있습니다.

---

User: `ldn_avr_value 3.0, cover_sheet_thk 28, gap_sheet_thk 1.2, screen_mrgn_widh 55`

---

**Step 3: 부족인자 반영**

`update_lot_reference(lot_id="AKB45A2", factors={...})` 실행 결과:

| 인자 | 값 | 상태 |
|---|---|---|
| cast_dsgn_thk (Sheet T 두께) | 4.8 um | 기존 |
| active_layer (액티브 층수) | 158 EA | 기존 |
| screen_mrgn_leng (스크린 마진 길이) | 80 um | 기존 |
| screen_chip_size_leng (스크린 길이) | 1550 um | 기존 |
| ldn_avr_value (레이다운 평균) | 3.0 | ✅ 반영 |
| cover_sheet_thk (커버 두께) | 28 um | ✅ 반영 |
| gap_sheet_thk (갭시트 두께) | 1.2 um | ✅ 반영 |
| screen_mrgn_widh (스크린 마진 너비) | 55 um | ✅ 반영 |

모든 인자가 채워졌습니다. 시뮬레이션을 진행할 수 있습니다. 최적설계(DOE)와 신뢰성 시뮬레이션 중 어느 것부터 하시겠습니까?

---

### Example: 자율 반복 — 신뢰성 최적 탐색

User prompt:

`top 5 전부 신뢰성 돌려보고 제일 좋은거 추천해줘.`

---

**탐색 전략**

top 5 후보 각각에 `reliability_simulation`을 실행해 통과확률을 비교하겠습니다.

**[1/5]** 후보 1 (cast_dsgn_thk=5.0, cover_sheet_thk=30, active_layer=162) → 통과확률: 0.8723
**[2/5]** 후보 2 (cast_dsgn_thk=5.2, cover_sheet_thk=28, active_layer=158) → 통과확률: 0.9134
**[3/5]** 후보 3 (cast_dsgn_thk=4.8, cover_sheet_thk=32, active_layer=166) → 통과확률: 0.8201
**[4/5]** 후보 4 (cast_dsgn_thk=5.1, cover_sheet_thk=30, active_layer=160) → 통과확률: 0.8512
**[5/5]** 후보 5 (cast_dsgn_thk=5.3, cover_sheet_thk=25, active_layer=155) → 통과확률: 0.7834

**종합 비교:**

| 후보 | 예측용량 | 신뢰성 통과확률 | 공정표준 |
|---|---|---|---|
| 2 | 10.05uF | **0.9134** | ✅ |
| 1 | 10.12uF | 0.8723 | ✅ |
| 4 | 9.94uF | 0.8512 | ✅ |
| 3 | 10.21uF | 0.8201 | ✅ |
| 5 | 9.88uF | 0.7834 | ⚠️ cover_sheet_thk 하한 경계 |

**추천: 후보 2**
- 신뢰성 통과확률 91.3%로 가장 높음
- 용량도 target 대비 +0.05uF로 충분
- 공정검사표준 전 항목 부합

이 후보를 base로 추가 미세 조정하시겠습니까?

---
