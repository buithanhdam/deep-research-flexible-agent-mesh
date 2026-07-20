"""Lark send message tool."""

from typing import Dict, Any
from src.tools.base_tool import BaseTool, ToolResult
from src.integrations.lark_client import get_lark_client
from src.logger import get_logger

logger = get_logger(__name__)


class LarkSendMessageTool(BaseTool):
    """Send message to Lark chat."""
    
    def get_name(self) -> str:
        return "lark_send_message"
    
    def get_description(self) -> str:
        return """Send a message to Lark (Feishu) chat or user.
        
Supports text messages and rich post messages with formatting."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "receive_id": {
                    "type": "string",
                    "description": "Receiver ID (chat_id or user_id)"
                },
                "message": {
                    "type": "string",
                    "description": "Message text"
                },
                "msg_type": {
                    "type": "string",
                    "enum": ["text", "post"],
                    "default": "text",
                    "description": "Message type"
                },
                "title": {
                    "type": "string",
                    "description": "Title for post messages (optional)"
                },
                "receive_id_type": {
                    "type": "string",
                    "enum": ["chat_id", "user_id", "email"],
                    "default": "chat_id"
                }
            },
            "required": ["receive_id", "message"]
        }
    
    def execute(
        self,
        receive_id: str,
        message: str,
        msg_type: str = "text",
        title: str = None,
        receive_id_type: str = "chat_id",
        **kwargs
    ) -> ToolResult:
        """Send message to Lark.
        
        Args:
            receive_id: Receiver ID
            message: Message text
            msg_type: Message type
            title: Title (for post)
            receive_id_type: ID type
        
        Returns:
            ToolResult
        """
        try:
            lark = get_lark_client()
            
            if msg_type == "text":
                result = lark.send_text(receive_id, message, receive_id_type)
            elif msg_type == "post":
                # Format as rich post
                content_blocks = [[{"tag": "text", "text": message}]]
                result = lark.send_post(
                    receive_id,
                    title or "Message",
                    content_blocks,
                    receive_id_type
                )
            else:
                return ToolResult(success=False, error=f"Unsupported msg_type: {msg_type}")
            
            return ToolResult(
                success=True,
                result={
                    "message_id": result.get("message_id"),
                    "sent_at": result.get("create_time"),
                    "receive_id": receive_id
                },
                metadata={"service": "lark"}
            )
            
        except Exception as e:
            logger.error("lark_send_message_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
