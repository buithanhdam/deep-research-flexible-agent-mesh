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
        import traceback as _tb
        messages = self.format_messages(task, context)
        
        try:
            if self.tools:
                # Tier-aware: fewer tool iterations for quick research
                task_tier = (context or {}).get("task_tier", "")
                max_iter = 3 if task_tier == "quick_research" else 6
                raw = self._process_with_tools(messages, max_iterations=max_iter)
                content = raw.get("content", "")
                
                # Nếu tools loop kết thúc nhưng content rỗng, yêu cầu LLM tổng hợp
                if not content or raw.get("stopped") == "max_iterations":
                    self.logger.warning("tools_loop_ended_without_output", agent=self.name)
                    content = self._request_final_summary(messages)
                
                result = self._parse_json_response(content)
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
            except Exception as pydantic_err:
                self.logger.warning("pydantic_validation_skipped", error=str(pydantic_err))
                return {
                    "success": True,
                    "result": result,
                    "confidence": result.get("confidence", 0.5)
                }
            
        except Exception as e:
            self.logger.error("research_failed", error=str(e), traceback=_tb.format_exc())
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "confidence": 0.0
            }
    
    def _request_final_summary(self, original_messages: list) -> str:
        """Khi tool loop xong nhưng chưa có JSON output, yêu cầu LLM tổng hợp."""
        summary_messages = original_messages + [{
            "role": "user",
            "content": (
                "Based on all the research you have done so far, "
                "please now output your final answer as a JSON object "
                "matching the required schema. Do not call any more tools."
            )
        }]
        return self._call_llm(summary_messages, temperature=0.3, json_mode=True)
