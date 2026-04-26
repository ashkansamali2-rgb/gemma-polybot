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
