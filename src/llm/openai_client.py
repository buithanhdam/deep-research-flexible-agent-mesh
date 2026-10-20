"""OpenAI ChatGPT client (drop-in alternative to OpenRouterClient).

Exposes the same interface (`chat_completion`, `chat`) so it can be swapped
in via `src.llm.llm_manager.get_llm_client(provider="chatgpt")`.
"""

import json
from typing import Dict, List, Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import requests

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """Client for interacting with OpenAI ChatGPT API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to config)
            model: Model name (defaults to config)
            base_url: Base URL (defaults to config)
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model or config.OPENAI_MODEL
        self.base_url = (base_url or config.OPENAI_BASE_URL).rstrip("/")

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion request to OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format (e.g., {"type": "json_object"})
            tools: Optional tool definitions for function calling

        Returns:
            Full response dict (OpenAI schema)
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools

        # Retry is built dynamically from config.MAX_RETRIES so that
        # .env (MAX_RETRIES) actually takes effect.
        retrying_call = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )(self._request)

        return retrying_call(payload=payload, **kwargs)

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the HTTP request against OpenAI."""
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=config.TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """Convenience method: send chat and return only the message content.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            json_mode: Force JSON response format

        Returns:
            String content of the assistant message
        """
        response_format = {"type": "json_object"} if json_mode else None

        response = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            **kwargs
        )

        return self.get_message_content(response)

    def get_message_content(self, response: Dict[str, Any]) -> str:
        """Extract message content from API response.

        Args:
            response: Full OpenAI response dict

        Returns:
            Content string (empty string if not found)
        """
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract message content: {e}")
            return ""
