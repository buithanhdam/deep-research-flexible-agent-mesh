"""Precheck/Router Agent - filters chat vs research tasks."""

from typing import Dict, Any, Optional
import json

from src.agents.base_agent import BaseAgent
from src.prompt_templates.precheck_prompt import get_precheck_prompt
from src.prompt_templates.output_models import PrecheckOutput
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
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            raw = self._parse_json_response(response)
            
            # Validate via Pydantic
            parsed = PrecheckOutput(**raw)
            
            return {
                "success": True,
                "result": parsed.model_dump(),
                "confidence": 1.0 if not parsed.is_pass else 0.9
            }
            
        except Exception as e:
            self.logger.error("precheck_failed", error=str(e))
            # Fail-open: pass to orchestrator rather than dropping the task
            return {
                "success": True,
                "result": PrecheckOutput(
                    is_pass=True,
                    topic="unknown",
                    task_type="research",
                    response=""
                ).model_dump(),
                "confidence": 0.5,
                "error": str(e)
            }
