"""Google Drive download tool."""

from typing import Dict, Any
import json
import os
import tempfile
from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class GoogleDriveDownloadTool(BaseTool):
    """Download file from Google Drive."""
    
    def get_name(self) -> str:
        return "google_drive_download"
    
    def get_description(self) -> str:
        return """Download a file from Google Drive by file ID. Returns local file path."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "Google Drive file ID"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (optional)"
                }
            },
            "required": ["file_id"]
        }
    
    def execute(self, file_id: str, output_path: str = None, **kwargs) -> ToolResult:
        """Download file from Drive.
        
        Args:
            file_id: Drive file ID
            output_path: Output path
        
        Returns:
            ToolResult with file path
        """
        if not config.GOOGLE_DRIVE_ENABLED:
            return ToolResult(
                success=False,
                error="Google Drive not enabled"
            )
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            # Get credentials
            if config.GOOGLE_DRIVE_CREDENTIALS:
                creds_data = json.loads(config.GOOGLE_DRIVE_CREDENTIALS)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
            elif config.GOOGLE_DRIVE_CREDENTIALS_JSON:
                credentials = service_account.Credentials.from_service_account_file(
                    config.GOOGLE_DRIVE_CREDENTIALS_JSON,
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
            else:
                return ToolResult(success=False, error="No credentials configured")
            
            service = build('drive', 'v3', credentials=credentials)
            
            # Get file metadata
            file_metadata = service.files().get(fileId=file_id, fields='name,mimeType,size').execute()
            filename = file_metadata['name']
            
            # Determine output path
            if not output_path:
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, filename)
            
            # Download file
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            file_size = os.path.getsize(output_path)
            
            logger.info("drive_file_downloaded", file_id=file_id, path=output_path)
            
            return ToolResult(
                success=True,
                result={
                    "file_path": output_path,
                    "file_id": file_id,
                    "filename": filename,
                    "file_size": file_size,
                    "mime_type": file_metadata.get('mimeType')
                },
                metadata={"service": "google_drive"}
            )
            
        except Exception as e:
            logger.error("drive_download_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
