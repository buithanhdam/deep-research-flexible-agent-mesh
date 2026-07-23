"""Main Agent Flow entry point for the multi-agent system."""

import json
from typing import Dict, Any
import uuid

from src.config import config
from src.logger import get_logger

from src.agents.precheck_agent import PrecheckAgent
from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.research_agent import ResearchAgent
from src.agents.data_agent import DataAgent
from src.agents.notification_agent import NotificationAgent
from src.agents.architect_agent import ArchitectAgent
from src.memory.memory_manager import get_memory_manager

# Import tools
from src.tools import (WebSearchTool, WebScrapeTool, JsonProcessorTool, MarkdownGeneratorTool,
                       PDFGeneratorTool, DocxGeneratorTool, GoogleDriveUploadTool,
                     GoogleDriveDownloadTool, DiagramGeneratorTool, LarkSendMessageTool,
                     LarkFileDownloadTool, LarkFileUploadTool, FileExtractorTool)

logger = get_logger(__name__)


def setup_orchestrator() -> OrchestratorAgent:
    """Setup orchestrator with registered agents and their tools.
    
    Returns:
        Configured orchestrator agent
    """
    orchestrator = OrchestratorAgent()
    
    # Setup Research Agent with search tools
    research_tools = [
        WebSearchTool(),  # General search
        WebScrapeTool(),
        FileExtractorTool()  # For reading downloaded files
    ]
    research_agent = ResearchAgent(tools=research_tools)
    
    # Setup Data Agent with data processing tools
    data_tools = [
        JsonProcessorTool(),
        FileExtractorTool(),
        GoogleDriveDownloadTool(),
        LarkFileDownloadTool()
    ]
    data_agent = DataAgent(tools=data_tools)
    
    # Setup Notification Agent with Lark tools
    notification_tools = [
        LarkSendMessageTool(),
        LarkFileUploadTool()
    ]
    notification_agent = NotificationAgent(tools=notification_tools)
    
    # Setup Architect Agent with document generation tools
    architect_tools = [
        MarkdownGeneratorTool(),
        PDFGeneratorTool(),
        DocxGeneratorTool(),
        GoogleDriveUploadTool(),
        DiagramGeneratorTool(),
        LarkFileUploadTool()  # Upload to Lark
    ]
    architect_agent = ArchitectAgent(tools=architect_tools)
    
    # Register all agents
    orchestrator.register_agent("research", research_agent)
    orchestrator.register_agent("data", data_agent)
    orchestrator.register_agent("notification", notification_agent)
    orchestrator.register_agent("architect", architect_agent)
    
    logger.info("orchestrator_setup_complete", agents=list(orchestrator._agent_registry.keys()))
    
    return orchestrator


