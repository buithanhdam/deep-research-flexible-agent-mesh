"""JSON processing tool."""

from typing import Dict, Any
import json
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


class JsonProcessorTool(BaseTool):
    """Process, validate, and transform JSON data."""
    
    def get_name(self) -> str:
        return "json_processor"
    
    def get_description(self) -> str:
        return """Process JSON data: parse, validate, extract fields, transform structure.
        
Operations: parse, validate, extract, pretty_print"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["parse", "validate", "extract", "pretty_print"],
                    "description": "Operation to perform"
                },
                "data": {
                    "type": "string",
                    "description": "JSON string or data"
                },
                "path": {
                    "type": "string",
                    "description": "JSON path for extract operation (e.g., 'user.name')"
                }
            },
            "required": ["operation", "data"]
        }
    
    def execute(self, operation: str, data: str, path: str = None) -> ToolResult:
        """Execute JSON operation.
        
        Args:
            operation: Operation type
            data: JSON data
            path: JSON path (for extract)
        
        Returns:
            ToolResult with processed data
        """
        try:
            if operation == "parse":
                parsed = json.loads(data)
                return ToolResult(
                    success=True,
                    result={"parsed": parsed, "type": type(parsed).__name__},
                    metadata={"keys": list(parsed.keys()) if isinstance(parsed, dict) else None}
                )
            
            elif operation == "validate":
                try:
                    json.loads(data)
                    return ToolResult(success=True, result={"valid": True, "message": "Valid JSON"})
                except json.JSONDecodeError as e:
                    return ToolResult(success=True, result={"valid": False, "error": str(e)})
            
            elif operation == "extract":
                if not path:
                    return ToolResult(success=False, error="Path required for extract operation")
                
                parsed = json.loads(data) if isinstance(data, str) else data
                
                # Navigate path
                parts = path.split('.')
                value = parsed
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif isinstance(value, list) and part.isdigit():
                        value = value[int(part)]
                    else:
                        return ToolResult(success=False, error=f"Path not found: {path}")
                
                return ToolResult(success=True, result={"extracted": value, "path": path})
            
            elif operation == "pretty_print":
                parsed = json.loads(data) if isinstance(data, str) else data
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                return ToolResult(success=True, result={"formatted": pretty})
            
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        
        except Exception as e:
            logger.error("json_processor_failed", operation=operation, error=str(e))
            return ToolResult(success=False, error=str(e))
