"""Architect Agent - generates technical documents and deliverables."""

import json
from typing import Dict, Any, Optional, List
from src.agents.base_agent import BaseAgent
from src.constants import AGENT_ARCHITECT
from src.tools.base_tool import BaseTool
from src.prompt_templates.architect_agent_prompt import get_architect_prompt
from src.prompt_templates.output_models import ArchitectOutput
from src.logger import get_logger

logger = get_logger(__name__)


class ArchitectAgent(BaseAgent):
    """Agent specialized in generating technical documentation and deliverables."""
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize architect agent.
        
        Args:
            tools: List of tools available to this agent
        """
        super().__init__(AGENT_ARCHITECT)
        self.tools = tools or []
        self._tool_map = {tool.name: tool for tool in self.tools}
    
    def get_system_prompt(self) -> str:
        return get_architect_prompt(tool_names=[t.name for t in self.tools])
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate documents using tool calling loop."""
        messages = self._format_messages_with_tools(task, context)
        
        try:
            # Always use tool calling — architect is tool-driven
            raw = self._process_with_tools(messages, max_iterations=8)
            result = self._parse_json_response(raw.get("content", "{}"))
            
            try:
                parsed = ArchitectOutput(**result)
                confidence = parsed.confidence
            except Exception:
                confidence = result.get("confidence", 0.9)
            
            return {"success": True, "result": result, "confidence": confidence}
            
        except Exception as e:
            self.logger.error("architect_processing_failed", error=str(e))
            return {"success": False, "error": str(e), "confidence": 0.0}
    
    def _format_messages_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Format messages including context from previous agents."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add context from previous agents if available
        if context:
            workflow_id = context.get("workflow_id")
            if workflow_id:
                workflow_context = self.memory.get_all_context(workflow_id)
                if workflow_context:
                    context_str = f"## Previous Agent Results:\n{json.dumps(workflow_context, indent=2)}\n\n"
                    task = context_str + task
        
        messages.append({"role": "user", "content": task})
        
        return messages
