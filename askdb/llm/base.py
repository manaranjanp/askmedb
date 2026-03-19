"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers.

    Implement this interface to use any LLM backend (OpenAI, Anthropic,
    local models, etc.).
    """

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a completion from a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text content.

        Raises:
            LLMError: If the API call fails after retries.
        """
        ...
