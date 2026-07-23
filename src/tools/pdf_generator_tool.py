"""PDF generation tool using WeasyPrint."""

from datetime import datetime
from typing import Dict, Any
import tempfile
import os
from pathlib import Path
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class PDFGeneratorTool(BaseTool):
    """Generate PDF from Markdown or HTML content."""
    
    def get_name(self) -> str:
        return "pdf_generator"
    
    def get_description(self) -> str:
        return """Convert Markdown or HTML to PDF document. Returns file path.
        
Input: content (markdown/html), output_path (optional), css_style (optional)"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Markdown or HTML content string (use this OR markdown_file_path)"
                },
                "markdown_file_path": {
                    "type": "string",
                    "description": "Path to an existing .md file to convert (use this OR content)"
                },
                "content_type": {
                    "type": "string",
                    "enum": ["markdown", "html"],
                    "default": "markdown",
                    "description": "Type of input content"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output PDF file path (optional, auto-generates if not provided)"
                },
                "title": {
                    "type": "string",
                    "description": "Document title"
                }
            },
            "required": []
        }
    
    def execute(
        self,
        content: str = None,
        markdown_file_path: str = None,
        content_type: str = "markdown",
        output_path: str = None,
        title: str = "Document",
        **kwargs
    ) -> ToolResult:
        """Generate PDF from content string or markdown file.
        
        Args:
            content: Markdown or HTML string
            markdown_file_path: Path to existing .md file (alternative to content)
            content_type: 'markdown' or 'html'
            output_path: Output PDF path
            title: Document title
        
        Returns:
            ToolResult with PDF file path
        """
        # Validate inputs
        if not content and not markdown_file_path:
            return ToolResult(success=False, error="Must provide either 'content' or 'markdown_file_path'")
        
        try:
            from weasyprint import HTML
            import markdown
            
            # Load from file if path provided
            if markdown_file_path:
                if not os.path.exists(markdown_file_path):
                    return ToolResult(
                        success=False,
                        error=f"Markdown file not found: {markdown_file_path}"
                    )
                with open(markdown_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content_type = "markdown"
                # Derive title from filename if not provided
                if title == "Document":
                    title = os.path.splitext(os.path.basename(markdown_file_path))[0].replace("_", " ")
            
            # Convert markdown to HTML if needed
            if content_type == "markdown":
                html_content = markdown.markdown(
                    content,
                    extensions=['tables', 'fenced_code', 'nl2br']
                )
            else:
                html_content = content
            
            full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
            margin-top: 30px;
        }}
        h3 {{
            color: #555;
            margin-top: 20px;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 20px;
            margin-left: 0;
            color: #666;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
            """
            
            # Derive output path from markdown file path when possible
            if not output_path:
                if markdown_file_path:
                    output_path = os.path.splitext(markdown_file_path)[0] + ".pdf"
                else:
                    filename = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    output_path = os.path.join(tempfile.gettempdir(), filename)
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            HTML(string=full_html).write_pdf(output_path)
            
            file_size = os.path.getsize(output_path)
            logger.info("pdf_generated", path=output_path, size=file_size)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": output_path,
                    "file_size": file_size,
                    "title": title
                },
                metadata={"format": "pdf", "content_type": content_type}
            )
            
        except ImportError:
            error_msg = "WeasyPrint not installed: pip install weasyprint markdown"
            logger.error("pdf_generation_failed", error=error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error("pdf_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
