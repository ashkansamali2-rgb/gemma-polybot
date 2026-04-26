from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot.paths import ADAPTERS_DIR


def start_training():
    model_id = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
    train_data_dir = "finetune"
    adapter_path = str(ADAPTERS_DIR)

    command = [
        sys.executable,
        "-m",
        "mlx_vlm.lora",
        "--model",
        model_id,
        "--train",
        "--data",
        train_data_dir,
        "--iters",
        "200",
        "--adapter-path",
        adapter_path,
        "--batch-size",
        "1",
        "--lora-layers",
        "16",
        "--lr",
        "1e-5",
        "--steps-per-report",
        "10",
    ]

    print(f"Starting MLX-VLM LoRA training for {model_id}...")
    print(f"Command: {' '.join(command)}")

    if not os.path.exists(os.path.join(train_data_dir, "train.jsonl")):
        print(f"Error: train.jsonl not found in {train_data_dir}")
        return

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        print("Training started. Monitoring output (first 20 lines)...")
        for _ in range(20):
            line = process.stdout.readline()
            if line:
                print(line.strip())
            else:
                break

        print("\nTraining is continuing in the background.")
        print("To monitor loss, inspect logs/training.log")
    except Exception as e:
        print(f"Error during training execution: {e}")


if __name__ == "__main__":
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    start_training()
