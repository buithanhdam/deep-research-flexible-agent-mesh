"""Lark (Feishu) API client."""

import json
from typing import Dict, Any, Optional
import requests
import time
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class LarkClient:
    """Client for Lark API using tenant access token."""
    
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None):
        """Initialize Lark client.
        
        Args:
            app_id: Lark App ID (defaults to config)
            app_secret: Lark App Secret (defaults to config)
        """
        self.app_id = app_id or config.LARK_APP_ID
        self.app_secret = app_secret or config.LARK_APP_SECRET
        self.base_url = "https://open.feishu.cn/open-apis"
        
        self._tenant_token = None
        self._token_expires_at = 0
    
    def _get_tenant_access_token(self) -> str:
        """Get tenant access token (cached).
        
        Returns:
            Tenant access token
        """
        # Return cached token if still valid
        if self._tenant_token and time.time() < self._token_expires_at:
            return self._tenant_token
        
        # Request new token
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") != 0:
                raise Exception(f"Lark API error: {data.get('msg')}")
            
            self._tenant_token = data["tenant_access_token"]
            # Token expires in ~2 hours, cache for 1.5 hours
            self._token_expires_at = time.time() + 5400
            
            logger.info("lark_token_refreshed")
            
            return self._tenant_token
            
        except Exception as e:
            logger.error("failed_to_get_lark_token", error=str(e))
            raise
    
    def send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: Dict[str, Any],
        receive_id_type: str = "chat_id"
    ) -> Dict[str, Any]:
        """Send message to Lark.
        
        Args:
            receive_id: Receiver ID (chat_id, user_id, email, etc.)
            msg_type: Message type (text, post, interactive, etc.)
            content: Message content dict
            receive_id_type: Type of receiver ID
        
        Returns:
            API response
        """
        token = self._get_tenant_access_token()
        
        url = f"{self.base_url}/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"receive_id_type": receive_id_type}
        
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content if isinstance(content, str) else json.dumps(content)
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") != 0:
                raise Exception(f"Lark API error: {data.get('msg')}")
            
            logger.info("lark_message_sent", receive_id=receive_id, msg_type=msg_type)
            
            return data.get("data", {})
            
        except Exception as e:
            logger.error("failed_to_send_lark_message", error=str(e))
            raise
    
    def send_text(self, receive_id: str, text: str, receive_id_type: str = "chat_id") -> Dict[str, Any]:
        """Send text message (simplified).
        
        Args:
            receive_id: Receiver ID
            text: Message text
            receive_id_type: ID type
        
        Returns:
            API response
        """
        content = {"text": text}
        return self.send_message(receive_id, "text", content, receive_id_type)
    
    def send_post(
        self,
        receive_id: str,
        title: str,
        content_blocks: list,
        receive_id_type: str = "chat_id"
    ) -> Dict[str, Any]:
        """Send rich text post message.
        
        Args:
            receive_id: Receiver ID
            title: Post title
            content_blocks: List of content blocks
            receive_id_type: ID type
        
        Returns:
            API response
        """
        import json
        
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content_blocks
            }
        }
        
        content = json.dumps({"post": post_content})
        return self.send_message(receive_id, "post", content, receive_id_type)
    
    def download_file(self, message_id: str, file_key: str, output_path: str, resource_type: str = "file") -> str:
        """Download file from Lark.
        
        Args:
            file_key: Lark file key
            output_path: Local output path
        
        Returns:
            Downloaded file path
        """
        token = self._get_tenant_access_token()
        url = f"{self.base_url}/im/v1/messages/{message_id}/resources/{file_key}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(url, headers=headers, params={"type": resource_type}, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info("lark_file_downloaded", file_key=file_key, path=output_path)
            
            return output_path
            
        except Exception as e:
            logger.error("failed_to_download_lark_file", error=str(e))
            raise
    
    def upload_file(self, file_path: str, file_type: str = "stream") -> Dict[str, Any]:
        """Upload file to Lark.
        
        Args:
            file_path: Local file path
            file_type: File type (stream, image, etc.)
        
        Returns:
            File key and URL
        """
        token = self._get_tenant_access_token()
        
        url = f"{self.base_url}/im/v1/files"
        headers = {"Authorization": f"Bearer {token}"}
        
        import os
        
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f)
            }
            data = {'file_type': file_type, 'file_name': os.path.basename(file_path)}
            
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30
                )
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("code") != 0:
                    raise Exception(f"Lark API error: {result.get('msg')}")
                
                file_key = result["data"]["file_key"]
                
                logger.info("lark_file_uploaded", file_key=file_key)
                
                return result["data"]
                
            except Exception as e:
                logger.error("failed_to_upload_lark_file", error=str(e))
                raise


# Singleton instance
_client: Optional[LarkClient] = None


def get_lark_client() -> LarkClient:
    """Get or create Lark client singleton."""
    global _client
    if _client is None:
        _client = LarkClient()
    return _client
