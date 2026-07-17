"""Data models for memory system."""

from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class MemoryType(str, Enum):
    """Types of memory storage."""
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class AgentExecution(BaseModel):
    """Record of an agent execution."""
    agent_name: str
    task: str
    result: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    """State of a workflow execution."""
    workflow_id: str
    status: str  # running, completed, failed, paused
    current_step: str
    agent_executions: List[AgentExecution] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CachedResult(BaseModel):
    """Cached result from a previous execution."""
    key: str
    agent_name: str
    task_hash: str
    result: Dict[str, Any]
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    hit_count: int = 0


class ChatMessage(BaseModel):
    """Chat message for session history."""
    session_id: str
    role: str  # user, assistant, system
    content: str
    agent_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
