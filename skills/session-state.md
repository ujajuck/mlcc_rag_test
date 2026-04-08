# 세션 상태 스키마 (Session State Schema)

이 파일은 세 스킬이 공유하는 세션 상태의 필드 정의와 소유권을 기술한다.
LLM은 대화 맥락에서 아래 필드를 추적하며, 값이 이미 있으면 다시 묻지 않는다.

## 상태 흐름

```
mlcc-rag-spec-selector
  └─ writes → chip_prod_id_list

mlcc-optimal-design-doe
  ├─ reads  ← chip_prod_id_list (위에서)
  ├─ writes → lot_id, targets, params, top_candidates, halt_conditions, final_design

mlcc-design-dispatch
  └─ reads  ← final_design (위에서)
```

---

## Phase 1 — RAG 스펙 선정 출력

| 필드 | 타입 | 단위 | 설명 |
|------|------|------|------|
| `chip_prod_id_list` | List[str] | — | rag-spec-selector가 생성한 인접기종 목록. find_ref_lot_candidate 입력으로 사용 |

---

## Phase 2 — DOE 시뮬레이션 상태

### lot 식별자

| 필드 | 타입 | 단위 | 설명 |
|------|------|------|------|
| `lot_id` | str | — | REF LOT 식별자. 짧은 영숫자(예: `AKB45A2`) |
| `chip_prod_id` | str | — | 대상 제품 기종 코드. 15~16자, CL로 시작 |

### targets (optimal_design 입력, scalar)

| 필드 | 타입 | 단위 |
|------|------|------|
| `target_electrode_c_avg` | float | uF |
| `target_grinding_l_avg` | float | um |
| `target_grinding_w_avg` | float | um |
| `target_grinding_t_avg` | float | um |
| `target_dc_cap` | float | uF |

### params (optimal_design 입력, list)

DOE 탐색 시: 다중 포인트 리스트. 재실행 시: `[단일값]`.

| 필드 | 타입 | 단위 |
|------|------|------|
| `active_layer` | List[int] | EA |
| `ldn_avr_value` | List[float] | — |
| `cast_dsgn_thk` | List[float] | um |
| `screen_chip_size_leng` | List[float] | um |
| `screen_mrgn_leng` | List[float] | um |
| `screen_chip_size_widh` | List[float] | um |
| `screen_mrgn_widh` | List[float] | um |
| `cover_sheet_thk` | List[float] | um |
| `total_cover_layer_num` | List[int] | EA |
| `gap_sheet_thk` | List[float] | um |

### 신뢰성 시험 조건 (reliability_simulation 입력, scalar)

사용자에게 한 번 확인받으면 세션 내 유지. 재확인 불필요.

| 필드 | 타입 | 단위 | 기본값 사용 금지 |
|------|------|------|------|
| `halt_voltage` | float | V | ⚠️ 기본값(5) 사용 금지 |
| `halt_temperature` | float | °C | ⚠️ 기본값(5) 사용 금지 |

### 시뮬레이션 결과

| 필드 | 타입 | 설명 |
|------|------|------|
| `top_candidates` | List[dict] | optimal_design 반환값. 각 항목: `rank`, `design`, `predicted`, `gap` |

---

## Phase 3 — 최종 설계값 (design-dispatch 입력)

optimal_design top_candidates 중 사용자가 확정한 후보. dispatch 단계에서 읽는다.

| 필드 | 타입 | 단위 |
|------|------|------|
| `active_layer` | int | EA |
| `cast_dsgn_thk` | float | um |
| `electrode_c_avg` | float | uF |
| `ldn_avr_value` | float | — |
| `screen_chip_size_leng` | float | um |
| `screen_chip_size_widh` | float | um |
| `screen_mrgn_leng` | float | um |
| `screen_mrgn_widh` | float | um |
| `cover_sheet_thk` | float | um |

---

## 상태 갱신 규칙

1. **이미 있는 값은 다시 묻지 않는다.** 사용자가 명시적으로 변경 요청할 때만 덮어쓴다.
2. **새 lot_id가 들어오면** targets, params, top_candidates를 초기화한다. halt_conditions는 유지한다.
3. **override 재실행 시** 변경 지시된 필드만 교체하고, 나머지 params는 직전 top_candidates 기준값을 그대로 사용한다.
4. **스킬 간 전달**: 명시적 "handoff" 없이 대화 맥락 내에서 이어진다. 값이 맥락에 있으면 그대로 사용한다.
