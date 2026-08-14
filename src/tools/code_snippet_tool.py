"""Code snippet tool — extract & format code blocks from text/HTML (free, no deps)."""

import re
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class CodeSnippetTool(BaseTool):
    """Extract code snippets from text, HTML, or markdown.

    Pure Python regex — no external dependencies, no API key.
    Detects fenced code blocks (```lang ... ```), indented blocks,
    and <pre><code> HTML blocks. Returns cleaned snippets with language.
    """

    def get_name(self) -> str:
        return "code_snippet"

    def get_description(self) -> str:
        return (
            "Extract code snippets from text, markdown, or HTML content. "
            "Free — no API key, pure regex. "
            "Input: content (text), language (optional filter, e.g. 'python'), max_snippets. "
            "Returns list of {language, code, line_count}. "
            "Use to pull code examples from scraped pages or research findings."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text / markdown / HTML to extract code from"},
                "language": {
                    "type": "string",
                    "default": "",
                    "description": "Filter by language (e.g. 'python'). Empty = all languages.",
                },
                "max_snippets": {"type": "integer", "default": 10, "description": "Max snippets to return"},
            },
            "required": ["content"],
        }

    def execute(
        self,
        content: str,
        language: str = "",
        max_snippets: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Extract code snippets from content."""
        try:
            snippets: List[Dict[str, Any]] = []

            # 1. Fenced code blocks: ```lang\n...\n```
            fence_pattern = r"```(\w*)\s*\n(.*?)```"
            for match in re.finditer(fence_pattern, content, re.DOTALL):
                lang = match.group(1).lower() or "text"
                code = match.group(2).strip()
                if language and lang != language.lower():
                    continue
                snippets.append({
                    "language": lang,
                    "code": code,
                    "line_count": code.count("\n") + 1,
                    "source": "fenced_block",
                })

            # 2. HTML <pre><code> blocks
            html_pattern = r"<pre[^>]*><code[^>]*>(.*?)</code></pre>"
            for match in re.finditer(html_pattern, content, re.DOTALL | re.IGNORECASE):
                code = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if not code:
                    continue
                snippets.append({
                    "language": "text",
                    "code": code,
                    "line_count": code.count("\n") + 1,
                    "source": "html_block",
                })

            # 3. <code> inline blocks (only if no fenced blocks found)
            if not snippets:
                inline_pattern = r"<code[^>]*>(.*?)</code>"
                for match in re.finditer(inline_pattern, content, re.DOTALL | re.IGNORECASE):
                    code = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                    if len(code) > 20:  # skip trivial inline code
                        snippets.append({
                            "language": "text",
                            "code": code,
                            "line_count": code.count("\n") + 1,
                            "source": "inline_code",
                        })

            # Filter by language if specified
            if language:
                snippets = [s for s in snippets if s["language"] == language.lower()]

            snippets = snippets[:max_snippets]

            logger.info("code_snippets_extracted", count=len(snippets), language=language)

            if not snippets:
                return ToolResult(
                    success=True,
                    result={"snippets": [], "message": "No code snippets found in the provided content."},
                    metadata={"language": language},
                )

            return ToolResult(
                success=True,
                result={"snippets": snippets, "count": len(snippets)},
                metadata={"language": language, "max_snippets": max_snippets},
            )
        except Exception as e:
            logger.error("code_snippet_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
