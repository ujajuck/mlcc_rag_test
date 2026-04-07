이 레포지토리 프로젝트의 목적은 삼성전기 MLCC 개발자가 고객사가 요청한 SPEC을 만족하기 위해 정보를 찾을때 도와주는 skill.md를 구축하기 위한 프로젝트이다.

*파일설명*
MLCC_2512.pdf : 삼성전기 MLCC catalog 원문.
mlcc_catalog_rag_chunks.jsonl : catalog를 vectorDB에 넣기 위해 만들어둔 chunks
mlcc_catalog_rag_master_ko : chunk에 대한 설명 정리본. 

*목적*
사용자가 "고객사 의뢰로 스펙 만족하는 MLCC 기종부터 선정해야해. A 온도특성, 정격전압 4V, L size 최대 690㎛, W size 최대 390㎛, T size 최대 550㎛, 기준용량 4.8㎌, M편차, 고주파 저전계에서 1V DC 전계를 인가하였을 때 최소 3.45㎌ 를 만족하는 기종을 설계해줘."
이런식으로 질문을 했을때,
mlcc_catalog_rag_chunks.jsonl 가 들어있는 vectorDB를 잘 검색하여 결과를 도출해 낼수 있도록 하는 skill를 개발하는게 이 프로젝트의 목적이다. 

*참고사항*
이 skill을 사용하는 에이전트는 사내 폐쇄망 환경이기 때문에 웹서치가 불가능하며, 순수하게 해당 vectorDB만 검색할수 있는 function tool을 하나 가지고 있다. (tool_name : search_rag). 에이전트가 사용하는 llm은 GPT-OSS 120B 수준이다.

*문서 유지 규칙*
- 시스템 흐름 기준 문서는 `SYSTEM_FLOW.md` 이고, 흐름 다이어그램 문서는 루트의 `SYSTEM_FLOW_DIAGRAM.md` 이다.
- 아래 항목이 바뀌면 `SYSTEM_FLOW.md` 와 `SYSTEM_FLOW_DIAGRAM.md` 를 반드시 함께 확인하고, 필요한 경우 같이 수정한다.
  - `mlcc_agent/agent.py` 의 전체 파이프라인, 스킬 등록, 루트 instruction
  - `mlcc_agent/tools/*.py` 의 입력/출력 계약, 상태 전달 방식, 선후행 순서
  - `skills/**/SKILL.md` 및 `skills/**/references/*.md` 의 단계, 라우팅 규칙, 응답 계약
  - `scripts/ingest_to_chromadb.py` 또는 RAG 데이터 파일의 구조/컬렉션 전략
- 문서 갱신 원칙은 아래와 같다.
  - `SYSTEM_FLOW.md` 는 설명 중심으로 유지한다.
  - `SYSTEM_FLOW_DIAGRAM.md` 는 다이어그램 중심 문서로 유지한다.
  - `SYSTEM_FLOW_DIAGRAM.md` 에는 최소 설명과 함께 mermaid 다이어그램을 두고, 적어도 `상위 개요` 와 `상세 I/O 및 외부 의존성` 이 보이도록 유지한다.
  - 흐름 변경이 있었는데 두 문서가 그대로면, 에이전트는 작업을 끝내기 전에 문서 갱신 필요 여부를 다시 확인한다.
  - 흐름 변경이 없으면 문서를 불필요하게 수정하지 않는다.
