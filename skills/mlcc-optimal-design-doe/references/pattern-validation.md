# 패턴: LOT 검증 + 부족인자 보충

이 패턴은 모든 시뮬레이션의 시작점이다. lot_id를 검증하고, 부족인자가 있으면 사용자로부터 값을 받아 채운다.

## 흐름

### 1. lot_id 확보

사용자가 lot_id를 제공하지 않았으면 먼저 요청한다.

### 2. check_optimal_design 실행

```
check_optimal_design(lot_id="L240215-B")
```

반환 예시:
```json
{
  "충족인자": {"cast_dsgn_thk": 4.8, "active_layer": 158, "screen_mrgn_leng": 80, "screen_chip_size_leng": 1550},
  "부족인자": ["ldn_avr_value", "cover_sheet_thk", "gap_sheet_thk", "screen_mrgn_widh"],
  "ref_values": {"cast_dsgn_thk": 4.8, "active_layer": 158, ..., "ldn_avr_value": null, ...}
}
```

### 3. 결과 해석

**부족인자가 없으면**: 바로 시뮬레이션 진행 가능. 다음 패턴(최적설계 또는 신뢰성)으로 넘어간다.

**부족인자가 있으면**: 사용자에게 두 가지 선택지를 제시한다.

응답 예시:

```
reference LOT L240215-B 검증 결과:

✅ 충족인자:
- cast_dsgn_thk (Sheet T 두께): 4.8 um
- active_layer (액티브 층수): 158 EA
- screen_mrgn_leng (스크린 마진 길이): 80 um
- screen_chip_size_leng (스크린 길이): 1550 um

❌ 부족인자 (값 없음):
- ldn_avr_value (레이다운 평균)
- cover_sheet_thk (커버 두께)
- gap_sheet_thk (갭시트 두께)
- screen_mrgn_widh (스크린 마진 너비)

부족인자에 원하시는 값을 알려주시면 반영하겠습니다.
또는 다른 lot_id로 교체할 수도 있습니다.
```

### 4. 부족인자 값 반영

사용자가 값을 제공하면 `update_lot_reference`를 호출한다.

```
update_lot_reference(
  lot_id="L240215-B",
  factors={"ldn_avr_value": 3.0, "cover_sheet_thk": 28, "gap_sheet_thk": 1.2, "screen_mrgn_widh": 55}
)
```

반환에서 `remaining_부족인자`가 비어있으면 시뮬레이션 진행 가능.
아직 남아있으면 남은 인자를 다시 요청한다.

### 5. 부분 입력 허용

사용자가 일부만 제공해도 된다. 예: "ldn_avr_value 3.0, cover_sheet_thk 28만 먼저 넣어줘"
→ 나머지(gap_sheet_thk, screen_mrgn_widh)는 다음 턴에 받으면 된다.

## 충족인자 값 활용

충족인자에 반환된 값은 이후 params 기본값 제안에 활용한다.
예: `check_optimal_design`이 `cast_dsgn_thk: 4.8`을 반환했으면, params 수집 시 "cast_dsgn_thk의 ref lot 값은 4.8um입니다. 이 값 기준으로 범위를 잡을까요?" 같은 제안이 가능하다.
