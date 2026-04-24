"""평가 결과 CSV 두 개를 비교하는 엔트리.

usage:
    python scripts/compare_eval.py OLD.csv NEW.csv
"""

import sys

from scripts.multiturn.compare import main


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python scripts/compare_eval.py OLD.csv NEW.csv")
    main(sys.argv[1], sys.argv[2])
