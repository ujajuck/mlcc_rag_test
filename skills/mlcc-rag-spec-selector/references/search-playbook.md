# Search Playbook

Use this reference when driving `search_rag` and composing the final answer.

## Contents

- Search Sequence
- Ranking Rules
- Response Format
- Example Handling Pattern
- Active Lineup Lookup Step
- Korean Query Expansions
- Guardrail Phrases

## Search Sequence

### 1. Resolve code tables first

Target:

- `part_numbering`

Goal:

- map 온도특성 코드, voltage, capacitance, tolerance, size, and thickness constraints into code candidates

Query patterns:

- `A X5R 온도특성 코드`
- `온도특성 A X5R`
- `온도특성 A X5R`
- `capacitance code 4.7uF 475`
- `기준용량 4.7uF 475`
- `R 4.0Vdc rated voltage code`
- `정격전압 4V code R`
- `M tolerance code +/-20%`
- `M편차 +/-20%`
- `size code 0201 0603`
- `L 690um W 390um 0201 0603`
- `0201 0603 thickness code 0.30`
- `T 550um thickness code`

### 2. Resolve family and reliability

Target:

- `product_family`
- `reliability_level`

Goal:

- choose Standard vs High Level I vs High Level II
- decide whether a specialty family is required

Query patterns:

- `standard MLCC wide lineup`
- `high level I industrial humidity reliability`
- `high level II outdoor 85 85 1000h`
- `산업용 high level II 85C 85RH 1000h`
- `low ESL high speed IC`
- `low acoustic noise piezo PMIC`
- `저소음 PMIC DC-DC`

### 3. Retrieve nearby example parts

Target:

- `new_product`

Goal:

- find the nearest catalog anchor by size, temperature characteristic, voltage, tolerance, family, and nominal capacitance

Query patterns:

- `0201 0603 4.7uF X5R 4.0V +/-20`
- `0201 0603 4.7uF class II`
- `0201 0603 4.7uF X5R 4V M편차`
- `0603 1608 47uF X5R 6.3V`
- `1206 3216 220uF X5R 6.3V`

### 4. Check active lineup when ambiguity remains

Target:

- active-lineup DB lookup tool with input parameter `chip_prod_id`

Goal:

- determine whether the partial or full code pattern currently exists in `mdh_continous_view_3`
- surface current `chip_prod_id` hits before forcing a final selection

Pattern examples:

- `chip_prod_id = CL32_106_O____`
- `chip_prod_id = %CL32_106_O____%`
- `chip_prod_id = CL03A515MR3____`

Handling rules:

- if multiple hits are returned, list them and ask one targeted follow-up question
- if one hit is returned, continue validation against remaining catalog constraints
- if zero hits are returned, keep the catalog skeletons and ask which unresolved field may move

### 5. Retrieve validation-only characteristics when required

Target:

- `caution_characteristics`

Goal:

- determine which requested behaviors can only be left as validation items

Query patterns:

- `DC bias characteristics X5R sample`
- `AC voltage characteristics class II`
- `effective capacitance high frequency low field`
- `impedance characteristic SRF ESR ESL`
- `1V DC bias 고주파 유효용량`

## Ranking Rules

Rank candidates in this order:

1. satisfy all hard constraints
2. have an exact catalog example part
3. preserve dimension margin inside the stated limits
4. stay closest to the requested nominal capacitance
5. match the intended application or family
6. reduce validation risk for bias and frequency behavior

Always state rejection reasons:

- `rejected: voltage mismatch`
- `rejected: L dimension exceeds max`
- `rejected: family mismatch`
- `rejected: no catalog evidence for exact option`

## Response Format

Emit sections in this order:

1. `constraints summary`
2. `derived code mapping`
3. `exact catalog matches`
4. `closest catalog anchors`
5. `recommended candidate skeletons`
6. `active lineup hits from DB` when lookup was run
7. `needs datasheet or measured validation`

For each anchor, say:

- which constraints it matches
- which constraints it misses
- whether it is evidence of feasibility or an exact match

For each candidate skeleton, say:

- why it is electrically plausible from the catalog
- why it is not yet a final orderable P/N
- what must be checked next

For each DB lookup step, say:

- the `chip_prod_id` pattern used
- whether the result count was zero, one, or many
- whether the hit list proves current existence only or also resolves ambiguity
- what the next follow-up question is, if any

## Example Handling Pattern

When the user requests:

`A temperature characteristic, 4V rated voltage, L <= 690 um, W <= 390 um, T <= 550 um, nominal 4.8 uF, M tolerance, minimum 3.45 uF at 1V DC in high-frequency low-field condition`

Respond in this pattern:

- map `A -> X5R`, `R -> 4.0Vdc`, `M -> +/-20%`
- size-filter `03 (0201 / 0603)` before looking at examples
- derive nearest standard nominal candidates `475` and `515`
- search example parts near `0201 / 0603`, Class II, `4.7 uF`
- keep the `>= 3.45 uF at 1V DC and high frequency` request in validation-only status unless a retrieved chunk proves it for the target part
- prefer the higher standard nominal only when the catalog evidence supports that it is the safer preselection

## Active Lineup Lookup Step

When catalog reasoning gives you a partial but useful code family, do not stop at the skeleton. Convert it into a DB pattern and continue interactively.

Example:

- catalog reasoning yields `CL32[TCC TBD]106[TOL TBD]O[...]`
- convert to DB lookup pattern `CL32_106_O____`
- run the active-lineup DB lookup tool
- show the returned list
- ask a targeted follow-up such as `온도특성은 X5R(A)와 X7R(B) 중 어느 쪽이 필요합니까?`

## Korean Query Expansions

When the user writes in Korean, expand both the Korean phrase and the catalog-facing English alias together.

- `온도특성 A` -> `A`, `X5R`, `온도특성 코드`, `temperature characteristic`
- `정격전압 4V` -> `4.0Vdc`, `code R`, `rated voltage`
- `기준용량 4.8uF` -> `4.8uF`, `4.7uF`, `5.1uF`, `475`, `515`, `capacitance code`
- `M편차` -> `+/-20%`, `tolerance code M`
- `산업용` -> `industrial`, `High Level I`, `High Level II`
- `현재 흐르는 기종`, `현행품`, `현재 흐르는 품목` -> `active lineup`, `chip_prod_id`, `current DB hits`
- `저소음` -> `Low Acoustic Noise`, `ANSC`, `THMC`
- `저ESL` -> `Low ESL`, `LICC`, `SLIC`, `reverse`, `3T`, `8T`
- `고주파 저전계`, `1V DC`, `직류 바이어스` -> `DC bias`, `AC voltage characteristics`, `effective capacitance`, `sample graph`

## Guardrail Phrases

Use these phrases when needed:

- `exact catalog match: none in retrieved evidence`
- `closest catalog anchor supports feasibility, not final orderable confirmation`
- `recommended preselection is a candidate skeleton`
- `needs datasheet validation for 1V DC bias and frequency-dependent effective capacitance`
