"""Research Agent - finds and gathers information using tools."""

from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.prompt_templates.research_agent_prompt import get_research_prompt
from src.prompt_templates.output_models import ResearchOutput
from src.constants import AGENT_RESEARCH
from src.tools.base_tool import BaseTool


class ResearchAgent(BaseAgent):
    """Agent specialized in finding and gathering information."""
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize research agent."""
        super().__init__(AGENT_RESEARCH, tools=tools)
    
    def get_system_prompt(self) -> str:
        return get_research_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Research task using tool calling loop."""
        messages = self.format_messages(task, context)
        
        try:
            if self.tools:
                raw = self._process_with_tools(messages, max_iterations=6)
                result = self._parse_json_response(raw.get("content", "{}"))
            else:
                response = self._call_llm(messages, temperature=0.5, json_mode=True)
                result = self._parse_json_response(response)
            
            # Validate via Pydantic
            try:
                parsed = ResearchOutput(**result)
                if parsed.needs_more_search:
                    self.logger.warning(
                        "research_needs_more_search",
                        suggested=parsed.suggested_queries
                    )
                return {
                    "success": True,
                    "result": parsed.model_dump(),
                    "confidence": parsed.confidence
                }
            except Exception:
                return {
                    "success": True,
                    "result": result,
                    "confidence": result.get("confidence", 0.5)
                }
            
        except Exception as e:
            self.logger.error("research_failed", error=str(e))
            return {"success": False, "error": str(e), "confidence": 0.0}
