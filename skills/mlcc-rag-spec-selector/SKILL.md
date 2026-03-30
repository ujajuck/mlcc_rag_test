---
name: mlcc-rag-spec-selector
description: Search-rag-plus-lineup skill for Samsung Electro-Mechanics MLCC catalog preselection and active product narrowing. Use when an agent in a closed network must answer customer MLCC spec requests or Korean prompts such as `온도특성 A`, `정격전압 4V`, `기준용량 4.8uF`, `M편차`, `고객사 의뢰 스펙 만족 MLCC 선정`, or partial part patterns like `CL32_106_O____` by querying a vector DB built from the SEMCO MLCC commercial-industrial catalog, mapping natural-language or 자연어 제약조건 to catalog codes, retrieving supporting chunks, proposing candidate part-number skeletons, and, when the request is partial or ambiguous, using a DB lookup function on `chip_prod_id` to list currently flowing matches before continuing the dialogue.
---

# MLCC RAG Spec Selector

Convert customer MLCC requirements into catalog-based candidates using `search_rag` first and an active-lineup DB lookup when needed. Use this skill for preselection and evidence-backed reasoning, not for final orderable P/N confirmation.

Read the bundled references as needed:

- Read `references/catalog-codebook.md` for code maps, family routing, chunk targets, size/thickness filtering rules, and catalog guardrails.
- Read `references/search-playbook.md` for search order, query patterns, ranking, and response format.
- Read `references/active-lineup-lookup.md` when the request is partial, ambiguous, requires checking currently flowing products by `chip_prod_id`, or when finding contiguous/adjacent models (인접기종) via `search_query_database`.
- Read `references/prompt-examples.md` for Korean and mixed-language invocation examples.

## Operating Boundaries

- Treat the catalog as authoritative for temperature-characteristic or dielectric codes, voltage codes, capacitance-code rules, tolerance codes, size codes, thickness-code filtering, reliability-family descriptions, and any example part number explicitly shown in retrieved chunks.
- Treat the active-lineup DB lookup as authoritative only for whether matching `chip_prod_id` rows currently exist in the `mdh_continous_view_3` view.
- Treat DC-bias behavior, high-frequency effective capacitance, ESR/ESL exact values, exact orderable tail codes, and real lineup availability as validation-only unless a retrieved chunk states them directly for the target part.
- Treat caution graphs and characteristic plots as sample guidance only. Do not convert them into exact guarantees for a candidate part.
- Never invent a full part number when the 8th-11th codes are not directly supported by retrieved evidence. Emit a skeleton or mark fields as TBD.

## Workflow

1. Parse the user request into:
   - hard constraints: temperature characteristic or dielectric code, rated voltage, L/W/T max, tolerance, explicit family or reliability requirement
   - soft constraints: application hints, preferred nominal capacitance, packaging preference, anchor proximity
   - validation-only constraints: effective capacitance under bias or frequency, ESR/ESL, ripple, exact tail code
   - active-lineup check trigger: partial request, ambiguous request, user asks whether the product is currently flowing, or unresolved code positions remain after catalog reasoning
   - adjacent/contiguous model search trigger: user asks for 인접기종, adjacent models, or contiguous models → use `search_query_database` with a SQL query against `public.mdh_contiguous_condition_view_dsgnagent`
2. Normalize units before retrieval:
   - lengths to `mm`
   - capacitance to `uF` and derived E-series code candidates
   - voltage to `Vdc`
   - tolerance words such as `M` to both code and percent
3. Retrieve `part_numbering` evidence first. Resolve temperature characteristic or dielectric code, voltage, capacitance, tolerance, size, and thickness-code constraints before searching example parts.
4. Retrieve `product_family` and `reliability_level` evidence next. Use application hints to choose between Standard, High Level I, High Level II, MFC, LSC, High Bending Strength, Low Acoustic Noise, and Low ESL.
5. Retrieve `new_product` anchors after the code mapping is stable. Prefer nearby catalog examples over free-form guessing.
6. Build one or more `candidate skeletons` from the catalog evidence. If the request is incomplete, also build a `chip_prod_id lookup pattern` that preserves known code positions and marks unresolved single-character slots with `_`.
7. If an active-lineup lookup tool is available and the request is partial, ambiguous, or needs current-product confirmation, call that tool with the `chip_prod_id` pattern and get the returned list before trying to force a final answer.
   - For **contiguous/adjacent model search** (인접기종 검색), use `search_query_database` instead. Write a SQL SELECT query against `public.mdh_contiguous_condition_view_dsgnagent` with `ILIKE` to find adjacent models sharing similar chip_prod_id patterns.
