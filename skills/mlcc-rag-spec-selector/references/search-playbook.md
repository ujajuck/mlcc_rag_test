# 검색 플레이북

`search_rag`를 구동하고 최종 답변을 구성할 때 이 reference를 참조한다.

## 목차

- 검색 순서
- 랭킹 규칙
- 응답 형식
- 예시 처리 패턴
- 활성 라인업 조회 단계
- 한국어 쿼리 확장
- 가드레일 문구

## 검색 순서

### 1. 코드 테이블 먼저 해석

타깃:

- `part_numbering`

목표:

- 온도특성, 전압, 용량, 편차, 사이즈, 두께 제약조건을 코드 후보로 매핑

쿼리 패턴:

- `temperature characteristic A X5R`
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

### 2. 패밀리 및 신뢰성 해석

타깃:

- `product_family`
- `reliability_level`

목표:

- Standard vs High Level I vs High Level II 선택
- 특수 패밀리 필요 여부 판단

쿼리 패턴:

- `standard MLCC wide lineup`
- `high level I industrial humidity reliability`
- `high level II outdoor 85 85 1000h`
- `산업용 high level II 85C 85RH 1000h`
- `low ESL high speed IC`
- `low acoustic noise piezo PMIC`
- `저소음 PMIC DC-DC`

### 3. 인접 예시 파트 조회

타깃:

- `new_product`

목표:

- 사이즈, 온도특성, 전압, 편차, 패밀리, 명목 용량 기준으로 가장 가까운 카탈로그 앵커 탐색

쿼리 패턴:

- `0201 0603 4.7uF X5R 4.0V +/-20`
- `0201 0603 4.7uF class II`
- `0201 0603 4.7uF X5R 4V M편차`
- `0603 1608 47uF X5R 6.3V`
- `1206 3216 220uF X5R 6.3V`

### 4. 모호성이 남으면 활성 라인업 확인

타깃:

- 입력 파라미터 `chip_prod_id`를 사용하는 활성 라인업 DB 조회 도구

목표:

- 부분 또는 전체 코드 패턴이 `mdh_continous_view_3`에 현재 존재하는지 확인
- 최종 선택을 강제하기 전에 현행 `chip_prod_id` 히트를 표면화

패턴 예시:

- `chip_prod_id = CL32_106_O____`
- `chip_prod_id = %CL32_106_O____%`
- `chip_prod_id = CL03A515MR3____`

처리 규칙:

- 다건 반환 시: 목록을 보여주고 포커스된 후속 질문 1개
- 1건 반환 시: 남은 카탈로그 제약 대비 검증 계속
- 0건 반환 시: 카탈로그 스켈레톤을 유지하고 어떤 미해결 필드를 변경할 수 있는지 질문

### 5. 검증 전용 특성 조회 (필요 시)

타깃:

- `caution_characteristics`

목표:

- 요청된 거동 중 검증 항목으로만 남겨야 하는 것을 판별

쿼리 패턴:

- `DC bias characteristics X5R sample`
- `AC voltage characteristics class II`
- `effective capacitance high frequency low field`
- `impedance characteristic SRF ESR ESL`
- `1V DC bias 고주파 유효용량`

## 랭킹 규칙

후보를 아래 순서로 랭킹한다:

1. 모든 하드 제약 충족
2. 정확한 카탈로그 예시 파트 보유
3. 명시된 한계 내 치수 마진 유지
4. 요청 명목 용량에 가장 가까움
5. 의도된 적용처 또는 패밀리 일치
6. 바이어스 및 주파수 거동에 대한 검증 리스크 최소화

탈락 사유는 항상 명시한다:

- `탈락: 전압 불일치`
- `탈락: L 치수 최대치 초과`
- `탈락: 패밀리 불일치`
- `탈락: 해당 옵션에 대한 카탈로그 근거 없음`

## 응답 형식

아래 순서로 섹션을 출력한다:

