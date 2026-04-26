import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mlx_lm_stub = types.ModuleType("mlx_lm")
mlx_lm_stub.generate = lambda *args, **kwargs: ""
mlx_lm_stub.load = lambda *args, **kwargs: (object(), object())
sys.modules.setdefault("mlx_lm", mlx_lm_stub)

