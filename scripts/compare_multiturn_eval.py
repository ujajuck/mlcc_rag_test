"""멀티턴 평가 결과 비교 엔트리 (얇은 래퍼).

usage:
    python scripts/compare_multiturn_eval.py OLD.csv NEW.csv
"""

import sys

from scripts.multiturn.compare import main


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python scripts/compare_multiturn_eval.py OLD.csv NEW.csv"
        )
    main(sys.argv[1], sys.argv[2])
