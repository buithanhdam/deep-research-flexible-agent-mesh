"""Gemini Code Execution tool — runs Python in Google's secure sandbox.

Uses Gemini's native `code_execution` tool (`types.ToolCodeExecution`).
Gemini auto-writes and executes Python code in a secure Google sandbox —
useful for calculations, CSV/data analysis, data transformations, and
chart generation without needing a local Python execution environment.

This tool delegates to `GeminiClient.code_execution()` (src/llm/gemini_client.py),
keeping the google-genai SDK logic inside the LLM client layer.

Requires: `google-genai` SDK + `GEMINI_API_KEY` env var.
Falls back gracefully (returns ToolResult(success=False)) if not configured.
"""

from typing import Dict, Any, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.llm.gemini_client import get_gemini_client
from src.logger import get_logger

logger = get_logger(__name__)


class GeminiCodeExecutionTool(BaseTool):
    """Execute Python code in Gemini's secure sandbox.

    Gemini auto-writes and runs Python code to compute/analyze data.
    Best for: calculations, CSV analysis, data transformations, statistics.
    Returns: {answer, code, result, source: "gemini_code_execution"}.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(name, description, **kwargs)

    # ------------------------------------------------------------------ #
    # BaseTool interface
    # ------------------------------------------------------------------ #
    def get_name(self) -> str:
        return "gemini_code_execution"

    def get_description(self) -> str:
        return (
            "Execute Python code in Google's secure sandbox (via Gemini). "
            "Gemini auto-writes and runs code to compute, analyze data, "
            "do calculations, process CSV, generate statistics. "
            "Use this for: math, data analysis, transformations, statistics. "
            "Returns: {answer: str, code: str, result: str}."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Natural language description of what to compute/analyze. "
                        "Can include data inline (e.g. CSV text, numbers, lists)."
                    ),
                },
            },
            "required": ["prompt"],
        }

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute(self, prompt: str, **kwargs) -> ToolResult:
        """Execute code in Gemini's sandbox via GeminiClient.

        Args:
            prompt: Natural language description of what to compute/analyze.

        Returns:
            ToolResult with {answer, code, result, source}.
        """
        client = get_gemini_client()
        if client is None:
            logger.warning("gemini_code_execution_skipped_no_client")
            return ToolResult(
                success=False,
                error="GeminiClient not available — GEMINI_API_KEY not configured.",
            )

        try:
            executed = client.code_execution(prompt=prompt)

            answer = executed.get("answer", "")
            code = executed.get("code", "")
            result = executed.get("result", "")

            if not answer and not code and not result:
                logger.warning("gemini_code_execution_empty", prompt=prompt[:100])
                return ToolResult(
                    success=False,
                    error="Gemini returned no answer, code, or execution result.",
                )

            return ToolResult(
                success=True,
                result={
                    "answer": answer,
                    "code": code,
                    "result": result,
                    "source": "gemini_code_execution",
                },
                metadata={
                    "model": executed.get("model", ""),
                    "code_length": len(code),
                    "result_length": len(result),
                },
            )

        except Exception as e:
            logger.error("gemini_code_execution_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