1. `제약조건 요약`
2. `코드 매핑 도출`
3. `정확 카탈로그 매칭`
4. `근접 카탈로그 앵커`
5. `권장 후보 스켈레톤`
6. `DB 활성 라인업 히트` (조회 실행 시)
7. `데이터시트 또는 실측 검증 필요 항목`

각 앵커에 대해:

- 일치하는 제약조건
- 불일치하는 제약조건
- 실현 가능성 근거인지 정확 매칭인지 여부

각 후보 스켈레톤에 대해:

- 카탈로그 기준 전기적 타당성 이유
- 아직 최종 주문 가능 P/N이 아닌 이유
- 다음에 확인해야 할 사항

각 DB 조회 단계에 대해:

- 사용한 `chip_prod_id` 패턴
- 결과 건수 (0건, 1건, 다건)
- 히트 목록이 현재 존재만 증명하는지, 모호성도 해결하는지
- 후속 질문 (있는 경우)

## 예시 처리 패턴

사용자가 아래와 같이 요청할 때:

`A 온도특성, 정격전압 4V, L <= 690 um, W <= 390 um, T <= 550 um, 기준용량 4.8 uF, M편차, 고주파 저전계에서 1V DC 전계를 인가했을 때 최소 3.45 uF`

다음 패턴으로 응답한다:

- `A -> X5R`, `R -> 4.0Vdc`, `M -> +/-20%` 매핑
- 예시 파트 검색 전에 `03 (0201 / 0603)` 사이즈 필터 적용
- 가장 가까운 표준 명목 후보 `475`와 `515` 도출
- `0201 / 0603`, Class II, `4.7 uF` 근처에서 예시 파트 검색
- `1V DC 고주파 >= 3.45 uF` 요구는 조회된 청크가 대상 파트에 대해 직접 증명하지 않는 한 검증 전용으로 유지
- 카탈로그 근거가 뒷받침할 때만 더 높은 표준 명목을 우선 추천

## 활성 라인업 조회 단계

카탈로그 추론으로 부분적이지만 유용한 코드 패밀리가 도출되면, 스켈레톤에서 멈추지 않는다. DB 패턴으로 변환하고 대화형으로 계속 진행한다.

예시:

- 카탈로그 추론 결과: `CL32[온도특성 TBD]106[편차 TBD]O[...]`
- DB 조회 패턴으로 변환: `CL32_106_O____`
- 활성 라인업 DB 조회 도구 실행
- 반환된 목록 표시
- 포커스된 후속 질문: `온도특성은 X5R(A)와 X7R(B) 중 어느 쪽이 필요합니까?`

## 한국어 쿼리 확장

사용자가 한국어로 작성하면, 한국어 표현과 카탈로그용 영문 별칭을 함께 확장한다.

- `온도특성 A` -> `A`, `X5R`, `temperature characteristic`
- `정격전압 4V` -> `4.0Vdc`, `code R`, `rated voltage`
- `기준용량 4.8uF` -> `4.8uF`, `4.7uF`, `5.1uF`, `475`, `515`, `capacitance code`
- `M편차` -> `+/-20%`, `tolerance code M`
- `산업용` -> `industrial`, `High Level I`, `High Level II`
- `현재 흐르는 기종`, `현행품`, `현재 흐르는 품목` -> `active lineup`, `chip_prod_id`, `current DB hits`
- `저소음` -> `Low Acoustic Noise`, `ANSC`, `THMC`
- `저ESL` -> `Low ESL`, `LICC`, `SLIC`, `reverse`, `3T`, `8T`
- `고주파 저전계`, `1V DC`, `직류 바이어스` -> `DC bias`, `AC voltage characteristics`, `effective capacitance`, `sample graph`

## 가드레일 문구

필요 시 아래 문구를 사용한다:

- `정확한 카탈로그 일치 항목이 조회된 근거에 없습니다.`
- `근접 카탈로그 앵커는 실현 가능성 근거이며, 최종 주문 가능 확정이 아닙니다.`
- `권장 사전선정안은 후보 스켈레톤입니다.`
- `1V DC 바이어스 및 주파수 의존 유효용량은 데이터시트 검증이 필요합니다.`
