"""Base tool class for agent tools."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from typing import Optional


class ToolInput(BaseModel):
    """Base input schema for tools."""
    pass


class ToolResult(BaseModel):
    """Tool execution result."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, **config):
        """Initialize tool.
        
        Args:
            name: Override default tool name
            description: Override default description
            **config: Additional tool-specific configuration
        """
        self.name = name or self.get_name()
        self.description = description or self.get_description()
        self.config = config
    
    @abstractmethod
    def get_name(self) -> str:
        """Get tool name."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get tool description for LLM."""
        pass
    
    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool inputs (OpenAI function format)."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute tool with given inputs.
        
        Returns:
            ToolResult with success/result/error
        """
        pass
    
    def to_function_definition(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling format.
        
        Returns:
            Function definition dict
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_input_schema()
            }
        }
