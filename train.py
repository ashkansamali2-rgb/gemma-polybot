import os
import subprocess
import sys

def start_training():
    # Model and Data Paths
    # Using Qwen2.5-VL as it's the standard for Vision-Language MLX fine-tuning currently
    model_id = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit" 
    train_data_dir = "finetune/"
    adapter_path = "poly_adapters"

    # MLX-VLM LoRA command
    # Note: mlx_vlm.lora is the module for VLM fine-tuning
    command = [
        sys.executable, "-m", "mlx_vlm.lora",
        "--model", model_id,
        "--train",
        "--data", train_data_dir,
        "--iters", "200",
        "--adapter-path", adapter_path,
        "--batch-size", "1",
        "--lora-layers", "16",
        "--lr", "1e-5",
        "--steps-per-report", "10"
    ]

    print(f"Starting MLX-VLM LoRA training for {model_id}...")
    print(f"Command: {' '.join(command)}")
    
    # Ensure finetune directory has train.jsonl
    if not os.path.exists(os.path.join(train_data_dir, "train.jsonl")):
        print(f"Error: train.jsonl not found in {train_data_dir}")
        return

    try:
        # Run the training process
        # We'll use subprocess.run here to see immediate output for this setup turn
        # In a real scenario, you might want Popen for backgrounding
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        print("Training started. Monitoring output (first 20 lines)...")
        for i in range(20):
            line = process.stdout.readline()
            if line:
                print(line.strip())
            else:
                break
        
        print("\nTraining is continuing in the background.")
        print(f"To monitor loss, run: tail -f training.log")
        
    except Exception as e:
        print(f"Error during training execution: {e}")

if __name__ == "__main__":
    os.makedirs("poly_adapters", exist_ok=True)
    start_training()
