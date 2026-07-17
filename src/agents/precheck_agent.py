"""Precheck/Router Agent - filters chat vs research tasks."""

from typing import Dict, Any, Optional
import json

from src.agents.base_agent import BaseAgent
from src.prompt_templates import get_precheck_prompt
from src.constants import AGENT_PRECHECK


class PrecheckAgent(BaseAgent):
    """Agent that filters casual chat from actual research tasks."""
    
    def __init__(self):
        """Initialize precheck agent."""
        super().__init__(AGENT_PRECHECK)
    
    def get_system_prompt(self) -> str:
        """Get system prompt for precheck agent.
        
        Returns:
            System prompt string
        """
        return get_precheck_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process incoming message and classify it.
        
        Args:
            task: Incoming message
            context: Additional context
        
        Returns:
            Dict with classification result
        """
        messages = self.format_messages(task, context)
        
        try:
            # Request JSON response
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            
            # Parse JSON
            result = self._parse_json_response(response)
            
            # Validate required fields
            required_fields = ["is_pass", "topic", "task_type"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            return {
                "success": True,
                "result": result,
                "confidence": 1.0 if result.get("is_pass") is False else 0.9
            }
            
        except Exception as e:
            self.logger.error("precheck_failed", error=str(e))
            
            # Default to passing through as research on error
            return {
                "success": True,
                "result": {
                    "is_pass": True,
                    "topic": "unknown",
                    "task_type": "research",
                    "response": ""
                },
                "confidence": 0.5,
                "error": str(e)
            }
