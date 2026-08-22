"""Base agent class for all agents in the system."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from src.llm.openrouter_client import get_openrouter_client
from src.memory.memory_manager import get_memory_manager
from src.memory.models import AgentExecution
from src.logger import get_logger
from src.constants import CONFIDENCE_MEDIUM
from src.config import config
from src.tools.base_tool import BaseTool

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str, tools: Optional[List[BaseTool]] = None):
        """Initialize base agent.
        
        Args:
            name: Agent name/identifier
            tools: List of tools available to this agent
        """
        self.name = name
        self.llm = get_openrouter_client()
        self.memory = get_memory_manager()
        self.logger = get_logger(f"agent.{name}")
        self.tools = tools or []
        self._tool_map = {tool.name: tool for tool in self.tools}
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.
        
        Returns:
            System prompt string
        """
        pass
    
    @abstractmethod
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a task assigned to this agent.
        
        Args:
            task: Task description
            context: Additional context
        
        Returns:
            Result dict with at least 'success', 'result', 'confidence'
        """
        pass
    
    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        json_mode: bool = False,
        tools: Optional[List[Dict]] = None
    ) -> str:
        """Call LLM with messages and optional tools.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            json_mode: Whether to request JSON response
            tools: Tool definitions for function calling
        
        Returns:
            LLM response content
        """
        try:
            if tools:
                # Use function calling
                response = self.llm.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    tools=tools
                )
                return response
            else:
                # Regular chat
                response = self.llm.chat(
                    messages=messages,
                    temperature=temperature,
                    json_mode=json_mode
                )
                return response
        except Exception as e:
            self.logger.error("llm_call_failed", error=str(e))
            raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response or not response.strip():
            raise ValueError("LLM returned empty response")
        
        text = response.strip()
        
        # 1. Direct parse (pure JSON)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 2. Strip ```json ... ``` or ``` ... ```
        import re
        pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)
        for match in matches:
            candidate = match.strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        
        # 3. Find first { ... } or [ ... ] block
        for opener, closer in [('{', '}'), ('[', ']')]:
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        
        # 4. Nothing worked
        self.logger.error(
            "json_parse_failed",
            agent=self.name,
            response_preview=text[:300]
        )
        raise ValueError(f"Cannot extract JSON from LLM response. Preview: {text[:200]}")
    
    def execute(
        self,
        task: str,
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute task with execution tracking and memory integration."""
        import traceback
        
        if context is None:
            context = {}
        if workflow_id:
            context["workflow_id"] = workflow_id
        
        session_id = context.get("session_id")
        
        # Check cache (skip for chat tasks)
        if context.get("task_type") != "chat":
            cached_result = self._check_cache(task)
            if cached_result:
                self.logger.info("returning_cached_result")
                return {
                    "success": True,
                    "result": cached_result,
                    "confidence": cached_result.get("confidence", 0.8),
                    "cached": True
                }
        
        execution = AgentExecution(
            agent_name=self.name,
            task=task,
            started_at=datetime.utcnow()
        )
        
        try:
            self.logger.info(
                "task_started",
                agent=self.name,
                task=task[:120],
                session_id=session_id,
                workflow_id=workflow_id
            )
            
            result = self.process_task(task, context)
            
            # Đảm bảo result có đầy đủ fields
            if not isinstance(result, dict):
                raise ValueError(f"{self.name}.process_task returned {type(result)} instead of dict")
            if "success" not in result:
                result["success"] = True
            
            execution.result = result
            execution.confidence = result.get("confidence", CONFIDENCE_MEDIUM)
            execution.completed_at = datetime.utcnow()
            
            self.logger.info(
                "task_completed",
                agent=self.name,
                success=result.get("success"),
                confidence=execution.confidence
            )
            
            if workflow_id:
                self.memory.save_agent_execution(workflow_id, execution)
            
            if result.get("success") and execution.confidence >= 0.7:
                self._save_to_cache(task, result, execution.confidence)
            
            if session_id:
                from src.memory.models import ChatMessage
                self.memory.add_chat_message(ChatMessage(
                    session_id=session_id, role="user",
                    content=task, agent_name=self.name
                ))
                self.memory.add_chat_message(ChatMessage(
                    session_id=session_id, role="assistant",
                    content=json.dumps(result.get("result", result), ensure_ascii=False),
                    agent_name=self.name
                ))
            
            return result
            
        except Exception as e:
            full_tb = traceback.format_exc()
            execution.error = full_tb
            execution.completed_at = datetime.utcnow()
            
            self.logger.error(
                "task_failed",
                agent=self.name,
                error=str(e),
                traceback=full_tb
            )
            
            if workflow_id:
                self.memory.save_agent_execution(workflow_id, execution)
            
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": full_tb,
                "agent": self.name,
                "confidence": 0.0
            }
    
    def _get_chat_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get recent chat history for context.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve (uses config default if None)
        
        Returns:
            List of message dicts for LLM
        """
        # Use smaller limit for LLM context (not full history)
        if limit is None:
            limit = min(5, config.CHAT_HISTORY_MAX_MESSAGES)
        
        chat_messages = self.memory.get_chat_history(session_id, limit)
        
        # Convert ChatMessage objects to LLM format
        history = []
        for msg in chat_messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    def _get_workflow_context(
        self,
        workflow_id: str
    ) -> Dict[str, Any]:
        """Get workflow context from working memory.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Context dict
        """
        return self.memory.get_all_context(workflow_id)
    
    def _check_cache(
        self,
        task: str,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Check if task result is cached.
        
        Args:
            task: Task description
            params: Additional parameters
        
        Returns:
            Cached result or None
        """
        cached = self.memory.get_cached_result(
            agent_name=self.name,
            task=task,
            params=params,
            max_age_hours=24
        )
        
        if cached:
            self.logger.info("cache_hit", task=task[:50])
        
        return cached
    
    def _save_to_cache(
        self,
        task: str,
        result: Dict[str, Any],
        confidence: float,
        params: Optional[Dict] = None
    ) -> None:
        """Save result to cache.
        
        Args:
            task: Task description
            result: Result to cache
            confidence: Confidence score
            params: Additional parameters
        """
        # Only cache high-confidence results
        if confidence >= 0.7:
            self.memory.save_cached_result(
                agent_name=self.name,
                task=task,
                result=result,
                confidence=confidence,
                params=params,
                ttl_hours=24
            )
    
    @staticmethod
    def _parse_tool_arguments(arguments: Any, tool_name: str) -> Dict[str, Any]:
        """Robustly parse tool arguments from LLM.
        
        LLM can produce malformed JSON when arguments contain large markdown
        strings with literal newlines or unescaped quotes.
        """
        if isinstance(arguments, dict):
            return arguments
        if not arguments or not str(arguments).strip():
            return {}
        
        text = str(arguments)
        
        # 1. Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 2. strict=False: allows literal control characters inside strings
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            pass
        
        # 3. Fix trailing commas then retry
        import re
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            pass
        
        raise ValueError(
            f"Cannot parse tool arguments for '{tool_name}'. "
            f"First 400 chars:\n{text[:400]}"
        )

    def _execute_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tool calls returned by the LLM."""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            raw_args = tool_call.get("function", {}).get("arguments", "{}")
            
            if function_name not in self._tool_map:
                self.logger.warning("tool_not_found", tool=function_name)
                results.append({
                    "tool": function_name,
                    "success": False,
                    "error": f"Tool '{function_name}' not registered on this agent"
                })
                continue
            
            tool = self._tool_map[function_name]
            
            try:
                args = self._parse_tool_arguments(raw_args, function_name)
                
                self.logger.info(
                    "executing_tool",
                    tool=function_name,
                    arg_keys=list(args.keys()) if args else []
                )
                
                tool_result = tool.execute(**args)
                
                if not tool_result.success:
                    self.logger.warning(
                        "tool_returned_failure",
                        tool=function_name,
                        error=tool_result.error
                    )
                
                results.append({
                    "tool": function_name,
                    "success": tool_result.success,
                    "result": tool_result.result,
                    "error": tool_result.error
                })
                
            except Exception as e:
                self.logger.error(
                    "tool_execution_failed",
                    tool=function_name,
                    error=str(e),
                    raw_args_preview=str(raw_args)[:300]
                )
                results.append({
                    "tool": function_name,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def _process_with_tools(
        self,
        messages: List[Dict[str, str]],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Process task with tool calling loop."""
        import traceback
        
        tool_definitions = [tool.to_function_definition() for tool in self.tools]
        current_messages = messages.copy()
        
        for iteration in range(max_iterations):
            self.logger.debug("tool_calling_iteration", agent=self.name, iteration=iteration + 1)
            
            # LLM call returns full response dict khi có tools
            response = self._call_llm(
                current_messages,
                temperature=0.3,
                tools=tool_definitions
            )
            
            # response có thể là str (no tools path) hoặc dict (tools path)
            if isinstance(response, str):
                return {"content": response, "iterations": iteration + 1}
            
            choices = response.get("choices", [])
            if not choices:
                self.logger.warning("empty_choices_from_llm", agent=self.name, response=str(response)[:300])
                break
            
            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls")
            
            if not tool_calls:
                # LLM finished — trả content cuối
                content = message.get("content") or ""
                if not content:
                    self.logger.warning(
                        "empty_content_no_tool_calls",
                        agent=self.name,
                        message=str(message)[:300]
                    )
                return {"content": content, "iterations": iteration + 1}
            
            # Execute tools
            tool_results = self._execute_tool_calls(tool_calls)
            
            # Append assistant turn + tool results
            current_messages.append(message)
            for i, (tc, tr) in enumerate(zip(tool_calls, tool_results)):
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{i}"),
                    "name": tr["tool"],
                    "content": json.dumps(tr)
                })
        
        self.logger.warning("max_tool_iterations_reached", agent=self.name, iterations=max_iterations)
        return {
            "content": "",
            "iterations": max_iterations,
            "stopped": "max_iterations"
        }
    
    def format_messages(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        include_history: bool = True
    ) -> List[Dict[str, str]]:
        """Format messages for LLM call with memory context.
        
        Args:
            task: Task description
            context: Additional context (may include session_id, workflow_id)
            include_history: Whether to include chat history
        
        Returns:
            List of message dicts
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add chat history if session_id provided
        session_id = context.get("session_id") if context else None
        if include_history and session_id:
            # Use smaller context window for LLM
            history_limit = min(5, config.CHAT_HISTORY_MAX_MESSAGES)
            history = self._get_chat_history(session_id, limit=history_limit)
            if history:
                # Add history context
                history_text = "\n\n## Previous Conversation:\n"
                for msg in history:
                    role = msg["role"].upper()
                    history_text += f"{role}: {msg['content']}\n"
                
                messages.append({
                    "role": "system",
                    "content": history_text
                })
        
        # Add workflow context if workflow_id provided
        workflow_id = context.get("workflow_id") if context else None
        if workflow_id:
            workflow_context = self._get_workflow_context(workflow_id)
            if workflow_context:
                context_text = "\n\n## Workflow Context:\n"
                context_text += json.dumps(workflow_context, indent=2)
                
                messages.append({
                    "role": "system",
                    "content": context_text
                })
        
        # Add additional context
        if context:
            # Filter out internal keys
            filtered_context = {
                k: v for k, v in context.items()
                if k not in ["session_id", "workflow_id"]
            }
            
            if filtered_context:
                context_str = f"\n\n## Additional Context:\n{json.dumps(filtered_context, indent=2)}\n\n"
                task = context_str + task
        
        messages.append({"role": "user", "content": task})
        
        return messages
