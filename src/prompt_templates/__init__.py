"""Prompt templates for agents."""
from .orchestrator_prompt import get_orchestrator_prompt
from .precheck_prompt import get_precheck_prompt
from .research_agent_prompt import get_research_prompt



__all__ = ["get_orchestrator_prompt", "get_precheck_prompt", "get_research_prompt"]
# Templates are imported as needed
