"""Orchestrator Agent - coordinates multiple specialized agents."""

from typing import Dict, Any, Optional, List
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.agents.base_agent import BaseAgent
from src.prompt_templates import get_orchestrator_prompt
from src.constants import AGENT_ORCHESTRATOR, CONFIDENCE_HIGH


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
        """Process task by coordinating multiple agents.
        
        Args:
            task: Task description
            context: Additional context
        
        Returns:
            Dict with orchestration result
        """
        workflow_id = context.get("workflow_id") if context else None
        
        # Step 1: Analyze and decompose task
        decomposition = self._decompose_task(task, context)
        
        if not decomposition.get("success"):
            return decomposition
        
        sub_tasks = decomposition.get("sub_tasks", [])
        
        if not sub_tasks:
            return {
                "success": False,
                "error": "No sub-tasks generated",
                "confidence": 0.0
            }
        
        # Step 2: Execute sub-tasks (parallel where possible)
        results = self._execute_sub_tasks(sub_tasks, workflow_id, context)
        
        # Step 3: Synthesize results
        synthesis = self._synthesize_results(task, results, context)
        
        return synthesis
    
    def _decompose_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Decompose task into sub-tasks.
        
        Args:
            task: Task description
            context: Additional context
        
        Returns:
            Dict with sub_tasks list
        """
        prompt = f"""Analyze this task and create a decomposition plan:

Task: {task}

Respond with JSON in this format:
{{
  "task_type": "research|data|integration|build",
  "sub_tasks": [
    {{
      "agent": "research|data|notification",
      "task": "specific task description",
      "priority": "high|medium|low"
    }}
  ]
}}
"""
        
        messages = self.format_messages(prompt, context)
        
        try:
            response = self._call_llm(messages, temperature=0.5, json_mode=True)
            result = self._parse_json_response(response)
            
            return {
                "success": True,
                "sub_tasks": result.get("sub_tasks", []),
                "task_type": result.get("task_type", "unknown")
            }
            
        except Exception as e:
            self.logger.error("decomposition_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "sub_tasks": []
            }
    
    def _execute_sub_tasks(
        self,
        sub_tasks: List[Dict[str, Any]],
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute sub-tasks using registered agents with shared context.
        
        Args:
            sub_tasks: List of sub-task dicts
            workflow_id: Optional workflow ID
            context: Shared context from parent
        
        Returns:
            List of results
        """
        results = []
        
        # Simple sequential execution for MVP
        # TODO: Implement parallel execution for independent tasks
        for i, sub_task in enumerate(sub_tasks):
            agent_name = sub_task.get("agent")
            task_desc = sub_task.get("task")
            
            if agent_name not in self._agent_registry:
                self.logger.warning("agent_not_found", agent=agent_name)
                results.append({
                    "agent": agent_name,
                    "success": False,
                    "error": f"Agent '{agent_name}' not registered"
                })
                continue
            
            agent = self._agent_registry[agent_name]
            
            # Build context for sub-agent
            sub_context = {
                "priority": sub_task.get("priority", "medium"),
                "sub_task_index": i,
                "total_sub_tasks": len(sub_tasks)
            }
            
            # Inherit session_id from parent if exists
            if context and "session_id" in context:
                sub_context["session_id"] = context["session_id"]
            
            # Share previous results via working memory
            if workflow_id and results:
                # Store previous results in working memory
                self.memory.set_context(
                    workflow_id,
                    f"previous_results_{i}",
                    results
                )
                sub_context["previous_results_available"] = True
            
            try:
                result = agent.execute(
                    task=task_desc,
                    workflow_id=workflow_id,
                    context=sub_context
                )
                
                # Store this result in working memory for next agent
                if workflow_id:
                    self.memory.set_context(
                        workflow_id,
                        f"{agent_name}_result",
                        result
                    )
                
                results.append({
                    "agent": agent_name,
                    "task": task_desc,
                    **result
                })
                
            except Exception as e:
                self.logger.error(
                    "sub_task_failed",
                    agent=agent_name,
                    error=str(e)
                )
                results.append({
                    "agent": agent_name,
                    "task": task_desc,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def _synthesize_results(
        self,
        original_task: str,
        results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synthesize results from multiple agents.
        
        Args:
            original_task: Original task description
            results: List of agent results
            context: Additional context
        
        Returns:
            Final synthesized result
        """
        # Calculate overall confidence
        confidences = [r.get("confidence", 0.0) for r in results if r.get("success")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Check if all sub-tasks succeeded
        all_success = all(r.get("success", False) for r in results)
        
        # Prepare synthesis prompt
        results_summary = json.dumps(results, indent=2)
        
        prompt = f"""Synthesize the results from multiple agents into a final response.

Original Task: {original_task}

Agent Results:
{results_summary}

Provide a JSON response with:
{{
  "action": "return|escalate",
  "confidence": 0.0-1.0,
  "reason": "explanation of decision",
  "summary": "brief summary of findings",
  "details": "comprehensive details",
  "sources": ["list of sources"],
  "next_steps": ["recommended actions if any"]
}}

Rules:
- If confidence < 0.7 or critical info missing: action = "escalate"
- Otherwise: action = "return"
- Be honest about limitations
"""
        
        messages = self.format_messages(prompt, context)
        
        try:
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            synthesis = self._parse_json_response(response)
            
            return {
                "success": all_success,
                "action": synthesis.get("action", "escalate"),
                "confidence": synthesis.get("confidence", avg_confidence),
                "result": {
                    "summary": synthesis.get("summary", ""),
                    "details": synthesis.get("details", ""),
                    "sources": synthesis.get("sources", []),
                    "next_steps": synthesis.get("next_steps", [])
                },
                "reason": synthesis.get("reason", ""),
                "agent_results": results
            }
            
        except Exception as e:
            self.logger.error("synthesis_failed", error=str(e))
            
            # Return safe fallback
            return {
                "success": False,
                "action": "escalate",
                "confidence": 0.0,
                "error": str(e),
                "agent_results": results
            }
