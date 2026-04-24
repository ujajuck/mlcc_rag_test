"""MLCC 멀티턴 평가 패키지.

파일 구성:
    types.py      - 데이터클래스 (TestCase / TurnRecord / CaseResult)
    plugins.py    - ADK BasePlugin (skill/tool/model 추적 콜백)
    evaluator.py  - 턴별 pass/fail 판정
    runner.py     - 한 케이스(멀티턴) 실행
    io.py         - CSV 로더, 결과 CSV/JSON 저장
    compare.py    - 두 결과 CSV 비교
"""
