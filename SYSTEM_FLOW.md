# 시스템 흐름

이 문서는 현재 레포의 실제 코드와 스킬 문서를 기준으로, 사용자 요청이 어떤 단계와 도구를 거쳐 처리되는지 정리한 기준 문서이다.

## 1. 목적

이 프로젝트의 목표는 삼성전기 MLCC 개발자가 고객 스펙 요청을 받았을 때,

1. 카탈로그와 RAG 데이터를 바탕으로 후보 기종을 좁히고
2. 필요하면 인접 기종과 REF LOT를 찾고
3. DOE / 신뢰성 시뮬레이션으로 설계값을 검토하고
4. 최종적으로 공정 적용 가능 여부와 적층투입지시까지 이어질 수 있게

에이전트와 스킬 체계를 만드는 것이다.

## 2. 상위 구조

레포는 크게 4개 층으로 나뉜다.

- 데이터 자산
  - `MLCC_2512.pdf`
  - `mlcc_catalog_rag_master_ko.md`
  - `mlcc_catalog_rag_chunks*.jsonl`
  - `mlcc_catalog_partnumber_core_v2.jsonl`
- 런타임
  - `mlcc_agent/agent.py`
  - `mlcc_agent/db.py`
  - `mlcc_agent/tools/*.py`
- 스킬 정의
  - `skills/mlcc-rag-spec-selector`
  - `skills/mlcc-optimal-design-doe`
  - `skills/mlcc-design-dispatch`
- 데이터 적재
  - `scripts/ingest_to_chromadb.py`

## 3. 핵심 구성요소 역할

### Root Agent

`mlcc_agent/agent.py` 의 `root_agent` 가 전체 오케스트레이션을 담당한다.

- 3개 스킬 디렉터리를 ADK `load_skill_from_dir` 로 읽는다.
- `SkillToolset` 으로 스킬을 묶는다.
- 스킬 외에도 low-level tool 을 직접 사용할 수 있다.
- 루트 instruction 에 전체 파이프라인과 금지 규칙이 들어 있다.

현재 등록된 주요 단계는 아래와 같다.

1. `mlcc-rag-spec-selector`
2. `mlcc-optimal-design-doe`
3. `mlcc-design-dispatch`

## 4. Skill별 역할

### 4.1 `mlcc-rag-spec-selector`

고객의 자연어 스펙 요청을 카탈로그 기반 후보와 `chip_prod_id` 패턴으로 바꾸는 단계다.

핵심 역할:
- 자연어 조건을 hard / soft / validation-only 제약으로 분해
- `catalog-codebook.md` 를 우선 사용해 품번 position 1~7 코드를 해석
- 필요할 때만 `search_rag` 로 패밀리, 앵커, 주의 특성을 보강
- 필요 시 `active_lineup_lookup` 또는 `search_query_database` 로 활성 라인업 / 인접기종 탐색

주요 출력:
- 후보 part-number skeleton
- `chip_prod_id_list` 또는 조회 패턴
- 검증이 더 필요한 항목

### 4.2 `mlcc-optimal-design-doe`

후보 기종에서 REF LOT를 찾고, DOE / 신뢰성 시뮬레이션까지 이어지는 단계다.

핵심 역할:
- `chip_prod_id_list` 를 `lot_id` 로 바꾸기
- REF LOT 상세정보를 state 에 적재
- 시뮬레이션 가능 여부 검증
- `optimal_design` 또는 `reliability_simulation` 실행
- 필요 시 부족인자 보충과 재실행

필수 흐름:
1. `find_ref_lot_candidate`
2. `get_first_lot_detail`
3. `check_optimal_design`
4. `optimal_design` 또는 `reliability_simulation`

### 4.3 `mlcc-design-dispatch`

최종 설계값을 실제 공정에 적용하기 전에 검증하고, 적층투입지시까지 이어가는 단계다.

핵심 역할:
- 스크린 동판 존재 여부 검색
- 현재 공정에서 유사 조건의 실제 칩 검색
- 사용자 최종 확인 후 적층투입지시 실행

기본 흐름:
1. `search_screen_plate`
2. `search_running_chips`
3. `dispatch_stacking_order`

## 5. Tool 계층

실행은 결국 `mlcc_agent/tools/*.py` 의 tool 이 담당한다.

### RAG / 조회 계층

- `search_rag`
  - 카탈로그 chunk 검색
  - 현재 로컬 구현은 JSONL 기반 mock
  - 운영 의도는 vector DB 검색
- `active_lineup_lookup`
  - `chip_prod_id` 패턴으로 현재 흐르는 제품 검색
- `search_query_database`
  - 인접기종 탐색용 SQL SELECT 실행
- `read_md_file`
  - 스킬 reference 문서를 런타임에 읽기 위한 도구

### DOE / 신뢰성 계층

- `find_ref_lot_candidate`
- `get_first_lot_detail`
- `check_optimal_design`
- `update_lot_reference`
- `optimal_design`
- `reliability_simulation`

### 공정 적용 계층

- `search_screen_plate`
- `search_running_chips`
- `dispatch_stacking_order`

## 6. 상태 전달 방식

이 시스템은 단계 사이 데이터를 일부 세션 state 로 넘긴다.

