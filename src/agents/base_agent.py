"""Base agent class for all agents in the system."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from src.llm.openrouter_client import get_client
from src.memory.memory_manager import get_memory_manager
from src.memory.models import AgentExecution
from src.logger import get_logger
from src.constants import CONFIDENCE_MEDIUM
from src.config import config

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str):
        """Initialize base agent.
        
        Args:
            name: Agent name/identifier
        """
        self.name = name
        self.llm = get_client()
        self.memory = get_memory_manager()
        self.logger = get_logger(f"agent.{name}")
    
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
        json_mode: bool = False
    ) -> str:
        """Call LLM with messages.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            json_mode: Whether to request JSON response
        
        Returns:
            LLM response content
        """
        try:
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
        """Parse JSON response from LLM.
        
        Args:
            response: Response string
        
        Returns:
            Parsed JSON dict
        """
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            self.logger.error("json_parse_failed", error=str(e), response=response[:200])
            raise ValueError(f"Failed to parse JSON: {str(e)}")
    
    def execute(
        self,
        task: str,
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute task with execution tracking and memory integration.
        
        Args:
            task: Task description
            workflow_id: Optional workflow ID for tracking
            context: Additional context (may include session_id)
        
        Returns:
            Result dict
        """
        # Merge workflow_id into context
        if context is None:
            context = {}
        if workflow_id:
            context["workflow_id"] = workflow_id
        
        # Check cache first (only for non-chat tasks)
        session_id = context.get("session_id")
        if not session_id or context.get("task_type") != "chat":
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
                task=task[:100],
                session_id=session_id,
                workflow_id=workflow_id
            )
            
            # Process task with full context
            result = self.process_task(task, context)
            
            execution.result = result
            execution.confidence = result.get("confidence", CONFIDENCE_MEDIUM)
            execution.completed_at = datetime.utcnow()
            
            self.logger.info(
                "task_completed",
                success=result.get("success", False),
                confidence=execution.confidence
            )
            
            # Save execution to memory
            if workflow_id:
                self.memory.save_agent_execution(workflow_id, execution)
            
            # Cache result if high confidence
            if result.get("success") and execution.confidence >= 0.7:
                self._save_to_cache(task, result, execution.confidence)
            
            # Save to chat history if session_id provided
            if session_id:
                from src.memory.models import ChatMessage
                
                # Save user message
                self.memory.add_chat_message(ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=task,
                    agent_name=self.name
                ))
                
                # Save assistant response
                response_content = json.dumps(result.get("result", result), ensure_ascii=False)
                self.memory.add_chat_message(ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=response_content,
                    agent_name=self.name
                ))
            
            return result
            
        except Exception as e:
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            
            self.logger.error("task_failed", error=str(e))
            
            if workflow_id:
                self.memory.save_agent_execution(workflow_id, execution)
            
            return {
                "success": False,
                "error": str(e),
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