def process_message(message: str, session_id: str = None) -> Dict[str, Any]:
    """Process incoming message through the agent system.
    
    Args:
        message: Incoming message text
        session_id: Optional session identifier
    
    Returns:
        Result dict
    """
    workflow_id = str(uuid.uuid4())
    memory = get_memory_manager()
    
    if not session_id:
        session_id = "default"
    
    logger.info(
        "processing_message",
        workflow_id=workflow_id,
        session_id=session_id,
        message_preview=message[:100]
    )
    
    try:
        # Step 1: Precheck - filter chat vs research
        logger.info("step_precheck", workflow_id=workflow_id)
        precheck = PrecheckAgent()
        precheck_result = precheck.execute(
            task=message,
            workflow_id=workflow_id,
            context={"session_id": session_id}
        )
        
        if not precheck_result.get("success"):
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": "Precheck failed",
                "details": precheck_result
            }
        
        result_data = precheck_result.get("result", {})
        
        # If it's just chat, return direct response
        if not result_data.get("is_pass", False):
            logger.info("chat_response", workflow_id=workflow_id)
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "type": "chat",
                "response": result_data.get("response", "Hello! How can I help you?"),
                "topic": result_data.get("topic", "greeting")
            }
        
        # Step 2: Research task - send confirmation
        logger.info("research_task_detected", workflow_id=workflow_id)
        
        confirmation = {
            "workflow_id": workflow_id,
            "status": "processing",
            "message": "I'm working on your request. This may take 1-2 minutes...",
            "topic": result_data.get("topic", "research")
        }
        
        # In n8n integration, this would be sent immediately
        # For CLI, we just log it
        logger.info("confirmation_sent", **confirmation)
        
        # Step 3: Run orchestrator
        logger.info("step_orchestrator", workflow_id=workflow_id)
        orchestrator = setup_orchestrator()
        
        orchestrator_result = orchestrator.execute(
            task=message,
            workflow_id=workflow_id,
            context={
                "session_id": session_id,
                "topic": result_data.get("topic"),
                "task_type": result_data.get("task_type")
            }
        )
        
        # Step 4: Check if need to call Architect
        if orchestrator_result.get("success"):
            action = orchestrator_result.get("action", "return")
            
            if action == "escalate":
                logger.info("escalating", workflow_id=workflow_id)
                return {
                    "workflow_id": workflow_id,
                    "status": "escalated",
                    "reason": orchestrator_result.get("reason", "Needs review"),
                    "confidence": orchestrator_result.get("confidence", 0.0),
                    "partial_results": orchestrator_result.get("result", {})
                }
            
            else:
                # Step 5: Call Architect to generate document
                logger.info("calling_architect", workflow_id=workflow_id)
                orchestrator = setup_orchestrator()
                architect = orchestrator._agent_registry.get("architect")
                
                if architect:
                    architect_task = f"""Generate professional documentation for the following task and results:

Original Task: {message}

Results:
{json.dumps(orchestrator_result.get('result', {}), indent=2)}

Create:
1. Markdown document with clear structure
2. PDF version
3. Upload to Google Drive if configured

Provide links and file paths.
"""
                    
                    architect_result = architect.execute(
                        task=architect_task,
                        workflow_id=workflow_id,
                        context={
                            "session_id": session_id,
                            "orchestrator_results": orchestrator_result
                        }
                    )
                    
                    logger.info("architect_completed", success=architect_result.get("success"))
                else:
                    architect_result = {"success": False, "error": "Architect not available"}
                
                logger.info("returning_results", workflow_id=workflow_id)
                return {
                    "workflow_id": workflow_id,
                    "status": "completed",
                    "type": "research",
                    "confidence": orchestrator_result.get("confidence", 0.0),
                    "result": orchestrator_result.get("result", {}),
                    "documents": architect_result.get("result", {}),
                    "agent_details": orchestrator_result.get("agent_results", []),
                    "rounds": orchestrator_result.get("rounds_executed", 0)
                }
        
        else:
            logger.error("orchestrator_failed", workflow_id=workflow_id)
            error_msg = orchestrator_result.get("error", "Unknown error")
            
            # Send error notification if Lark configured
            if config.LARK_APP_ID and config.LARK_ERROR_CHAT_ID:
                try:
                    from src.tools.lark_send_message_tool import LarkSendMessageTool
                    lark_tool = LarkSendMessageTool()
                    lark_tool.execute(
                        receive_id=config.LARK_ERROR_CHAT_ID,
                        message=f"❌ Task Failed\n\nWorkflow: {workflow_id}\nError: {error_msg}\n\nTask: {message[:200]}",
                        msg_type="text"
                    )
                except Exception as e:
                    logger.error("error_notification_failed", error=str(e))
            
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": error_msg,
                "details": orchestrator_result
            }
    
    except Exception as e:
        logger.error("processing_failed", workflow_id=workflow_id, error=str(e))
        
        # Send critical error notification
        if config.LARK_APP_ID and config.LARK_ERROR_CHAT_ID:
            try:
                from src.tools.lark_send_message_tool import LarkSendMessageTool
                lark_tool = LarkSendMessageTool()
                lark_tool.execute(
                    receive_id=config.LARK_ERROR_CHAT_ID,
                    message=f"🚨 Critical Error\n\nWorkflow: {workflow_id}\nException: {str(e)}\n\nTask: {message[:200]}",
                    msg_type="text"
                )
            except:
                pass
        
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e)
        }
    finally:
        # Clear working memory if auto-clear enabled
        if config.WORKING_MEMORY_AUTO_CLEAR:
            memory.clear_context(workflow_id)
            logger.debug("working_memory_cleared", workflow_id=workflow_id)