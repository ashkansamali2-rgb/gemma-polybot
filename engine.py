import os
from mlx_lm import load, generate

class PolyEngine:
    def __init__(self, model_path="mlx-community/Qwen3.6-27B-mxfp4", adapter_path="./poly_adapters"):
        print(f"Loading model from {model_path} with adapters from {adapter_path}...")
        self.model, self.tokenizer = load(model_path, adapter_path=adapter_path)

    def analyze(self, market_data, system_prompt=None, raw_prompt=None):
        if raw_prompt:
            return generate(self.model, self.tokenizer, prompt=raw_prompt, max_tokens=1000, verbose=False)
            
        if system_prompt is None:
            system_prompt = "You are a professional market analyst with self-correction capabilities."
        
        live_context = market_data.get("live_context", "")
        context_block = f"\n\nLIVE CONTEXT:\n{live_context}" if live_context else ""
        
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        prompt += f"<|im_start|>user\nAnalyze this market: {market_data['title']}. News: {market_data.get('news', 'N/A')}. Odds: {market_data['odds']}. Initial Thought: {market_data.get('initial_thought', 'Analyze for edge.')}{context_block}<|im_end|>\n"
        prompt += f"<|im_start|>assistant\n"
        return generate(self.model, self.tokenizer, prompt=prompt, max_tokens=1000, verbose=False)

    def stream_analyze(self, market_data):
        response = self.analyze(market_data)
        for word in response.split(" "):
            yield word + " "


if __name__ == "__main__":
    # Test
    engine = PolyEngine()
    result = engine.analyze({"title": "Will BTC hit $100k?", "odds": "45%", "news": "Institutional buying increasing."})
    print(result)