대표 예시는 아래와 같다.

- `get_first_lot_detail`
  - `lot_id` 기준 상세 데이터를 `tool_context.state[lot_id]` 에 저장
- `check_optimal_design`
  - 검증 결과를 `tool_context.state['validation'][lot_id]` 에 저장
- `optimal_design`
  - 위 validation 결과를 확인한 뒤 시뮬레이션 실행

즉, DOE 단계는 단순 호출 체인이 아니라 `lot_id -> state 적재 -> validation -> simulation` 구조를 갖는다.

## 7. 데이터 흐름

### 7.1 RAG 데이터 준비

카탈로그 데이터 흐름은 아래와 같다.

1. PDF 원문
   - `MLCC_2512.pdf`
2. 사람이 읽기 쉬운 정리 문서
   - `mlcc_catalog_rag_master_ko.md`
3. 검색용 chunk JSONL
   - `mlcc_catalog_rag_chunks_v2_partnumber_focused.jsonl`
   - `mlcc_catalog_partnumber_core_v2.jsonl`
4. Chroma 적재
   - `scripts/ingest_to_chromadb.py`

### 7.2 컬렉션 전략

`scripts/ingest_to_chromadb.py` 는 크게 3개 컬렉션 전략을 가진다.

- `core`
  - part-number mapping 중심
- `context`
  - family / caution / dimension 등 맥락 중심
- `full`
  - 전체 통합

스킬 문서 기준으로는 code mapping 은 codebook 우선이고, `search_rag` 는 맥락 검색에 가깝게 쓰는 구조를 권장한다.

## 8. 사용자 요청 처리 흐름

### 8.1 스펙 선정 요청

예: 고객 스펙을 만족하는 MLCC 후보를 찾아달라는 요청

1. 사용자가 자연어 스펙을 입력한다.
2. Root Agent 가 요청을 분석한다.
3. `mlcc-rag-spec-selector` 가 코드북 우선으로 품번 규칙을 해석한다.
4. 필요하면 `search_rag` 로 패밀리 / 앵커 / 주의 특성을 보강한다.
5. 필요하면 활성 라인업 또는 인접기종 DB 조회를 한다.
6. 후보 skeleton, `chip_prod_id_list`, 검증 포인트를 응답한다.

### 8.2 DOE / 설계 요청

예: 위 후보들로 REF LOT를 찾고 설계를 돌려달라는 요청

1. Agent 가 DOE 단계 요청으로 판단한다.
2. `mlcc-optimal-design-doe` 로 진입한다.
3. `chip_prod_id_list` 를 `find_ref_lot_candidate` 에 넣어 `lot_id` 를 확보한다.
4. `get_first_lot_detail` 로 REF LOT 정보를 state 에 적재한다.
5. `check_optimal_design` 로 시뮬레이션 가능 여부를 검증한다.
6. `optimal_design` 또는 `reliability_simulation` 을 실행한다.
7. 최종 설계 후보를 사용자에게 제시한다.

### 8.3 공정 검증 / 투입 요청

예: 확정된 설계값으로 동판 확인과 투입까지 요청하는 경우

1. Agent 가 dispatch 단계 요청으로 판단한다.
2. `mlcc-design-dispatch` 로 진입한다.
3. `search_screen_plate` 로 스크린 동판을 검색한다.
4. `search_running_chips` 로 유사 실제 칩을 검색한다.
5. `dispatch_stacking_order(user_confirmed=False)` 로 사용자 확인용 요약을 만든다.
6. 사용자가 승인하면 `dispatch_stacking_order(user_confirmed=True)` 로 실제 투입을 실행한다.

## 9. 현재 구현과 운영 의도의 차이

현재 레포는 운영 구조와 로컬 개발용 mock 구현이 함께 들어 있다.

- `search_rag` 는 현재 JSONL 키워드 검색 mock 이다.
- `search_screen_plate`, `search_running_chips`, `dispatch_stacking_order` 는 환경변수 존재 여부에 따라 production/mock 경로를 나눈다.
- 일부 DOE / 신뢰성 tool 은 외부 API URL 환경변수에 의존한다.

따라서 문서화 시에는 아래 원칙을 따른다.

- 실제 코드에 구현된 현재 동작을 우선 기록한다.
- 운영 의도와 현재 mock 이 다르면 둘을 구분해서 쓴다.

## 10. 흐름 다이어그램

흐름 다이어그램의 mermaid 원문은 루트의 `mermaid.md` 에 분리해 둔다.

- 설명이 바뀌면 `SYSTEM_FLOW.md` 를 수정한다.
- 단계 구조나 연결 관계가 바뀌면 `mermaid.md` 도 함께 수정한다.

## 11. 이 문서를 같이 수정해야 하는 변경

아래 변경이 있으면 이 문서와 `mermaid.md` 를 함께 업데이트한다.

- 새로운 skill 추가 / 제거
- skill 간 선후행 순서 변경
- 주요 tool 의 입력/출력 계약 변경
- state 저장 방식 변경
- RAG 컬렉션 전략 변경
- mock 에서 production 으로 동작 방식이 바뀌는 경우
- 사용자 요청 처리 경로가 달라지는 instruction 변경
