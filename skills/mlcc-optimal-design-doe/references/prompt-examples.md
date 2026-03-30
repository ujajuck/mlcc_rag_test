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

`lot_id 123456을 reference로 써서 최적설계 돌려줘.`

기대 동작:

- 먼저 `check_optimal_design` 실행
- 부족인자가 없으면 `targets.*`와 `params.*`를 수집
- `optimal_design` 실행 후 공정검사표준 검증 후 top 5 제시

### Example 2

`reference lot 123456 기준으로 용량 10uF, thickness 0.8, L 1.6, W 0.8 타겟 맞추는 설계 추천해줘.`

기대 동작:

- `lot_id` 검증
- 주어진 값은 `targets.*`에 채움
- 빠진 `params.*`만 질문

## 부족인자 보충

### Example 3

`이 lot으로 가능한지 먼저 봐줘. 안 되면 부족인자 보여줘.`

기대 동작:

- `check_optimal_design`만 먼저 실행
- `충족인자`(값 포함), `부족인자`를 분리해서 보여줌
- 부족인자가 있으면 값을 채울지 다른 lot을 쓸지 묻는다

### Example 4

`부족인자에 유전체 두께 3.2, Cover 두께 28, 유전상수 2600, Margin W 55 넣어줘.`

기대 동작:

- `update_lot_reference`로 값 반영
- `remaining_부족인자`가 비었으면 시뮬레이션 진행 가능 안내
- 남아있으면 나머지 인자 요청

### Example 5

`유전체 두께 3.2랑 Cover 두께 28만 먼저 넣어줘. 나머지는 좀 고민해볼게.`

기대 동작:

- `update_lot_reference`로 2개만 반영
- "유전상수, Margin W가 아직 비어있습니다. 준비되면 알려주세요." 안내

## 재시뮬레이션

### Example 6

`3번째 설계값에서 Sheet T만 5.2로 바꿔서 다시 시뮬레이션해줘.`

기대 동작:

- 최신 top 5의 3번 후보를 base로 사용
- `Sheet T=5.2`만 override, 나머지는 그대로
- params를 각 항목 `[단일값]` 리스트로 구성
- `optimal_design` 재호출 후 결과 제시

### Example 7

`2번 후보는 그대로 두고 thickness target만 0.75로 바꿔서 다시 보고싶어.`

기대 동작:

- `target_thickness=0.75`로 수정
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

`Cover T를 28, 30, 32로 바꿔가면서 신뢰성 비교해줘. 나머지는 3번 후보 기준.`

기대 동작:

- 3번 후보의 설계값을 base로 사용
- Cover T만 3가지로 바꿔서 `reliability_simulation` 3번 호출
- 비교 테이블 제시

## 자율 반복 / 복합 요청

### Example 11

`너가 알아서 설계값 다르게 넣으면서 신뢰성 여러번 돌려보고 제일 좋은값 도출되면 나한테 추천해줘.`

기대 동작:

1. 탐색 전략 수립 후 사용자에게 공유
   - "핵심 파라미터(Cover T, Margin L)를 축으로 5~6가지 조합을 시도하겠습니다. 진행할까요?"
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
| 후보 | Sheet T | Cover T | 전극수 | 예측용량 | 신뢰성 통과확률 |
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

`lot_id L240215-B 검증하고, 부족인자 있으면 내가 값 넣을게.`

---

**Step 1: Reference 검증**

`check_optimal_design(lot_id="L240215-B")` 실행 결과:

✅ 충족인자:
| 인자 | 값 |
|---|---|
| Sheet 두께 | 4.8 um |
| 전극 폭 | 670 um |
| 전극 수 | 158 EA |
| Margin L | 80 um |

❌ 부족인자: 유전체 두께, Cover 두께, 유전상수, Margin W

부족인자에 원하시는 값을 알려주시면 반영하겠습니다. 또는 다른 lot_id로 교체할 수도 있습니다.

---

User: `유전체 두께 3.2, Cover 두께 28, 유전상수 2600, Margin W 55`

---

**Step 2: 부족인자 반영**

`update_lot_reference(lot_id="L240215-B", factors={...})` 실행 결과:

| 인자 | 값 | 상태 |
|---|---|---|
| Sheet 두께 | 4.8 um | 기존 |
| 전극 폭 | 670 um | 기존 |
| 전극 수 | 158 EA | 기존 |
| Margin L | 80 um | 기존 |
| 유전체 두께 | 3.2 um | ✅ 반영 |
| Cover 두께 | 28 um | ✅ 반영 |
| 유전상수 | 2600 | ✅ 반영 |
| Margin W | 55 um | ✅ 반영 |

모든 인자가 채워졌습니다. 시뮬레이션을 진행할 수 있습니다. 최적설계(DOE)와 신뢰성 시뮬레이션 중 어느 것부터 하시겠습니까?

---

### Example: 자율 반복 — 신뢰성 최적 탐색

User prompt:

`top 5 전부 신뢰성 돌려보고 제일 좋은거 추천해줘.`

---

**탐색 전략**

top 5 후보 각각에 `reliability_simulation`을 실행해 통과확률을 비교하겠습니다.

**[1/5]** 후보 1 (Sheet T=5.0, Cover T=30, 전극수=162) → 통과확률: 0.8723
**[2/5]** 후보 2 (Sheet T=5.2, Cover T=28, 전극수=158) → 통과확률: 0.9134
**[3/5]** 후보 3 (Sheet T=4.8, Cover T=32, 전극수=166) → 통과확률: 0.8201
**[4/5]** 후보 4 (Sheet T=5.1, Cover T=30, 전극수=160) → 통과확률: 0.8512
**[5/5]** 후보 5 (Sheet T=5.3, Cover T=25, 전극수=155) → 통과확률: 0.7834

**종합 비교:**

| 후보 | 예측용량 | 신뢰성 통과확률 | 공정표준 |
|---|---|---|---|
| 2 | 10.05uF | **0.9134** | ✅ |
| 1 | 10.12uF | 0.8723 | ✅ |
| 4 | 9.94uF | 0.8512 | ✅ |
| 3 | 10.21uF | 0.8201 | ✅ |
| 5 | 9.88uF | 0.7834 | ⚠️ Cover T 하한 경계 |

**추천: 후보 2**
- 신뢰성 통과확률 91.3%로 가장 높음
- 용량도 target 대비 +0.05uF로 충분
- 공정검사표준 전 항목 부합

이 후보를 base로 추가 미세 조정하시겠습니까?

---
