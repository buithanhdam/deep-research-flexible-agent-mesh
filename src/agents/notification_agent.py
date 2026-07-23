"""Notification Agent - prepares and sends Lark notifications."""

from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.constants import AGENT_NOTIFICATION
from src.tools.base_tool import BaseTool
from src.prompt_templates.notification_agent_prompt import get_notification_prompt
from src.prompt_templates.output_models import NotificationOutput


class NotificationAgent(BaseAgent):
    """Agent specialized in preparing and sending Lark notifications."""
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize notification agent."""
        super().__init__(AGENT_NOTIFICATION, tools=tools)
    
    def get_system_prompt(self) -> str:
        return get_notification_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare and send notification with tool calling."""
        messages = self.format_messages(task, context)
        
        try:
            if self.tools:
                raw = self._process_with_tools(messages)
                result = self._parse_json_response(raw.get("content", "{}"))
            else:
                response = self._call_llm(messages, temperature=0.3, json_mode=True)
                result = self._parse_json_response(response)
            
            try:
                parsed = NotificationOutput(**result)
                confidence = parsed.confidence
            except Exception:
                confidence = result.get("confidence", 0.9)
            
            return {"success": True, "result": result, "confidence": confidence}
            
        except Exception as e:
            self.logger.error("notification_prep_failed", error=str(e))
            return {"success": False, "error": str(e), "confidence": 0.0}
