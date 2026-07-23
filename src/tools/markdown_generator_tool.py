"""Markdown document generator."""

from typing import Dict, Any
from datetime import datetime
import os
import tempfile
from pathlib import Path
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class MarkdownGeneratorTool(BaseTool):
    """Save markdown content to a .md file on disk."""
    
    def get_name(self) -> str:
        return "markdown_generator"
    
    def get_description(self) -> str:
        return (
            "Save a Markdown document to disk and return the file path. "
            "Write the full markdown content yourself, then call this tool with "
            "title (for filename) and full_content (the complete markdown text). "
            "Do NOT use sections array — pass the entire document as a single string."
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Document title, used for filename (e.g. 'Python Best Practices')"
                },
                "full_content": {
                    "type": "string",
                    "description": (
                        "The complete Markdown document as a single string. "
                        "Include all headings, sections, bullet points, code blocks. "
                        "Use actual newline characters (\\n) in the string."
                    )
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional: explicit output .md file path"
                }
            },
            "required": ["title", "full_content"]
        }
    
    def execute(
        self,
        title: str,
        full_content: str,
        output_path: str = None,
        # Legacy support: sections-based input
        sections: list = None,
        metadata: dict = None,
        **kwargs
    ) -> ToolResult:
        """Save Markdown content to disk.
        
        Accepts either:
          - full_content (preferred): complete markdown string
          - sections (legacy): list of {heading, content} dicts
        
        Returns:
            ToolResult with file_path
        """
        try:
            # Build content
            if full_content:
                markdown = full_content
                # Prepend timestamp header if not already present
                if not markdown.strip().startswith("#"):
                    markdown = f"# {title}\n\n" + markdown
            elif sections:
                # Legacy path
                lines = [f"# {title}\n"]
                if metadata:
                    for k, v in metadata.items():
                        lines.append(f"**{k.title()}**: {v}  ")
                    lines.append("")
                lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
                lines.append("---\n")
                for section in sections:
                    heading = section.get("heading", "")
                    content = section.get("content", "")
                    level = section.get("level", 2)
                    lines.append(f"{'#' * level} {heading}\n")
                    lines.append(f"{content}\n")
                markdown = "\n".join(lines)
            else:
                return ToolResult(success=False, error="Must provide 'full_content' or 'sections'")
            
            # Generate output path
            if not output_path:
                safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
                safe = safe.strip().replace(" ", "_")[:60]
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(tempfile.gettempdir(), f"{safe}_{ts}.md")
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            
            file_size = os.path.getsize(output_path)
            logger.info("markdown_saved", path=output_path, size=file_size)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": output_path,
                    "length": len(markdown),
                },
                metadata={"title": title, "format": "markdown", "file_size": file_size}
            )
            
        except Exception as e:
            logger.error("markdown_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
