"""Memory manager - gateway between agents and database."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import hashlib
import json

from src.memory.models import (
    AgentExecution,
    WorkflowState,
    CachedResult,
    ChatMessage
)
from src.db.postgres_client import get_postgres_client
from src.logger import get_logger
from src.config import config

logger = get_logger(__name__)


class MemoryManager:
    """Central memory management for the multi-agent system."""
    
    def __init__(self):
        """Initialize memory manager."""
        self.db = get_postgres_client()
        self._working_memory: Dict[str, Any] = {}
    
    # ========== Working Memory (Runtime only) ==========
    
    def set_context(self, workflow_id: str, key: str, value: Any) -> None:
        """Set a context value in working memory.
        
        Args:
            workflow_id: Workflow identifier
            key: Context key
            value: Context value
        """
        if workflow_id not in self._working_memory:
            self._working_memory[workflow_id] = {}
        
        self._working_memory[workflow_id][key] = value
        logger.debug("context_set", workflow_id=workflow_id, key=key)
    
    def get_context(self, workflow_id: str, key: str, default: Any = None) -> Any:
        """Get a context value from working memory.
        
        Args:
            workflow_id: Workflow identifier
            key: Context key
            default: Default value if not found
        
        Returns:
            Context value or default
        """
        return self._working_memory.get(workflow_id, {}).get(key, default)
    
    def get_all_context(self, workflow_id: str) -> Dict[str, Any]:
        """Get all context for a workflow.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            All context as dict
        """
        return self._working_memory.get(workflow_id, {})
    
    def clear_context(self, workflow_id: str) -> None:
        """Clear working memory for a workflow.
        
        Args:
            workflow_id: Workflow identifier
        """
        if workflow_id in self._working_memory:
            del self._working_memory[workflow_id]
            logger.debug("context_cleared", workflow_id=workflow_id)
    
    # ========== Short-term Memory (Recent workflows) ==========
    
    def save_workflow_state(self, state: WorkflowState) -> None:
        """Save workflow state to database.
        
        Args:
            state: Workflow state to save
        """
        if not self.db.is_available():
            logger.warning("db_not_available_skipping_save")
            return
        
        try:
            query = """
                INSERT INTO workflow_states (
                    workflow_id, status, current_step, context, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (workflow_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    current_step = EXCLUDED.current_step,
                    context = EXCLUDED.context,
                    updated_at = EXCLUDED.updated_at
            """
            
            self.db.execute_query(
                query,
                (
                    state.workflow_id,
                    state.status,
                    state.current_step,
                    json.dumps(state.context),
                    state.created_at,
                    state.updated_at
                ),
                fetch=False
            )
            
            logger.info(
                "workflow_state_saved",
                workflow_id=state.workflow_id,
                status=state.status
            )
            
        except Exception as e:
            logger.error("save_workflow_state_failed", error=str(e))
    
    def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get workflow state from database.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Workflow state or None
        """
        if not self.db.is_available():
            logger.warning("db_not_available")
            return None
        
        try:
            query = """
                SELECT workflow_id, status, current_step, context, created_at, updated_at
                FROM workflow_states
                WHERE workflow_id = %s
            """
            
            results = self.db.execute_query(query, (workflow_id,))
            
            if not results:
                return None
            
            row = results[0]
            
            return WorkflowState(
                workflow_id=row['workflow_id'],
                status=row['status'],
                current_step=row['current_step'],
                context=row['context'] or {},
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
        except Exception as e:
            logger.error("get_workflow_state_failed", error=str(e))
            return None
    
    def save_agent_execution(
        self,
        workflow_id: str,
        execution: AgentExecution
    ) -> None:
        """Save agent execution record.
        
        Args:
            workflow_id: Workflow identifier
            execution: Agent execution record
        """
        if not self.db.is_available():
            logger.warning("db_not_available_skipping_save")
            return
        
        try:
            # Ensure workflow state exists first
            query_check = "SELECT 1 FROM workflow_states WHERE workflow_id = %s"
            exists = self.db.execute_query(query_check, (workflow_id,))
            
            if not exists:
                # Create workflow state if not exists
                from src.memory.models import WorkflowState
                self.save_workflow_state(WorkflowState(
                    workflow_id=workflow_id,
                    status="running",
                    current_step=execution.agent_name
                ))
            
            query = """
                INSERT INTO agent_executions (
                    workflow_id, agent_name, task, result, confidence,
                    error, started_at, completed_at, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            self.db.execute_query(
                query,
                (
                    workflow_id,
                    execution.agent_name,
                    execution.task,
                    json.dumps(execution.result) if execution.result else None,
                    execution.confidence,
                    execution.error,
                    execution.started_at,
                    execution.completed_at,
                    json.dumps(execution.metadata)
                ),
                fetch=False
            )
            
            logger.info(
                "agent_execution_saved",
                workflow_id=workflow_id,
                agent=execution.agent_name,
                success=execution.error is None
            )
            
        except Exception as e:
            logger.error("save_agent_execution_failed", error=str(e))
    
    # ========== Long-term Memory (Cached results) ==========
    
    def _generate_cache_key(
        self,
        agent_name: str,
        task: str,
        params: Optional[Dict] = None
    ) -> str:
        """Generate cache key for a task.
        
        Args:
            agent_name: Name of the agent
            task: Task description
            params: Additional parameters
        
        Returns:
            Cache key hash
        """
        content = f"{agent_name}:{task}"
        if params:
            content += f":{json.dumps(params, sort_keys=True)}"
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_cached_result(
        self,
        agent_name: str,
        task: str,
        params: Optional[Dict] = None,
        max_age_hours: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached result if available and not expired.
        
        Args:
            agent_name: Name of the agent
            task: Task description
            params: Additional parameters
            max_age_hours: Maximum age in hours
        
        Returns:
            Cached result or None
        """
        if not self.db.is_available():
            return None
        
        # Use config default if not specified
        if max_age_hours is None:
            max_age_hours = config.CACHE_DEFAULT_TTL_HOURS
        
        cache_key = self._generate_cache_key(agent_name, task, params)
        
        try:
            query = """
                SELECT result, confidence, hit_count
                FROM cached_results
                WHERE cache_key = %s
                  AND agent_name = %s
                  AND (expires_at IS NULL OR expires_at > NOW())
                  AND created_at > NOW() - (%s || ' hours')::INTERVAL
            """
            
            results = self.db.execute_query(
                query,
                (cache_key, agent_name, max_age_hours)
            )
            
            if not results:
                logger.debug("cache_miss", agent=agent_name, key=cache_key)
                return None
            
            row = results[0]
            
            # Update hit count
            update_query = """
                UPDATE cached_results
                SET hit_count = hit_count + 1,
                    last_hit_at = NOW()
                WHERE cache_key = %s
            """
            self.db.execute_query(update_query, (cache_key,), fetch=False)
            
            logger.info(
                "cache_hit",
                agent=agent_name,
                key=cache_key,
                hit_count=row['hit_count'] + 1
            )
            
            return {
                **row['result'],
                'confidence': float(row['confidence'])
            }
            
        except Exception as e:
            logger.error("get_cached_result_failed", error=str(e))
            return None
    
    def save_cached_result(
        self,
        agent_name: str,
        task: str,
        result: Dict[str, Any],
        confidence: float,
        params: Optional[Dict] = None,
        ttl_hours: Optional[int] = None
    ) -> None:
        """Save result to cache.
        
        Args:
            agent_name: Name of the agent
            task: Task description
            result: Result to cache
            confidence: Confidence score
            params: Additional parameters
            ttl_hours: Time to live in hours
        """
        if not self.db.is_available():
            return
        
        # Use config default if not specified
        if ttl_hours is None:
            ttl_hours = config.CACHE_DEFAULT_TTL_HOURS
        
        # Enforce max TTL
        if ttl_hours > config.CACHE_MAX_TTL_HOURS:
            ttl_hours = config.CACHE_MAX_TTL_HOURS
            logger.warning(
                "cache_ttl_capped",
                requested=ttl_hours,
                max=config.CACHE_MAX_TTL_HOURS
            )
        
        cache_key = self._generate_cache_key(agent_name, task, params)
        task_hash = hashlib.sha256(task.encode()).hexdigest()
        
        try:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            
            query = """
                INSERT INTO cached_results (
                    cache_key, agent_name, task_hash, task, result,
                    confidence, params, expires_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (cache_key) DO UPDATE SET
                    result = EXCLUDED.result,
                    confidence = EXCLUDED.confidence,
                    expires_at = EXCLUDED.expires_at,
                    hit_count = 0
            """
            
            self.db.execute_query(
                query,
                (
                    cache_key,
                    agent_name,
                    task_hash,
                    task,
                    json.dumps(result),
                    confidence,
                    json.dumps(params) if params else None,
                    expires_at
                ),
                fetch=False
            )
            
            logger.info("cache_saved", agent=agent_name, key=cache_key)
            
        except Exception as e:
            logger.error("save_cached_result_failed", error=str(e))
    
    # ========== Chat History (MVP - Simple session-based) ==========
    
    def add_chat_message(self, message: ChatMessage) -> None:
        """Add message to chat history.
        
        Args:
            message: Chat message to save
        """
        if not self.db.is_available():
            logger.warning("db_not_available_skipping_save")
            return
        
        try:
            query = """
                INSERT INTO chat_history (
                    session_id, role, content, agent_name, timestamp, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
            """
            
            self.db.execute_query(
                query,
                (
                    message.session_id,
                    message.role,
                    message.content,
                    message.agent_name,
                    message.timestamp,
                    json.dumps(message.metadata)
                ),
                fetch=False
            )
            
            logger.info(
                "chat_message_saved",
                session_id=message.session_id,
                role=message.role
            )
            
        except Exception as e:
            logger.error("add_chat_message_failed", error=str(e))
    
    def get_chat_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get recent chat history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages
        
        Returns:
            List of chat messages
        """
        if not self.db.is_available():
            logger.warning("db_not_available")
            return []
        
        # Use config default if not specified
        if limit is None:
            limit = config.CHAT_HISTORY_MAX_MESSAGES
        
        try:
            query = """
                SELECT session_id, role, content, agent_name, timestamp, metadata
                FROM chat_history
                WHERE session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            
            results = self.db.execute_query(query, (session_id, limit))
            
            if not results:
                return []
            
            # Reverse to get chronological order
            messages = []
            for row in reversed(results):
                messages.append(ChatMessage(
                    session_id=row['session_id'],
                    role=row['role'],
                    content=row['content'],
                    agent_name=row['agent_name'],
                    timestamp=row['timestamp'],
                    metadata=row['metadata'] or {}
                ))
            
            logger.info(
                "chat_history_retrieved",
                session_id=session_id,
                count=len(messages)
            )
            
            return messages
            
        except Exception as e:
            logger.error("get_chat_history_failed", error=str(e))
            return []


    # ========== Helper Methods ==========
    
    def get_agent_executions(
        self,
        workflow_id: str
    ) -> List[AgentExecution]:
        """Get all agent executions for a workflow.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            List of agent executions
        """
        if not self.db.is_available():
            return []
        
        try:
            query = """
                SELECT agent_name, task, result, confidence, error,
                       started_at, completed_at, metadata
                FROM agent_executions
                WHERE workflow_id = %s
                ORDER BY started_at ASC
            """
            
            results = self.db.execute_query(query, (workflow_id,))
            
            executions = []
            for row in results:
                executions.append(AgentExecution(
                    agent_name=row['agent_name'],
                    task=row['task'],
                    result=row['result'],
                    confidence=float(row['confidence']) if row['confidence'] else None,
                    error=row['error'],
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    metadata=row['metadata'] or {}
                ))
            
            return executions
            
        except Exception as e:
            logger.error("get_agent_executions_failed", error=str(e))
            return []
    
    def cleanup_old_data(self, retention_days: Optional[int] = None) -> Dict[str, int]:
        """Clean up old data from database.
        
        Args:
            retention_days: Number of days to retain data
        
        Returns:
            Dict with counts of deleted records
        """
        if not self.db.is_available():
            return {}
        
        # Use config default if not specified
        if retention_days is None:
            retention_days = config.CHAT_HISTORY_RETENTION_DAYS
        
        try:
            # Clean chat history
            chat_result = self.db.execute_query(
                "SELECT cleanup_old_chat_history(%s)",
                (retention_days,)
            )
            chat_deleted = chat_result[0]['cleanup_old_chat_history'] if chat_result else 0
            
            # Clean expired cache
            cache_result = self.db.execute_query(
                "SELECT cleanup_expired_cache()"
            )
            cache_deleted = cache_result[0]['cleanup_expired_cache'] if cache_result else 0
            
            # Clean old workflows
            workflow_result = self.db.execute_query(
                "SELECT cleanup_old_workflows(%s)",
                (retention_days,)
            )
            workflow_deleted = workflow_result[0]['cleanup_old_workflows'] if workflow_result else 0
            
            logger.info(
                "cleanup_completed",
                chat_deleted=chat_deleted,
                cache_deleted=cache_deleted,
                workflow_deleted=workflow_deleted
            )
            
            return {
                'chat_messages': chat_deleted,
                'cached_results': cache_deleted,
                'workflows': workflow_deleted
            }
            
        except Exception as e:
            logger.error("cleanup_failed", error=str(e))
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics.
        
        Returns:
            Dict with statistics
        """
        if not self.db.is_available():
            return {"database": "not_available"}
        
        try:
            stats = {}
            
            # Agent performance
            perf_query = "SELECT * FROM agent_performance"
            stats['agent_performance'] = self.db.execute_query(perf_query)
            
            # Cache statistics
            cache_query = "SELECT * FROM cache_statistics"
            stats['cache_statistics'] = self.db.execute_query(cache_query)
            
            # Workflow statistics
            workflow_query = "SELECT * FROM workflow_statistics"
            stats['workflow_statistics'] = self.db.execute_query(workflow_query)
            
            # Working memory size
            stats['working_memory_workflows'] = len(self._working_memory)
            
            return stats
            
        except Exception as e:
            logger.error("get_statistics_failed", error=str(e))
            return {"error": str(e)}
    
    def init_database(self) -> bool:
        """Initialize database schema.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.db.is_available():
            logger.error("database_not_available")
            return False
        
        try:
            # Read schema file
            import os
            schema_path = os.path.join(
                os.path.dirname(__file__),
                'schema.sql'
            )
            
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Execute the whole schema as one script — do NOT split by ';',
            # since $$ ... $$ function bodies contain their own semicolons.
            self.db.execute_script(schema_sql)
            
            logger.info("database_initialized")
            return True
            
        except Exception as e:
            logger.error("init_database_failed", error=str(e))
            return False


# Singleton instance
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create memory manager singleton."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
