"""DOCX generation tool."""

from typing import Dict, Any
import tempfile
import os
from pathlib import Path
from datetime import datetime
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class DocxGeneratorTool(BaseTool):
    """Generate DOCX documents from Markdown."""
    
    def get_name(self) -> str:
        return "docx_generator"
    
    def get_description(self) -> str:
        return """Convert Markdown to DOCX (Microsoft Word) document. Returns file path.
        
Input: content (markdown), output_path (optional), title"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Markdown content string (use this OR markdown_file_path)"
                },
                "markdown_file_path": {
                    "type": "string",
                    "description": "Path to existing .md file (use this OR content)"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output DOCX file path (optional)"
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
        output_path: str = None,
        title: str = "Document",
        **kwargs
    ) -> ToolResult:
        """Generate DOCX from content string or markdown file.
        
        Args:
            content: Markdown content string
            markdown_file_path: Path to existing .md file
            output_path: Output DOCX path
            title: Document title
        
        Returns:
            ToolResult with file path
        """
        if not content and not markdown_file_path:
            return ToolResult(success=False, error="Must provide either 'content' or 'markdown_file_path'")
        
        try:
            import pypandoc
            
            # Load from file if provided
            if markdown_file_path:
                if not os.path.exists(markdown_file_path):
                    return ToolResult(
                        success=False,
                        error=f"Markdown file not found: {markdown_file_path}"
                    )
                # Derive output path alongside md file
                if not output_path:
                    output_path = os.path.splitext(markdown_file_path)[0] + ".docx"
            
            if not output_path:
                filename = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                output_path = os.path.join(tempfile.gettempdir(), filename)
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Convert: prefer file input to avoid large string args
            if markdown_file_path:
                pypandoc.convert_file(
                    markdown_file_path,
                    'docx',
                    outputfile=output_path,
                    extra_args=[f'--metadata=title:{title}', '--standalone']
                )
            else:
                pypandoc.convert_text(
                    content,
                    'docx',
                    format='md',
                    outputfile=output_path,
                    extra_args=[f'--metadata=title:{title}', '--standalone']
                )
            
            file_size = os.path.getsize(output_path)
            logger.info("docx_generated", path=output_path, size=file_size)
            
            return ToolResult(
                success=True,
                result={"file_path": output_path, "file_size": file_size, "title": title},
                metadata={"format": "docx"}
            )
            
        except ImportError:
            error_msg = "pypandoc not installed: pip install pypandoc (requires pandoc binary)"
            logger.error("docx_generation_failed", error=error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error("docx_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
