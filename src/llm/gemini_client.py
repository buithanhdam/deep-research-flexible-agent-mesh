"""Google Gemini client (via google-genai SDK) — mirrors OpenRouterClient interface.

Why a separate client?
  Google Search Grounding is a *native* Gemini feature only available through the
  `google-genai` SDK — it is NOT exposed via OpenRouter. This client provides:
    1. `chat_completion()`  — standard text generation (drop-in alternative to OpenRouter)
    2. `search_grounding()` — Google Search grounding with citations (unique to Gemini)

The client is optional: if `GEMINI_API_KEY` is not set, `get_gemini_client()` returns
None and callers should fall back to OpenRouter / Tavily / DuckDuckGo.
"""

from typing import Dict, List, Optional, Any

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """Client for interacting with Google Gemini via the google-genai SDK.

    Provides both standard chat completion and Google Search Grounding.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize Gemini client.

        Args:
            api_key: Google AI API key (defaults to config.GEMINI_API_KEY).
            model: Gemini model name (defaults to config.GEMINI_MODEL).

        Raises:
            ValueError: If no API key is provided.
        """
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.GEMINI_MODEL

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiClient")

        # Lazy import — google-genai is an optional dependency.
        # Importing here (not at module top) means the rest of the app works
        # fine even if google-genai is not installed.
        from google import genai

        self._client = genai.Client(api_key=self.api_key)
        logger.info("gemini_client_initialized", model=self.model)

    # ------------------------------------------------------------------ #
    # Standard chat completion (mirrors OpenRouterClient.chat_completion)
    # ------------------------------------------------------------------ #
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat completion request to Gemini.

        Converts OpenAI-style messages to Gemini `contents` format internally.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": str}.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            json_mode: If True, request JSON output.
            **kwargs: Additional generation config options.

        Returns:
            Normalized response dict (compatible with OpenRouterClient shape):
            {"choices": [{"message": {"content": str}}], "usage": {...}}
        """
        from google.genai import types

        retrying = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

        return retrying(self._chat_completion_request)(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            **kwargs,
        )

    def _chat_completion_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Single (non-retried) chat completion call to Gemini."""
        from google.genai import types

        logger.info(
            "gemini_chat_request",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
            json_mode=json_mode,
        )

        # Extract system instruction (Gemini handles system separately)
        system_parts = [
            m["content"] for m in messages if m.get("role") == "system"
        ]
        system_instruction = "\n\n".join(system_parts) if system_parts else None

        # Convert non-system messages to Gemini contents
        contents = self._messages_to_contents(
            [m for m in messages if m.get("role") != "system"]
        )

        # Build generation config
        gen_config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_tokens:
            gen_config_kwargs["max_output_tokens"] = max_tokens
        if json_mode:
            gen_config_kwargs["response_mime_type"] = "application/json"

        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            **gen_config_kwargs,
        )

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=gen_config,
        )

        content = self._extract_text(response)

        logger.info("gemini_chat_success", model=self.model)

        # Normalize to OpenAI-like shape for compatibility
        return {
            "choices": [{"message": {"content": content}}],
            "usage": self._extract_usage(response),
        }

    # ------------------------------------------------------------------ #
    # Google Search Grounding (unique to Gemini)
    # ------------------------------------------------------------------ #
    def search_grounding(
        self,
        query: str,
        temperature: float = 0.2,
        max_citations: int = 5,
    ) -> Dict[str, Any]:
        """Run Google Search Grounding via Gemini.

        Gemini searches Google *during inference* and returns a synthesized
        answer with citation sources.

        Args:
            query: The question / search query to ground.
            temperature: Low temperature for factual grounding (default 0.2).
            max_citations: Maximum citation sources to return.

        Returns:
            Dict with keys:
              - answer: str          — synthesized grounded answer
              - citations: list[dict] — [{title, url, content}]
              - queries: list[str]   — actual Google search queries used
              - model: str
        """
        from google.genai import types

        logger.info("gemini_search_grounding_request", query=query, model=self.model)

        retrying = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

        response = retrying(self._grounding_request)(
            query=query, temperature=temperature
        )

        answer = self._extract_text(response)
        citations = self._extract_citations(response, max_citations)
        queries = self._extract_search_queries(response)

        logger.info(
            "gemini_search_grounding_success",
            query=query,
            citation_count=len(citations),
            search_queries=queries,
        )

        return {
            "answer": answer,
            "citations": citations,
            "queries": queries,
            "model": self.model,
        }

    def _grounding_request(self, query: str, temperature: float):
        """Single (non-retried) grounding call."""
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=temperature,
        )

        return self._client.models.generate_content(
            model=self.model,
            contents=query,
            config=gen_config,
        )

    # ------------------------------------------------------------------ #
    # URL Context (native Gemini — extract content from specific URLs)
    # ------------------------------------------------------------------ #
    def url_context(
        self,
        url: str,
        instruction: str = "Extract and return the main content of this page.",
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Extract content from a specific URL using Gemini's URL Context tool.

        Gemini fetches the URL and processes its content natively — useful as a
        fallback when Tavily extract fails or traditional BeautifulSoup scraping
        hits JS-rendered pages.

        Args:
            url: The URL to extract content from.
            instruction: What to do with the page content (default: extract main content).
            temperature: Low temperature for factual extraction (default 0.2).

        Returns:
            Dict with keys:
              - content: str   — extracted/processed text
              - url: str       — the source URL
              - model: str
        """
        logger.info("gemini_url_context_request", url=url, model=self.model)

        retrying = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

        response = retrying(self._url_context_request)(
            url=url, instruction=instruction, temperature=temperature
        )

        content = self._extract_text(response)

        logger.info("gemini_url_context_success", url=url, length=len(content))

        return {
            "content": content,
            "url": url,
            "model": self.model,
        }

    def _url_context_request(self, url: str, instruction: str, temperature: float):
        """Single (non-retried) URL context call."""
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            tools=[types.Tool(url_context=types.UrlContext())],
            temperature=temperature,
        )

        prompt = f"{instruction}\n\nURL: {url}"

        return self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=gen_config,
        )

    # ------------------------------------------------------------------ #
    # Vision (image analysis — OCR fallback for non-text images)
    # ------------------------------------------------------------------ #
    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Analyze an image with Gemini vision (OCR / description / extraction).

        Used as LLM-OCR fallback: RapidOCR handles text-dense images well, but
        for photos, diagrams, biology/scientific visuals Gemini vision extracts
        far more meaningful information.

        Args:
            image_bytes: Raw image bytes.
            mime_type: MIME type (image/png, image/jpeg, image/webp, image/gif).
            prompt: What to extract/analyze from the image.
            temperature: Low for factual extraction (default 0.1).

        Returns:
            Dict with keys:
              - content: str — Gemini's analysis of the image
              - model: str
        """
        from google.genai import types

        logger.info("gemini_vision_request", mime_type=mime_type, bytes=len(image_bytes))

        retrying = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

        def _vision_request():
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            gen_config = types.GenerateContentConfig(temperature=temperature)
            return self._client.models.generate_content(
                model=self.model,
                contents=[part, prompt],
                config=gen_config,
            )

        response = retrying(_vision_request)()
        content = self._extract_text(response)

        logger.info("gemini_vision_success", length=len(content))
        return {"content": content, "model": self.model}

    # ------------------------------------------------------------------ #
    # Code Execution (native Gemini — sandbox Python execution)
    # ------------------------------------------------------------------ #
    def code_execution(
        self,
        prompt: str,
        temperature: float = 0.4,
    ) -> Dict[str, Any]:
        """Run Python code in Gemini's sandbox to compute/analyze data.

        Gemini auto-writes and executes Python code in a secure Google sandbox.
        Useful for: calculations, CSV/data analysis, chart generation, data
        transformations — without needing a local Python execution environment.

        Args:
            prompt: Natural language description of what to compute/analyze.
                Can include data inline (e.g. CSV text, numbers).
            temperature: Slightly higher for code generation (default 0.4).

        Returns:
            Dict with keys:
              - answer: str          — final text answer / explanation
              - code: str            — the Python code Gemini wrote & executed
              - result: str          — execution output (stdout)
              - model: str
        """
        logger.info("gemini_code_execution_request", model=self.model)

        retrying = retry(
            stop=stop_after_attempt(config.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

        response = retrying(self._code_execution_request)(
            prompt=prompt, temperature=temperature
        )

        answer = self._extract_text(response)
        code, result = self._extract_code_parts(response)

        logger.info(
            "gemini_code_execution_success",
            code_length=len(code),
            result_length=len(result),
        )

        return {
            "answer": answer,
            "code": code,
            "result": result,
            "model": self.model,
        }

    def _code_execution_request(self, prompt: str, temperature: float):
        """Single (non-retried) code execution call."""
        from google.genai import types

        gen_config = types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution())],
            temperature=temperature,
        )

        return self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=gen_config,
        )

    @staticmethod
    def _extract_code_parts(response) -> tuple:
        """Extract executable code and execution result from Gemini response parts.

        Gemini code execution returns parts with:
          - executable_code: the Python code
          - code_execution_result: stdout output
        """
        code = ""
        result = ""
        try:
            parts = response.candidates[0].content.parts
            for part in parts:
                # executable_code attribute
                exec_code = getattr(part, "executable_code", None)
                if exec_code:
                    code += getattr(exec_code, "code", str(exec_code)) + "\n"
                # code_execution_result attribute
                exec_result = getattr(part, "code_execution_result", None)
                if exec_result:
                    result += getattr(exec_result, "output", str(exec_result)) + "\n"
        except Exception as e:
            logger.warning("gemini_extract_code_parts_failed", error=str(e))
        return code.strip(), result.strip()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _messages_to_contents(messages: List[Dict[str, str]]):
        """Convert OpenAI-style messages to Gemini contents format.

        Gemini uses "user" / "model" roles and accepts a list of Content parts.
        """
        from google.genai import types

        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Map OpenAI "assistant" → Gemini "model"
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=msg.get("content", ""))],
                )
            )
        return contents

    @staticmethod
    def _extract_text(response) -> str:
        """Extract text from Gemini response (handles blocked/empty cases)."""
        try:
            return response.text or ""
        except Exception:
            try:
                parts = response.candidates[0].content.parts
                return "".join(
                    p.text for p in parts if hasattr(p, "text") and p.text
                )
            except Exception:
                return ""

    @staticmethod
    def _extract_citations(response, max_citations: int) -> List[Dict[str, Any]]:
        """Extract grounding citation sources from response metadata."""
        citations: List[Dict[str, Any]] = []
        try:
            metadata = response.candidates[0].grounding_metadata
            chunks = getattr(metadata, "grounding_chunks", None) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if not web and isinstance(chunk, dict):
                    web = chunk.get("web", {})
                if not web:
                    continue

                url = (
                    getattr(web, "uri", None)
                    or (web.get("uri") if isinstance(web, dict) else "")
                )
                title = (
                    getattr(web, "title", None)
                    or (web.get("title") if isinstance(web, dict) else "")
                )
                if url:
                    citations.append({
                        "title": title or url,
                        "url": url,
                        "content": "",
                        "score": 0,
                    })
                if len(citations) >= max_citations:
                    break
        except Exception as e:
            logger.warning("gemini_extract_citations_failed", error=str(e))
        return citations

    @staticmethod
    def _extract_search_queries(response) -> List[str]:
        """Extract the actual Google Search queries Gemini used for grounding."""
        try:
            metadata = response.candidates[0].grounding_metadata
            queries = getattr(metadata, "web_search_queries", None) or []
            return list(queries)
        except Exception:
            return []

    @staticmethod
    def _extract_usage(response) -> Dict[str, Any]:
        """Extract token usage from Gemini response."""
        try:
            usage = response.usage_metadata
            return {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                "completion_tokens": getattr(usage, "candidates_token_count", 0),
                "total_tokens": getattr(usage, "total_token_count", 0),
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------ #
    # Convenience (mirrors OpenRouterClient.chat)
    # ------------------------------------------------------------------ #
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> str:
        """Simplified chat — returns just the content string."""
        response = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            **kwargs,
        )
        return response["choices"][0]["message"]["content"]


# ------------------------------------------------------------------ #
# Singleton (mirrors OpenRouterClient.get_openrouter_client pattern)
# ------------------------------------------------------------------ #
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> Optional[GeminiClient]:
    """Get or create the Gemini client singleton.

    Returns None if GEMINI_API_KEY is not configured — callers should
    fall back to OpenRouter / other search providers.
    """
    global _gemini_client
    if _gemini_client is None:
        if not config.GEMINI_API_KEY:
            logger.info("gemini_client_not_configured_no_api_key")
            return None
        try:
            _gemini_client = GeminiClient()
        except Exception as e:
            logger.error("gemini_client_init_failed", error=str(e))
            return None
    return _gemini_client
