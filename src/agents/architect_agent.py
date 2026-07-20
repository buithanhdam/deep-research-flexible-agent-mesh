"""Architect Agent - generates technical documents and deliverables."""

from typing import Dict, Any, Optional, List
from src.agents.base_agent import BaseAgent
from src.constants import AGENT_ARCHITECT
from src.tools.base_tool import BaseTool
from src.logger import get_logger

logger = get_logger(__name__)


class ArchitectAgent(BaseAgent):
    """Agent specialized in generating technical documentation and deliverables."""
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize architect agent.
        
        Args:
            tools: List of tools available to this agent
        """
        super().__init__(AGENT_ARCHITECT)
        self.tools = tools or []
        self._tool_map = {tool.name: tool for tool in self.tools}
    
    def get_system_prompt(self) -> str:
        """Get system prompt for architect agent."""
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools
        ])
        
        return f"""You are an Architect Agent specialized in creating technical documentation and deliverables.

# Your Role
Transform research findings and analysis results into professional, well-structured documents.

# Available Tools
{tool_descriptions}

# Process

## Step 1: Analyze Input
Review the results from previous agents (research, data analysis) to understand what needs to be documented.

## Step 2: Plan Document Structure
Create a logical document structure with:
- Executive summary
- Key findings
- Detailed analysis
- Recommendations/next steps
- References/sources

## Step 3: Generate Document
Use your tools to create the document:
1. Generate Markdown content with proper sections
2. Convert to PDF/DOCX if requested
3. Generate diagrams if needed
4. Upload to Google Drive if requested

## Step 4: Return Deliverables
Provide file paths, links, and summary of what was created.

# Output Format
Always respond with JSON:
```json
{{
  "documents_created": [
    {{
      "type": "markdown|pdf|docx",
      "file_path": "path/to/file",
      "title": "document title",
      "size_bytes": 12345
    }}
  ],
  "uploaded_files": [
    {{
      "filename": "doc.pdf",
      "drive_link": "https://drive.google.com/...",
      "file_id": "abc123"
    }}
  ],
  "summary": "Brief summary of deliverables created",
  "tool_calls": ["list of tools used"]
}}
```

# Rules
1. Create clear, professional documents
2. Use proper Markdown formatting
3. Include all sources and references
4. Generate diagrams when helpful for understanding
5. Always upload to Drive if configured
6. Provide shareable links
"""
    
    def process_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process document generation task.
        
        Args:
            task: Task description
            context: Additional context including results from other agents
        
        Returns:
            Dict with generation results
        """
        # Build messages with tool definitions
        messages = self._format_messages_with_tools(task, context)
        
        try:
            # Call LLM with function calling
            import json
            
            # Get tool definitions
            tools_schema = [tool.to_function_definition() for tool in self.tools]
            
            # Simple implementation - let LLM decide what to generate
            # In production, use proper function calling flow
            
            response = self._call_llm(messages, temperature=0.3, json_mode=True)
            result = self._parse_json_response(response)
            
            # Execute tool calls if any
            # This is simplified - in production use proper function calling loop
            
            return {
                "success": True,
                "result": result,
                "confidence": 0.9
            }
            
        except Exception as e:
            self.logger.error("architect_processing_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "confidence": 0.0
            }
    
    def _format_messages_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Format messages including context from previous agents."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add context from previous agents if available
        if context:
            workflow_id = context.get("workflow_id")
            if workflow_id:
                workflow_context = self.memory.get_all_context(workflow_id)
                if workflow_context:
                    context_str = f"## Previous Agent Results:\n{json.dumps(workflow_context, indent=2)}\n\n"
                    task = context_str + task
        
        messages.append({"role": "user", "content": task})
        
        return messages
