"""Research Agent - finds and gathers information."""

from typing import Dict, Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompt_templates import get_research_prompt
from src.constants import AGENT_RESEARCH


class ResearchAgent(BaseAgent):
    """Agent specialized in finding and gathering information."""
    
    def __init__(self):
        """Initialize research agent."""
        super().__init__(AGENT_RESEARCH)
    
    def get_system_prompt(self) -> str:
        """Get system prompt for research agent.
        
        Returns:
            System prompt string
        """
        return get_research_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process research task.
        
        Args:
            task: Research task description
            context: Additional context
        
        Returns:
            Dict with research results
        """
        messages = self.format_messages(task, context)
        
        try:
            # Call LLM for research
            response = self._call_llm(messages, temperature=0.5, json_mode=True)
            
            # Parse JSON response
            result = self._parse_json_response(response)
            
            # Extract key fields
            findings = result.get("findings", [])
            summary = result.get("summary", "")
            confidence = result.get("confidence", 0.5)
            sources = result.get("sources", [])
            
            # Check if sub-agent is recommended
            recommended_sub_agent = result.get("recommended_sub_agent")
            if recommended_sub_agent:
                self.logger.info(
                    "sub_agent_recommended",
                    sub_agent=recommended_sub_agent,
                    reason=result.get("reason", "")
                )
            
            return {
                "success": True,
                "result": {
                    "research_type": result.get("research_type", "general"),
                    "summary": summary,
                    "findings": findings,
                    "sources": sources,
                    "limitations": result.get("limitations", []),
                    "recommended_sub_agent": recommended_sub_agent
                },
                "confidence": confidence
            }
            
        except Exception as e:
            self.logger.error("research_failed", error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "confidence": 0.0
            }
