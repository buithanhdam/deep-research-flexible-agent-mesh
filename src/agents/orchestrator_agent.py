"""Orchestrator Agent - coordinates multiple specialized agents."""

from typing import Dict, Any, Optional, List
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.agents.base_agent import BaseAgent
from src.prompt_templates.orchestrator_prompt import get_orchestrator_prompt
from src.prompt_templates.output_models import OrchestratorDecision, OrchestratorFinalOutput
from src.constants import AGENT_ORCHESTRATOR, CONFIDENCE_HIGH
from src.config import config

class OrchestratorAgent(BaseAgent):
    """Agent that coordinates other agents to complete complex tasks."""
    
    def __init__(self):
        """Initialize orchestrator agent."""
        super().__init__(AGENT_ORCHESTRATOR)
        self._agent_registry: Dict[str, BaseAgent] = {}
    
    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """Register an agent for delegation.
        
        Args:
            name: Agent name/identifier
            agent: Agent instance
        """
        self._agent_registry[name] = agent
        self.logger.info("agent_registered", agent_name=name)
    
    def get_system_prompt(self) -> str:
        """Get system prompt for orchestrator.
        
        Returns:
            System prompt string
        """
        return get_orchestrator_prompt()
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process task with multi-round orchestration.
        
        Args:
            task: Task description
            context: Additional context
        
        Returns:
            Dict with orchestration result
        """
        workflow_id = context.get("workflow_id") if context else None
        max_rounds = config.AGENT_LOOP_MAX_ROUNDS  # Prevent infinite loops
        all_results = []
        
        for round_num in range(max_rounds):
            self.logger.info("orchestration_round", round=round_num + 1, max=max_rounds)
            
            # Step 1: Decide next action based on current state
            decision = self._decide_next_action(task, all_results, context)
            
            if not decision.get("success"):
                return decision
            
            action = decision.get("action")
            
            # If complete, finalize
            if action == "complete":
                self.logger.info("task_complete", round=round_num + 1)
                return self._finalize_results(task, all_results, context)
            
            # If escalate, return for human review
            if action == "escalate":
                self.logger.info("task_escalated", round=round_num + 1)
                return {
                    "success": False,
                    "action": "escalate",
                    "reason": decision.get("reason", "Task too complex"),
                    "confidence": decision.get("confidence", 0.0),
                    "partial_results": all_results
                }
            
            # Otherwise, execute next agent
            next_agent = decision.get("next_agent")
            next_task = decision.get("next_task")
            
            if not next_agent or next_agent not in self._agent_registry:
                self.logger.error("invalid_next_agent", agent=next_agent)
                break
            
            # Execute agent
            agent_result = self._execute_agent(
                next_agent,
                next_task,
                workflow_id,
                context
            )
            
            all_results.append({
                "round": round_num + 1,
                "agent": next_agent,
                "task": next_task,
                **agent_result
            })
            
            # Store in working memory
            if workflow_id:
                self.memory.set_context(
                    workflow_id,
                    f"round_{round_num}_result",
                    agent_result
                )
        
        # Max rounds reached
        self.logger.warning("max_rounds_reached")
        return self._finalize_results(task, all_results, context)
    
    def _decide_next_action(
        self,
        original_task: str,
        current_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Decide next action based on current state.
        
        Args:
            original_task: Original task
            current_results: Results so far
            context: Additional context
        
        Returns:
            Decision dict with action and next steps
        """
        results_summary = json.dumps(current_results, indent=2) if current_results else "No results yet"
        
        prompt = f"""You are orchestrating a multi-agent workflow. Decide the next action.

Original Task: {original_task}

Current Results:
{results_summary}

Available Agents:
- research: Find information, search web, gather data
- data: Process and analyze data
- notification: Format messages and notifications

Respond with JSON:
{{
  "action": "execute_agent|complete|escalate",
  "next_agent": "research|data|notification" (if action=execute_agent),
  "next_task": "specific task for that agent" (if action=execute_agent),
  "reason": "why this decision",
  "confidence": 0.0-1.0,
  "assessment": {{
    "is_complete": true|false,
    "missing_info": ["what's still needed"],
    "quality": "high|medium|low"
  }}
}}

Rules:
- If no results yet: execute_agent to start
- If results are sufficient and high quality: complete
- If results are low confidence or missing critical info: execute_agent or escalate
- If stuck or too complex: escalate
"""
        
        messages = self.format_messages(prompt, context)
        
        try:
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            raw = self._parse_json_response(response)
            
            try:
                parsed = OrchestratorDecision(**raw)
                return {"success": True, **parsed.model_dump()}
            except Exception:
                # Pydantic validation failed, return raw dict
                return {"success": True, **raw}
            
        except Exception as e:
            self.logger.error("decision_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    def _execute_agent(
        self,
        agent_name: str,
        task: str,
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute single agent."""
        import traceback as _tb
        
        agent = self._agent_registry[agent_name]
        
        agent_context = {}
        if context and "session_id" in context:
            agent_context["session_id"] = context["session_id"]
        
        try:
            result = agent.execute(
                task=task,
                workflow_id=workflow_id,
                context=agent_context
            )
            
            # Log nếu agent trả về failure
            if not result.get("success"):
                self.logger.warning(
                    "sub_agent_returned_failure",
                    agent=agent_name,
                    error=result.get("error"),
                    error_type=result.get("error_type"),
                )
            
            if workflow_id:
                self.memory.set_context(workflow_id, f"{agent_name}_last_result", result)
            
            return result
            
        except Exception as e:
            full_tb = _tb.format_exc()
            self.logger.error(
                "agent_execution_exception",
                agent=agent_name,
                error=str(e),
                traceback=full_tb
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": full_tb,
                "agent": agent_name,
                "confidence": 0.0
            }
    
    def _finalize_results(
        self,
        original_task: str,
        all_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Finalize and synthesize all results.
        
        Args:
            original_task: Original task
            all_results: All agent results from all rounds
            context: Context
        
        Returns:
            Final result
        """
        results_summary = json.dumps(all_results, indent=2)
        
        prompt = f"""Synthesize final results from multi-round orchestration.

Original Task: {original_task}

All Agent Results (chronological):
{results_summary}

Provide JSON:
{{
  "summary": "brief summary",
  "details": "comprehensive details",
  "sources": ["sources"],
  "confidence": 0.0-1.0,
  "completeness": "complete|partial|insufficient",
  "recommendations": ["next steps or recommendations"]
}}
"""
        
        messages = self.format_messages(prompt, context)
        
        try:
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            raw = self._parse_json_response(response)
            
            try:
                parsed = OrchestratorFinalOutput(**raw)
                result_dict = parsed.model_dump()
            except Exception:
                result_dict = raw
            
            successful_rounds = [r for r in all_results if r.get("success")]
            success_rate = len(successful_rounds) / len(all_results) if all_results else 0.0
            
            return {
                "success": success_rate > 0.5,
                "action": "return",
                "confidence": result_dict.get("confidence", 0.7),
                "result": result_dict,
                "completeness": result_dict.get("completeness", "partial"),
                "agent_results": all_results,
                "rounds_executed": len(all_results)
            }
            
        except Exception as e:
            import traceback as _tb
            full_tb = _tb.format_exc()
            self.logger.error("finalization_failed", error=str(e), traceback=full_tb)
            return {
                "success": False,
                "action": "escalate",
                "confidence": 0.0,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": full_tb,
                "agent": self.name,
                "agent_results": all_results
            }
