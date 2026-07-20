"""Lark file operations tool."""

from typing import Dict, Any
import os
import tempfile
from src.tools.base_tool import BaseTool, ToolResult
from src.integrations.lark_client import get_lark_client
from src.logger import get_logger

logger = get_logger(__name__)


class LarkFileDownloadTool(BaseTool):
    """Download file from Lark."""
    
    def get_name(self) -> str:
        return "lark_file_download"
    
    def get_description(self) -> str:
        return """Download a file from Lark by file key. Returns local file path."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "Lark file key"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (optional, generates temp if not provided)"
                }
            },
            "required": ["file_key"]
        }
    
    def execute(self, file_key: str, output_path: str = None, **kwargs) -> ToolResult:
        """Download file from Lark.
        
        Args:
            file_key: File key
            output_path: Output path
        
        Returns:
            ToolResult with file path
        """
        try:
            if not output_path:
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, f"lark_file_{file_key}")
            
            lark = get_lark_client()
            file_path = lark.download_file(file_key, output_path)
            
            file_size = os.path.getsize(file_path)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": file_path,
                    "file_key": file_key,
                    "file_size": file_size
                },
                metadata={"service": "lark"}
            )
            
        except Exception as e:
            logger.error("lark_file_download_failed", error=str(e))
            return ToolResult(success=False, error=str(e))


class LarkFileUploadTool(BaseTool):
    """Upload file to Lark."""
    
    def get_name(self) -> str:
        return "lark_file_upload"
    
    def get_description(self) -> str:
        return """Upload a local file to Lark. Returns file key for sharing."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local file path to upload"
                },
                "file_type": {
                    "type": "string",
                    "enum": ["stream", "image"],
                    "default": "stream",
                    "description": "File type"
                }
            },
            "required": ["file_path"]
        }
    
    def execute(self, file_path: str, file_type: str = "stream", **kwargs) -> ToolResult:
        """Upload file to Lark.
        
        Args:
            file_path: Local file path
            file_type: File type
        
        Returns:
            ToolResult with file key
        """
        try:
            lark = get_lark_client()
            result = lark.upload_file(file_path, file_type)
            
            return ToolResult(
                success=True,
                result={
                    "file_key": result["file_key"],
                    "file_name": os.path.basename(file_path)
                },
                metadata={"service": "lark"}
            )
            
        except Exception as e:
            logger.error("lark_file_upload_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
