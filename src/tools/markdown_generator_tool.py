"""Markdown document generator."""

from typing import Dict, Any
from datetime import datetime
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class MarkdownGeneratorTool(BaseTool):
    """Generate structured Markdown documents."""
    
    def get_name(self) -> str:
        return "markdown_generator"
    
    def get_description(self) -> str:
        return """Generate well-structured Markdown documents with sections, tables, lists, code blocks.
        
Input: title, sections (list of {heading, content}), metadata"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Document title"
                },
                "sections": {
                    "type": "array",
                    "description": "List of sections with heading and content",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "content": {"type": "string"},
                            "level": {"type": "integer", "default": 2}
                        }
                    }
                },
                "metadata": {
                    "type": "object",
                    "description": "Document metadata (author, date, etc.)"
                }
            },
            "required": ["title", "sections"]
        }
    
    def execute(self, title: str, sections: list, metadata: dict = None) -> ToolResult:
        """Generate Markdown document.
        
        Args:
            title: Document title
            sections: List of section dicts
            metadata: Optional metadata
        
        Returns:
            ToolResult with markdown content
        """
        try:
            lines = []
            
            # Title
            lines.append(f"# {title}\n")
            
            # Metadata
            if metadata:
                for key, value in metadata.items():
                    lines.append(f"**{key.title()}**: {value}  ")
                lines.append("")
            
            # Add generation timestamp
            lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            lines.append("---\n")
            
            # Sections
            for section in sections:
                heading = section.get("heading", "")
                content = section.get("content", "")
                level = section.get("level", 2)
                
                # Add heading
                lines.append(f"{'#' * level} {heading}\n")
                
                # Add content
                lines.append(f"{content}\n")
            
            markdown = "\n".join(lines)
            
            return ToolResult(
                success=True,
                result={
                    "markdown": markdown,
                    "length": len(markdown),
                    "sections_count": len(sections)
                },
                metadata={
                    "title": title,
                    "format": "markdown"
                }
            )
            
        except Exception as e:
            logger.error("markdown_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
