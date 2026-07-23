"""File content extraction tool."""

from typing import Dict, Any
import os
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class FileExtractorTool(BaseTool):
    """Extract text content from various file types."""
    
    def get_name(self) -> str:
        return "file_extractor"
    
    def get_description(self) -> str:
        return """Extract text content from files (PDF, DOCX, TXT, MD, etc.). Returns text content."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to file"
                },
                "max_length": {
                    "type": "integer",
                    "default": 50000,
                    "description": "Maximum content length"
                }
            },
            "required": ["file_path"]
        }
    
    def execute(self, file_path: str, max_length: int = 50000, **kwargs) -> ToolResult:
        """Extract content from file.
        
        Args:
            file_path: File path
            max_length: Max content length
        
        Returns:
            ToolResult with extracted text
        """
        if not os.path.exists(file_path):
            return ToolResult(success=False, error=f"File not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext in ['.txt', '.md', '.json', '.yaml', '.yml', '.log']:
                content = self._extract_text_file(file_path)
            elif file_ext == '.pdf':
                content = self._extract_pdf(file_path)
            elif file_ext == '.docx':
                content = self._extract_docx(file_path)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unsupported file type: {file_ext}"
                )
            
            # Truncate if too long
            if len(content) > max_length:
                content = content[:max_length] + f"\n\n... (truncated, total: {len(content)} chars)"
            
            return ToolResult(
                success=True,
                result={
                    "content": content,
                    "file_path": file_path,
                    "file_type": file_ext,
                    "length": len(content)
                }
            )
            
        except Exception as e:
            logger.error("file_extraction_failed", path=file_path, error=str(e))
            return ToolResult(success=False, error=str(e))
    
    def _extract_text_file(self, path: str) -> str:
        """Extract from text file."""
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _extract_pdf(self, path: str) -> str:
        """Extract from PDF."""
        try:
            import pypdf
            
            text = []
            with open(path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
            
            return '\n\n'.join(text)
        except ImportError:
            raise ImportError("PyPDF2 not installed. Install: pip install PyPDF2")
    
    def _extract_docx(self, path: str) -> str:
        """Extract from DOCX."""
        try:
            from docx import Document
            
            doc = Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)
        except ImportError:
            raise ImportError("python-docx not installed. Install: pip install python-docx")