8. If the DB lookup returns multiple hits, show the list and ask one targeted follow-up question that narrows the unresolved slot or requirement. Continue the conversation instead of picking arbitrarily.
9. If the DB lookup returns zero hits, enter the **condition-relaxation loop**:
   a. Identify which spec dimensions are encoded in the current skeleton. For example `CL32_106_O____` encodes size (`32` = 1210), capacitance (`106` = 10 uF), and voltage (`O` = 16 V).
   b. Present these locked dimensions to the user and ask which one they would like to relax — expand upward, downward, or both. Phrase the options concretely:
      - Size: "사이즈를 한 단계 키워 1812(43)로 검색할까요, 또는 줄여 0805(21)로 검색할까요?"
      - Capacitance: "용량을 4.7 uF(475)로 낮추거나, 22 uF(226)로 올려 검색할까요?"
      - Voltage: "전압을 25 V(A)로 올리거나, 10 V(P)로 낮춰 검색할까요?"
   c. After the user picks a condition to change, rebuild the chip_prod_id skeleton with the new code and run `active_lineup_lookup` again.
   d. If the retry also returns zero hits, repeat from (b) — offer further relaxation or a different dimension. If the user has already relaxed two or more dimensions without success, suggest broadening the search by using `%` wildcards or leaving more positions as `_`.
   e. Once hits are found, continue from step 8 (multiple-hit narrowing) or step 10 (synthesis).
10. Retrieve `caution_characteristics` only when the user asks for bias, frequency, impedance, or aging behavior. Use those chunks to define what still needs datasheet or measured-data validation.
11. Synthesize the answer by separating:
   - exact catalog matches
   - closest catalog anchors
   - recommended candidate skeletons
   - current active-lineup hits from DB, when checked
   - unresolved validation items

## Retrieval Rules

- Search iteratively. Do not stop after one query.
- Start broad enough to find the right chunk family, then tighten around size, temperature characteristic, voltage, and nominal capacitance.
- Use bilingual and alias expansions when helpful, for example `X5R`, `A code`, `온도특성 A`, `0603`, `0201`, `High Level II`, `산업용`, `DC bias`, `직류 바이어스`.
- If the requested nominal is not a standard catalog nominal, present the nearest standard candidates instead of silently snapping to one.
- If no exact anchor exists, say so explicitly and keep the output at skeleton level.
- If unresolved positions remain, transform the catalog skeleton into a DB lookup pattern and prefer an interactive narrowing step over a forced guess.
- Use `_` for unknown single-character code positions in a `chip_prod_id` pattern. Use `%` only when the actual DB tool contract expects SQL-like wildcard matching over variable-length prefix or suffix.
- Do not promise that you will run a DB lookup later. If the tool is available and the pattern is ready, run it in the current turn.

## Response Contract

Structure the final answer in this order:

1. `constraints summary`
2. `derived code mapping`
3. `exact catalog matches`
4. `closest catalog anchors`
5. `recommended candidate skeletons`
6. `active lineup hits from DB` when a `chip_prod_id` lookup was run
7. `needs datasheet or measured validation`

For each recommended skeleton:

- explain which hard constraints it satisfies
- explain which catalog anchor supports it
- explain why it ranks above alternatives
- list each unresolved item in concrete language

For each DB lookup step:

- show the pattern you searched
- show the returned `chip_prod_id` list or count
- explain what remains ambiguous
- ask one focused follow-up question if multiple active hits remain

For each condition-relaxation step (zero-hit retry):

- show the original pattern and confirm it returned 0 hits
- list the locked dimensions with their current values and the nearest alternative codes in each direction (e.g., size up/down, capacitance up/down, voltage up/down)
- ask the user which dimension to relax and in which direction
- after rebuilding the skeleton, show the new pattern before querying again

## Failure Handling

Use explicit guardrail language when evidence is incomplete:

- `No exact catalog match found; providing candidate skeletons only.`
- `Catalog supports preselection, not final orderable P/N confirmation.`
- `Exact tail codes and bias-effective capacitance require datasheet or measured-data validation.`
- `Current DB hits were listed for the partial pattern, but additional constraints are needed before selecting one active product.`
- `No current DB hits were found for the partial pattern; confirm whether any of the unresolved fields can change.`
- `조건 완화 검색: [dimension]을(를) [old value] → [new value]로 변경하여 재검색합니다.`
- `[N]개 조건을 완화했으나 여전히 0건입니다. 와일드카드를 넓히거나 추가 조건 변경이 필요합니다.`

If the user asks for a guarantee that exceeds catalog evidence, refuse the guarantee and provide the strongest catalog-based preselection instead.
