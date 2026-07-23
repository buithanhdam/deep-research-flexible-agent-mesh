"""OpenRouter API client for LLM interactions."""

import json
from typing import Dict, List, Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import requests

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to config)
            model: Model name (defaults to config)
            base_url: Base URL (defaults to config)
        """
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.model = model or config.OPENROUTER_MODEL
        self.base_url = base_url or config.OPENROUTER_BASE_URL

        if not self.api_key:
            raise ValueError("OpenRouter API key is required")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/buithanhdam",
            "X-Title": "Multi-Agent System"
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
        """Send chat completion request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format (e.g., {"type": "json_object"})
            **kwargs: Additional parameters for the API

        Returns:
            API response dict
        """
        # Retry được build động theo config.MAX_RETRIES thay vì hardcode 3,
        # để .env (AGENT_MAX_RETRIES) thực sự có tác dụng.
        retrying_call = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )(self._chat_completion_request)

        return retrying_call(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            **kwargs
        )

    def _chat_completion_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Single (non-retried) call to OpenRouter — wrapped by chat_completion()."""
        logger.info(
            "chat_completion_request",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
            has_tools=bool(tools)
        )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if response_format:
            payload["response_format"] = response_format

        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=config.TIMEOUT_SECONDS
            )
            response.raise_for_status()

            result = response.json()

            # Detect API-level error inside 200 response (OpenRouter quirk)
            if "error" in result:
                err = result["error"]
                err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                logger.error("openrouter_api_error", error=err_msg, full=result)
                raise RuntimeError(f"OpenRouter API error: {err_msg}")

            logger.info(
                "chat_completion_success",
                model=self.model,
                usage=result.get("usage", {})
            )

            return result

        except requests.exceptions.HTTPError as e:
            # Extract body for richer error message
            try:
                body = e.response.json()
            except Exception:
                body = e.response.text if e.response else ""
            logger.error("chat_completion_http_error", status=e.response.status_code if e.response else None, body=str(body)[:500])
            raise RuntimeError(f"HTTP {e.response.status_code if e.response else '?'}: {body}") from e

        except requests.exceptions.RequestException as e:
            logger.error("chat_completion_request_error", error=str(e))
            raise

    def get_message_content(self, response: Dict[str, Any]) -> str:
        """Extract message content from API response.

        Args:
            response: API response dict

        Returns:
            Message content string
        """
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("failed_to_extract_message", error=str(e))
            raise ValueError("Invalid response format") from e

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """Simplified chat interface that returns just the content.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            json_mode: Whether to request JSON response
            **kwargs: Additional parameters

        Returns:
            Message content as string
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


# Singleton instance
_client: Optional[OpenRouterClient] = None


def get_client() -> OpenRouterClient:
    """Get or create OpenRouter client singleton."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client