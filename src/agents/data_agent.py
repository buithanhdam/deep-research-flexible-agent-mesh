"""Data Agent - processes and analyzes data."""

from typing import Dict, Any, Optional

from src.agents.base_agent import BaseAgent
from src.constants import AGENT_DATA


class DataAgent(BaseAgent):
    """Agent specialized in data processing and analysis."""
    
    def __init__(self):
        """Initialize data agent."""
        super().__init__(AGENT_DATA)
    
    def get_system_prompt(self) -> str:
        """Get system prompt for data agent.
        
        Returns:
            System prompt string
        """
        return """You are a Data Agent specialized in processing and analyzing data.

# Your Role
Process, transform, and analyze data according to requirements.

# Capabilities
- Data transformation and cleaning
- Statistical analysis
- Data aggregation and summarization
- Format conversion

# Output Format
Respond with JSON:
```json
{
  "processed_data": {},
  "analysis": "analysis summary",
  "statistics": {},
  "confidence": 0.0-1.0
}
```

# Rules
1. Validate input data before processing
2. Handle errors gracefully
3. Document any assumptions made
4. Provide confidence scores for analyses
"""
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process data task.
        
        Args:
            task: Data processing task
            context: Additional context including data
        
        Returns:
            Dict with processed data results
        """
        messages = self.format_messages(task, context)
        
        try:
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            result = self._parse_json_response(response)
            
            return {
                "success": True,
                "result": result,
                "confidence": result.get("confidence", 0.7)
            }
            
        except Exception as e:
            self.logger.error("data_processing_failed", error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "confidence": 0.0
            }
