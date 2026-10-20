"""Unified LLM Provider Manager.

Provides a single entry point (`get_llm_client`) to acquire the configured
LLM client based on `LLM_PROVIDER` in .env:
  - openrouter : OpenRouter (multi-provider aggregator)
  - chatgpt    : OpenAI ChatGPT (gpt-4o, etc.)
  - gemini     : Google Gemini (google-genai SDK, default fallback)
  - custom     : Any OpenAI-compatible custom endpoint (base_url + key)

Each provider is initialized from environment keys and supports runtime
overrides via parameters (provider/model/api_key).
"""

from typing import Optional

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

VALID_PROVIDERS = ("openrouter", "chatgpt", "gemini", "custom")


def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Return an LLM client matching the selected provider.

    Priority: explicit argument > config.LLM_PROVIDER > fallback to gemini.

    Args:
        provider: Override provider ('openrouter' | 'chatgpt' | 'gemini' | 'custom')
        model: Override model name for the selected provider
        api_key: Override API key for the selected provider

    Returns:
        Client instance exposing `chat_completion()` and `chat()`.

    Raises:
        ValueError: If the provider is unsupported or missing required key.
    """
    selected = (provider or config.LLM_PROVIDER or "").lower().strip()

    if selected not in VALID_PROVIDERS:
        logger.warning(
            f"Unknown LLM_PROVIDER '{selected}' — falling back to 'gemini'."
        )
        selected = "gemini"

    try:
        return _build_client(selected, model=model, api_key=api_key)
    except (ValueError, Exception) as e:
        logger.error(
            f"Failed to init LLM provider '{selected}': {e}. "
            f"Falling back to 'gemini'."
        )
        return _build_client("gemini", model=model, api_key=api_key)


def _build_client(provider: str, model: Optional[str] = None, api_key: Optional[str] = None):
    """Instantiate the concrete client for a provider."""
    if provider == "openrouter":
        from src.llm.openrouter_client import OpenRouterClient

        return OpenRouterClient(
            api_key=api_key or config.OPENROUTER_API_KEY,
            model=model or config.OPENROUTER_MODEL,
            base_url=config.OPENROUTER_BASE_URL,
        )

    if provider == "chatgpt":
        from src.llm.openai_client import OpenAIClient

        return OpenAIClient(
            api_key=api_key or config.OPENAI_API_KEY,
            model=model or config.OPENAI_MODEL,
            base_url=config.OPENAI_BASE_URL,
        )

    if provider == "gemini":
        from src.llm.gemini_client import GeminiClient

        return GeminiClient(
            api_key=api_key or config.GEMINI_API_KEY,
            model=model or config.GEMINI_MODEL,
        )

    if provider == "custom":
        from src.llm.custom_client import CustomClient

        return CustomClient(
            api_key=api_key or config.CUSTOM_LLM_API_KEY,
            model=model or config.CUSTOM_LLM_MODEL,
            base_url=config.CUSTOM_LLM_BASE_URL,
        )

    raise ValueError(f"Unsupported provider: {provider}")
