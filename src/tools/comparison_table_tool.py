"""Comparison table tool — generate comparison tables from structured data (free, no deps)."""

import os
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class ComparisonTableTool(BaseTool):
    """Generate a comparison table (Markdown / HTML) from structured data.

    Pure Python, no external dependencies, no API key.
    Input: items (list of names), attributes (list of column names),
    rows (list of dicts mapping attribute → value per item).
    """

    def get_name(self) -> str:
        return "comparison_table"

    def get_description(self) -> str:
        return (
            "Generate a comparison table (Markdown or HTML) from structured data. "
            "Free, no API key. "
            "Input: items (row names), attributes (column names), "
            "data (dict: {item_name: {attribute: value}}). "
            "Returns markdown table string + optional saved file path."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Table title"},
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Row labels (items being compared)",
                },
                "attributes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column headers (attributes to compare)",
                },
                "data": {
                    "type": "object",
                    "description": "{item_name: {attribute: value}} mapping",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["markdown", "html"],
                    "default": "markdown",
                },
                "output_dir": {
                    "type": "string",
                    "default": "./output/tables",
                },
            },
            "required": ["title", "items", "attributes", "data"],
        }

    def execute(
        self,
        title: str,
        items: List[str],
        attributes: List[str],
        data: Dict[str, Dict[str, Any]],
        output_format: str = "markdown",
        output_dir: str = "./output/tables",
        **kwargs,
    ) -> ToolResult:
        """Generate a comparison table."""
        try:
            if output_format == "html":
                table_str = self._build_html(title, items, attributes, data)
                ext = "html"
            else:
                table_str = self._build_markdown(title, items, attributes, data)
                ext = "md"

            # Save to file
            os.makedirs(output_dir, exist_ok=True)
            safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:50]
            filename = f"{safe_title}_comparison.{ext}"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(table_str)

            file_size = os.path.getsize(filepath)
            logger.info("comparison_table_generated", format=output_format, filepath=filepath)

            return ToolResult(
                success=True,
                result={
                    "table": table_str,
                    "file_path": os.path.abspath(filepath),
                    "filename": filename,
                    "format": output_format,
                    "size_bytes": file_size,
                    "rows": len(items),
                    "cols": len(attributes),
                },
                metadata={"items": len(items), "attributes": len(attributes)},
            )
        except Exception as e:
            logger.error("comparison_table_failed", error=str(e))
            return ToolResult(success=False, error=str(e))

    @staticmethod
    def _build_markdown(
        title: str,
        items: List[str],
        attributes: List[str],
        data: Dict[str, Dict[str, Any]],
    ) -> str:
        lines = [f"## {title}\n"]
        # Header
        header = "| Item | " + " | ".join(attributes) + " |"
        separator = "|------|" + "|".join(["------" for _ in attributes]) + "|"
        lines.append(header)
        lines.append(separator)
        # Rows
        for item in items:
            row_data = data.get(item, {})
            cells = [str(row_data.get(attr, "—")) for attr in attributes]
            lines.append(f"| {item} | " + " | ".join(cells) + " |")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _build_html(
        title: str,
        items: List[str],
        attributes: List[str],
        data: Dict[str, Dict[str, Any]],
    ) -> str:
        html = [f"<h2>{title}</h2>", '<table border="1" cellpadding="6" style="border-collapse:collapse;">']
        # Header
        html.append("<tr><th>Item</th>" + "".join(f"<th>{a}</th>" for a in attributes) + "</tr>")
        # Rows
        for item in items:
            row_data = data.get(item, {})
            cells = "".join(f"<td>{row_data.get(attr, '—')}</td>" for attr in attributes)
            html.append(f"<tr><td><b>{item}</b></td>{cells}</tr>")
        html.append("</table>")
        return "\n".join(html)
