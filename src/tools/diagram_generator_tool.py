"""Simple diagram generator using Graphviz."""

from typing import Dict, Any
import tempfile
import os
from datetime import datetime
from pathlib import Path
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class DiagramGeneratorTool(BaseTool):
    """Generate simple diagrams from DOT notation."""
    
    def get_name(self) -> str:
        return "diagram_generator"
    
    def get_description(self) -> str:
        return """Generate diagrams using Graphviz DOT notation. Supports flowcharts, graphs, etc.
        
Input: dot_code (Graphviz DOT syntax), output_format (png/svg/pdf), output_path"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dot_code": {
                    "type": "string",
                    "description": "Graphviz DOT notation code"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["png", "svg", "pdf"],
                    "default": "png",
                    "description": "Output format"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (optional)"
                }
            },
            "required": ["dot_code"]
        }
    
    def execute(
        self,
        dot_code: str,
        output_format: str = "png",
        output_path: str = None
    ) -> ToolResult:
        """Generate diagram.
        
        Args:
            dot_code: DOT notation
            output_format: Output format
            output_path: Output path
        
        Returns:
            ToolResult with diagram file path
        """
        try:
            import graphviz
            
            # Generate output path if not provided
            if not output_path:
                temp_dir = tempfile.gettempdir()
                filename = f"diagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                output_path = os.path.join(temp_dir, filename)
            else:
                # Remove extension if provided (graphviz adds it)
                output_path = os.path.splitext(output_path)[0]
            
            # Ensure directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create graph from DOT code
            src = graphviz.Source(dot_code)
            
            # Render diagram
            output_file = src.render(
                filename=output_path,
                format=output_format,
                cleanup=True
            )
            
            file_size = os.path.getsize(output_file)
            
            logger.info("diagram_generated", path=output_file, format=output_format)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": output_file,
                    "file_size": file_size,
                    "format": output_format
                },
                metadata={"engine": "graphviz"}
            )
            
        except ImportError:
            error_msg = "Graphviz not installed. Install: pip install graphviz (requires graphviz binary)"
            logger.error("diagram_generation_failed", error=error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error("diagram_generation_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
