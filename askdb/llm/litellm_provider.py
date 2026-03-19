"""LiteLLM-based LLM provider supporting 100+ models."""

import time
from litellm import completion

from .base import BaseLLMProvider
from ..core.exceptions import LLMError


class LiteLLMProvider(BaseLLMProvider):
    """LLM provider using LiteLLM.

    Supports any provider that LiteLLM supports: OpenAI, Anthropic, Groq,
    Ollama, Azure, Hugging Face, and many more.

    Args:
        model: Model string in LiteLLM format (e.g. "anthropic/claude-haiku-4-5-20251001",
               "groq/llama-3.3-70b-versatile", "gpt-4o").
        max_retries: Number of retries with exponential backoff on failure.
    """

    def __init__(self, model: str, max_retries: int = 3):
        self.model = model
        self.max_retries = max_retries

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a completion using LiteLLM."""
        for attempt in range(self.max_retries):
            try:
                response = completion(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise LLMError(f"LLM call failed after {self.max_retries} attempts: {e}") from e
                wait = 2 ** attempt
                time.sleep(wait)
