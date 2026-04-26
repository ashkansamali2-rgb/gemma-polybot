from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot.config import StrategyConfig
from polybot.runner import build_runner


def run_autopilot():
    config = StrategyConfig()
    runner = build_runner(mode="paper", config=config)
    runner.run_live(once=False)


if __name__ == "__main__":
    try:
        run_autopilot()
    except KeyboardInterrupt:
        print("AUTOPILOT_SHUTDOWN_BY_USER.")
