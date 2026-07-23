"""Google Drive upload tool."""

from typing import Dict, Any
import json
from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class GoogleDriveUploadTool(BaseTool):
    """Upload files to Google Drive."""
    
    def get_name(self) -> str:
        return "google_drive_upload"
    
    def get_description(self) -> str:
        return """Upload a file to Google Drive. Returns file ID and shareable link.
        
Input: file_path, filename (optional), folder_id (optional)"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local file path to upload"
                },
                "filename": {
                    "type": "string",
                    "description": "Filename in Drive (optional, uses original if not provided)"
                },
                "folder_id": {
                    "type": "string",
                    "description": "Google Drive folder ID (optional, uses config default)"
                }
            },
            "required": ["file_path"]
        }
    
    def execute(
        self,
        file_path: str,
        filename: str = None,
        folder_id: str = None
    ) -> ToolResult:
        """Upload file to Google Drive.
        
        Args:
            file_path: Local file path
            filename: Drive filename
            folder_id: Drive folder ID
        
        Returns:
            ToolResult with file ID and link
        """
        if not config.GOOGLE_DRIVE_ENABLED:
            return ToolResult(
                success=False,
                error="Google Drive not enabled. Set GOOGLE_DRIVE_ENABLED=true in .env"
            )
        
        # Validate file exists before attempting upload
        import os as _os
        if not _os.path.exists(file_path):
            return ToolResult(
                success=False,
                error=f"File not found: {file_path}. Ensure markdown_generator or pdf_generator ran successfully first."
            )
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            import os
            
            # Get credentials
            if config.GOOGLE_DRIVE_CREDENTIALS:
                # Inline JSON
                creds_data = json.loads(config.GOOGLE_DRIVE_CREDENTIALS)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=['https://www.googleapis.com/auth/drive.file']
                )
            elif config.GOOGLE_DRIVE_CREDENTIALS_JSON:
                # JSON file path
                credentials = service_account.Credentials.from_service_account_file(
                    config.GOOGLE_DRIVE_CREDENTIALS_JSON,
                    scopes=['https://www.googleapis.com/auth/drive.file']
                )
            else:
                return ToolResult(
                    success=False,
                    error="No Google Drive credentials configured"
                )
            
            # Build Drive service
            service = build('drive', 'v3', credentials=credentials)
            
            # Determine filename
            if not filename:
                filename = os.path.basename(file_path)
            
            # Prepare file metadata
            file_metadata = {'name': filename}
            
            # Add folder if specified
            target_folder = folder_id or config.GOOGLE_DRIVE_FOLDER_ID
            if target_folder:
                file_metadata['parents'] = [target_folder]
            
            # Upload file
            media = MediaFileUpload(file_path, resumable=True)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink'
            ).execute()
            
            # Make file publicly accessible (optional)
            try:
                service.permissions().create(
                    fileId=file['id'],
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
            except Exception as e:
                logger.warning("failed_to_make_public", error=str(e))
            
            logger.info("file_uploaded_to_drive", file_id=file['id'], name=filename)
            
            return ToolResult(
                success=True,
                result={
                    "file_id": file['id'],
                    "filename": file['name'],
                    "view_link": file.get('webViewLink'),
                    "download_link": file.get('webContentLink'),
                    "folder_id": target_folder
                },
                metadata={"service": "google_drive"}
            )
            
        except ImportError:
            error_msg = "Google API client not installed. Install: pip install google-auth google-auth-oauthlib google-api-python-client"
            logger.error("drive_upload_failed", error=error_msg)
            return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error("drive_upload_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
