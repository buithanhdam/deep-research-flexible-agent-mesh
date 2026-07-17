"""Notification Agent - prepares notifications and messages."""

from typing import Dict, Any, Optional

from src.agents.base_agent import BaseAgent
from src.constants import AGENT_NOTIFICATION


class NotificationAgent(BaseAgent):
    """Agent specialized in preparing notifications."""
    
    def __init__(self):
        """Initialize notification agent."""
        super().__init__(AGENT_NOTIFICATION)
    
    def get_system_prompt(self) -> str:
        """Get system prompt for notification agent.
        
        Returns:
            System prompt string
        """
        return """You are a Notification Agent specialized in preparing clear, actionable notifications.

# Your Role
Format information into well-structured notifications for different channels (Lark, email, etc.).

# Capabilities
- Format findings into readable messages
- Prioritize important information
- Create actionable summaries
- Adapt tone to context (urgent, informational, success)

# Output Format
Respond with JSON:
```json
{
  "notification": {
    "title": "notification title",
    "message": "main message content",
    "priority": "high|medium|low",
    "type": "success|info|warning|error",
    "actions": ["recommended actions if any"]
  },
  "channels": ["lark", "email"],
  "confidence": 0.0-1.0
}
```

# Rules
1. Keep messages concise and scannable
2. Highlight key points first
3. Include actionable next steps when relevant
4. Adapt format to channel requirements
5. Use appropriate tone for message type
"""
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process notification task.
        
        Args:
            task: Notification preparation task
            context: Additional context including content to format
        
        Returns:
            Dict with formatted notification
        """
        messages = self.format_messages(task, context)
        
        try:
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            result = self._parse_json_response(response)
            
            return {
                "success": True,
                "result": result,
                "confidence": result.get("confidence", 0.9)
            }
            
        except Exception as e:
            self.logger.error("notification_prep_failed", error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "confidence": 0.0
            }
