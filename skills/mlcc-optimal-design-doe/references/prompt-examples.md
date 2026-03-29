# Prompt Examples

이 reference는 한국어 사용자 요청 예시와 기대 동작을 보여준다.

## Contents

- 첫 실행
- Reference 교체
- 결과 비교
- 재시뮬레이션

## 첫 실행

### Example 1

`lot_id 123456을 reference로 써서 최적설계 돌려줘.`

기대 동작:

- 먼저 `check_optimal_design` 실행
- 부족인자가 없으면 `targets.*`와 `params.*`를 수집
- `optimal_design` 실행 후 top 5 제시

### Example 2

`reference lot 123456 기준으로 용량 10uF, thickness 0.8, L 1.6, W 0.8 타겟 맞추는 설계 추천해줘.`

기대 동작:

- `lot_id` 검증
- 주어진 값은 `targets.*`에 채움
- 빠진 `params.*`만 질문

## Reference 교체

### Example 3

`이 lot으로 가능한지 먼저 봐줘. 안 되면 부족인자 보여줘.`

기대 동작:

- `check_optimal_design`만 먼저 실행
- `충족인자`, `부족인자`를 분리해서 보여줌
- 부족인자가 있으면 다른 `lot_id` 요청

## 결과 비교

### Example 4

`top 5 중에서 target에 제일 가까운 후보랑 두께 margin이 제일 좋은 후보를 비교해줘.`

기대 동작:

- 최신 top 5에서 후보 번호를 유지
- 각 후보의 핵심 설계값과 target 차이를 비교

## 재시뮬레이션

### Example 5

`3번째 설계값에서 Sheet T만 5.2로 바꿔서 다시 시뮬레이션해줘.`

기대 동작:

- 최신 top 5의 3번 후보를 base로 사용
- `Sheet T=5.2`만 override
- 나머지 값은 그대로 유지
- 새 payload로 `optimal_design` 재호출

### Example 6

`2번 후보는 그대로 두고 thickness target만 0.75로 바꿔서 다시 보고싶어.`

기대 동작:

- 최신 target 값을 base로 사용
- `target thickness=0.75`만 수정
- candidate 2의 설계값 또는 현재 payload를 기준으로 재실행

### Example 7

`3번째 후보 기준이라고 했는데 지난번 run 말고 방금 run 기준이야.`

기대 동작:

- 최신 run 기준으로 후보 번호를 다시 해석
- 문맥이 애매하면 어느 run인지 짧게 재확인

## Full Response Example

### Example: 첫 실행부터 top 5 제시까지

User prompt:

`lot_id L240301-A 기준으로 최적설계 돌려줘. 용량 10uF, chip thickness 0.85mm, chip length 1.6mm, chip width 0.8mm 타겟이야.`

Full response:

---

**Step 1: Reference 검증**

`check_optimal_design(lot_id="L240301-A")` 실행 결과:

- 충족인자: Sheet 두께, 전극 폭, 전극 수, Margin, 유전체 두께, Cover 두께, 유전상수
- 부족인자: (없음)

→ reference LOT `L240301-A`는 시뮬레이션에 사용 가능합니다.

**Step 2: Target 확인**

| Target | 값 |
|---|---|
| 용량 | 10 uF |
| Chip Thickness | 0.85 mm |
| Chip Length | 1.6 mm |
| Chip Width | 0.8 mm |

**Step 3: DOE 입력값 수집**

아직 DOE 입력값(params)이 필요합니다. 아래 항목의 절대값을 알려주세요:

- Sheet T (um)
- Electrode W (um)
- Margin L (um)
- Margin W (um)
- Cover T (um)
- 전극 수 (EA)

(사용자가 값을 제공한 후)

**Step 4: Top 5 결과**

| 순위 | Sheet T | Elec W | Margin L | Margin W | Cover T | 전극수 | 예측 용량 | 예측 Thickness | Target 대비 용량 차이 | Target 대비 두께 차이 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5.0 | 680 | 85 | 60 | 30 | 162 | 10.12 uF | 0.846 mm | +0.12 uF | -0.004 mm |
| 2 | 5.2 | 675 | 85 | 60 | 28 | 158 | 10.05 uF | 0.849 mm | +0.05 uF | -0.001 mm |
| 3 | 4.8 | 690 | 80 | 55 | 32 | 166 | 10.21 uF | 0.851 mm | +0.21 uF | +0.001 mm |
| 4 | 5.1 | 670 | 90 | 65 | 30 | 160 | 9.94 uF | 0.843 mm | -0.06 uF | -0.007 mm |
| 5 | 5.3 | 685 | 80 | 60 | 25 | 155 | 9.88 uF | 0.840 mm | -0.12 uF | -0.010 mm |

**요약:**

1. 후보 1: 용량과 두께 모두 target에 근접. 균형 잡힌 설계.
2. 후보 2: 용량 target에 가장 가까움. 두께도 margin 내.
3. 후보 3: 용량 여유가 가장 크지만 두께가 target에 거의 도달.
4. 후보 4: 두께 여유는 크지만 용량이 target 미달.
5. 후보 5: 두께 margin이 가장 크지만 용량이 가장 부족.

이 중 어느 후보를 base로 설계값을 조정하시겠습니까? 예: `2번 후보에서 Sheet T만 5.0으로 바꿔서 다시 돌려줘`

---
