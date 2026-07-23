"""Prompt templates for agents."""

from src.prompt_templates.precheck_prompt import get_precheck_prompt
from src.prompt_templates.orchestrator_prompt import get_orchestrator_prompt
from src.prompt_templates.research_agent_prompt import get_research_prompt
from src.prompt_templates.data_agent_prompt import get_data_prompt
from src.prompt_templates.notification_agent_prompt import get_notification_prompt
from src.prompt_templates.architect_agent_prompt import get_architect_prompt

__all__ = [
    "get_precheck_prompt",
    "get_orchestrator_prompt",
    "get_research_prompt",
    "get_data_prompt",
    "get_notification_prompt",
    "get_architect_prompt",
]
