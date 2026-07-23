"""Data Agent - processes and analyzes data."""

from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.constants import AGENT_DATA
from src.tools.base_tool import BaseTool
from src.prompt_templates.data_agent_prompt import get_data_prompt
from src.prompt_templates.output_models import DataOutput


class DataAgent(BaseAgent):
    """Agent specialized in data processing and analysis."""
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize data agent."""
        super().__init__(AGENT_DATA, tools=tools)
    
    def get_system_prompt(self) -> str:
        return get_data_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process data task with tool calling."""
        messages = self.format_messages(task, context)
        
        try:
            if self.tools:
                raw = self._process_with_tools(messages)
                result = self._parse_json_response(raw.get("content", "{}"))
            else:
                response = self._call_llm(messages, temperature=0.3, json_mode=True)
                result = self._parse_json_response(response)
            
            # Validate against schema
            try:
                parsed = DataOutput(**result)
                confidence = parsed.confidence
            except Exception:
                confidence = result.get("confidence", 0.7)
            
            return {
                "success": True,
                "result": result,
                "confidence": confidence
            }
            
        except Exception as e:
            self.logger.error("data_processing_failed", error=str(e))
            return {"success": False, "error": str(e), "confidence": 0.0}
