from mlx_lm import generate, load

from polybot.paths import ADAPTERS_DIR


class PolyEngine:
    def __init__(self, model_path="mlx-community/Qwen3.6-27B-mxfp4", adapter_path=None):
        adapter_path = adapter_path or str(ADAPTERS_DIR)
        print(f"Loading model from {model_path} with adapters from {adapter_path}...")
        self.model, self.tokenizer = load(model_path, adapter_path=adapter_path)

    def analyze(self, market_data, system_prompt=None, raw_prompt=None, max_tokens=1000):
        if raw_prompt:
            return generate(
                self.model,
                self.tokenizer,
                prompt=raw_prompt,
                max_tokens=max_tokens,
                verbose=False,
            )

        if system_prompt is None:
            system_prompt = "You are a professional market analyst with self-correction capabilities."

        live_context = market_data.get("live_context", "")
        context_block = f"\n\nLIVE CONTEXT:\n{live_context}" if live_context else ""

        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        prompt += (
            f"<|im_start|>user\nAnalyze this market: {market_data['title']}. "
            f"News: {market_data.get('news', 'N/A')}. Odds: {market_data['odds']}. "
            f"Initial Thought: {market_data.get('initial_thought', 'Analyze for edge.')}"
            f"{context_block}<|im_end|>\n"
        )
        prompt += "<|im_start|>assistant\n"
        return generate(self.model, self.tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)

    def stream_analyze(self, market_data):
        response = self.analyze(market_data)
        for word in response.split(" "):
            yield word + " "
