from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot_infra.settlement import run_settlement


if __name__ == "__main__":
    run_settlement()
