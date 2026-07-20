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
                    "description": "Markdown content"
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
            "required": ["content"]
        }
    
    def execute(
        self,
        content: str,
        output_path: str = None,
        title: str = "Document"
    ) -> ToolResult:
        """Generate DOCX.
        
        Args:
            content: Markdown content
            output_path: Output file path
            title: Document title
        
        Returns:
            ToolResult with file path
        """
        try:
            import pypandoc
            
            # Generate output path if not provided
            if not output_path:
                temp_dir = tempfile.gettempdir()
                filename = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                output_path = os.path.join(temp_dir, filename)
            
            # Ensure directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Convert markdown to docx using pandoc
            pypandoc.convert_text(
                content,
                'docx',
                format='md',
                outputfile=output_path,
                extra_args=[
                    f'--metadata=title:{title}',
                    '--standalone'
                ]
            )
            
            file_size = os.path.getsize(output_path)
            
            logger.info("docx_generated", path=output_path, size=file_size)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": output_path,
                    "file_size": file_size,
                    "title": title
                },
                metadata={"format": "docx"}
            )
            
        except ImportError:
            error_msg = "pypandoc not installed. Install: pip install pypandoc (requires pandoc)"
            logger.error("docx_generation_failed", error=error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error("docx_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
