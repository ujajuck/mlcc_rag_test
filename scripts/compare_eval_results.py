"""단일턴 결과 비교 엔트리 (얇은 래퍼).

단일턴/멀티턴 결과 CSV 포맷은 동일하므로 scripts.multiturn.compare 로 위임한다.

usage:
    python scripts/compare_eval_results.py OLD.csv NEW.csv
"""

import sys

from scripts.multiturn.compare import main


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python scripts/compare_eval_results.py OLD.csv NEW.csv"
        )
    main(sys.argv[1], sys.argv[2])
