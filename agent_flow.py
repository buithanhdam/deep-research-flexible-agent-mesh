"""Main Agent Flow entry point for the multi-agent system."""

import json
from typing import Dict, Any, List
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
                     LarkFileDownloadTool, LarkFileUploadTool, FileExtractorTool,
                     ArxivSearchTool, HuggingFaceTool, GitHubRepoTool,
                     WikipediaTool, NewsSearchTool, StackOverflowTool,
                     YouTubeTranscriptTool, CodeSnippetTool,
                     DataChartTool, ComparisonTableTool, MindmapGeneratorTool)
from src.constants import (
    TIER_CHAT, TIER_QUICK_RESEARCH, TIER_DEEP_RESEARCH, TIER_MULTI_DOMAIN,
    DELIVERY_NONE, DELIVERY_DOCUMENT, DELIVERY_DIAGRAM, DELIVERY_NOTIFY, DELIVERY_UPLOAD,
    WORKFLOW_AWAITING_CONFIRMATION, WORKFLOW_GENERATING,
)
from src.prompt_templates.output_models import ProposedAction

logger = get_logger(__name__)


def _send_error_to_lark(
    workflow_id: str,
    task: str,
    error: str,
    error_type: str = "",
    agent: str = "",
    traceback: str = ""
) -> None:
    """Send structured error notification to Lark."""
    try:
        from src.tools.lark_send_message_tool import LarkSendMessageTool
        
        # Truncate traceback — Lark có giới hạn message size
        tb_snippet = traceback.strip().splitlines()
        tb_short = "\n".join(tb_snippet[-10:]) if tb_snippet else "(no traceback)"
        
        msg = (
            f"❌ Task Failed\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Workflow : {workflow_id}\n"
            f"Agent    : {agent or 'unknown'}\n"
            f"Error    : {error_type}: {error}\n\n"
            f"Task (preview):\n{task[:300]}\n\n"
            f"Traceback (last 10 lines):\n{tb_short}"
        )
        
        lark_tool = LarkSendMessageTool()
        result = lark_tool.execute(
            receive_id=config.LARK_ERROR_CHAT_ID,
            message=msg,
            msg_type="text"
        )
        
        if not result.success:
            logger.error("lark_error_notification_failed", error=result.error)
        else:
            logger.info("lark_error_notification_sent", workflow_id=workflow_id)
            
    except Exception as e:
        # Tuyệt đối không raise ở đây
        logger.error("lark_error_notification_exception", error=str(e))


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
        FileExtractorTool(),  # For reading downloaded files
        # Free research tools (no API key required)
        ArxivSearchTool(),       # arXiv academic papers
        HuggingFaceTool(),       # HuggingFace Hub models/spaces
        GitHubRepoTool(),        # GitHub repo search
        WikipediaTool(),         # Wikipedia encyclopedia
        NewsSearchTool(),        # GDELT news search
        StackOverflowTool(),     # Stack Overflow Q&A
        YouTubeTranscriptTool(), # YouTube video transcripts
        CodeSnippetTool(),       # Extract code from scraped content
    ]
    research_agent = ResearchAgent(tools=research_tools)
    
    # Setup Data Agent with data processing + visualization tools
    data_tools = [
        JsonProcessorTool(),
        FileExtractorTool(),
        GoogleDriveDownloadTool(),
        LarkFileDownloadTool(),
        # Visualization & analysis tools (free)
        DataChartTool(),         # matplotlib charts → PNG
        ComparisonTableTool(),   # comparison tables → MD/HTML
        MindmapGeneratorTool(),  # concept maps → PNG (graphviz)
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


# ─────────────────────────────────────────────
# Delivery-gate helpers (Part 1 & 2)
# ─────────────────────────────────────────────

def _build_proposed_actions(task_tier: str) -> List["ProposedAction"]:
    """Build the list of deliverable options to propose to the user.

    These are rendered by the UI as selectable choices. The user picks one,
    then the pipeline resumes by calling execute_delivery().
    """
    actions = [
        ProposedAction(
            action_id="create_pdf",
            label="📄 Tạo tài liệu PDF",
            description="Tạo tài liệu PDF đầy đủ từ kết quả research, kèm nguồn tham khảo.",
            action_type="create_document",
            formats=["markdown", "pdf"],
        ),
        ProposedAction(
            action_id="create_docx",
            label="📝 Tạo tài liệu DOCX",
            description="Tạo tài liệu Word (.docx) có thể chỉnh sửa từ kết quả research.",
            action_type="create_document",
            formats=["markdown", "docx"],
        ),
        ProposedAction(
            action_id="create_diagram",
            label="📊 Tạo sơ đồ kiến trúc",
            description="Sinh diagram (Graphviz DOT) mô tả kiến trúc / luồng từ kết quả research.",
            action_type="create_diagram",
            formats=["dot", "png"],
        ),
    ]

    # Upload option chỉ hiện khi Google Drive đã cấu hình
    if config.GOOGLE_DRIVE_ENABLED:
        actions.append(ProposedAction(
            action_id="upload_drive",
            label="☁️ Tạo PDF & upload Google Drive",
            description="Tạo PDF rồi upload lên Google Drive, trả về link chia sẻ.",
            action_type="upload_drive",
            formats=["markdown", "pdf"],
        ))

    # Notify option chỉ hiện khi Lark notification đang bật
    if config.LARK_NOTIFICATION_ENABLED:
        actions.append(ProposedAction(
            action_id="notify_lark",
            label="💬 Gửi kết quả qua Lark",
            description="Định dạng tóm tắt và gửi notification qua Lark.",
            action_type="notify",
            formats=[],
        ))

    # Option "không tạo gì thêm" luôn có
    actions.append(ProposedAction(
        action_id="none",
        label="✅ Chỉ giữ kết quả research",
        description="Không tạo tài liệu thêm — kết quả research đã đủ cho nhu cầu hiện tại.",
        action_type="none",
        formats=[],
    ))

    return actions


def _save_workflow_state(
    workflow_id: str,
    status: str,
    current_step: str,
    context: Dict[str, Any],
    memory,
) -> None:
    """Persist workflow state to DB (reuses existing workflow_states table)."""
    try:
        from src.memory.models import WorkflowState
        from datetime import datetime
        state = WorkflowState(
            workflow_id=workflow_id,
            status=status,
            current_step=current_step,
            context=context,
            updated_at=datetime.utcnow(),
        )
        memory.save_workflow_state(state)
    except Exception as e:
        logger.warning("save_workflow_state_failed", workflow_id=workflow_id, error=str(e))


def _execute_delivery(
    workflow_id: str,
    session_id: str,
    message: str,
    delivery_intent: str,
    orchestrator_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the delivery step (Architect / Notification) based on intent.

    Called when delivery_intent is explicitly non-'none' (user asked for a
    deliverable) OR when the user confirms a proposed action via resume.
    """
    logger.info("executing_delivery", workflow_id=workflow_id, delivery_intent=delivery_intent)

    # Notify intent → chỉ chạy notification agent (nếu Lark đang bật)
    if delivery_intent == DELIVERY_NOTIFY:
        if not config.LARK_NOTIFICATION_ENABLED:
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "type": "research",
                "confidence": orchestrator_result.get("confidence", 0.0),
                "result": orchestrator_result.get("result", {}),
                "documents": {},
                "notification": {"skipped": True, "reason": "LARK_NOTIFICATION_ENABLED=false"},
                "agent_details": orchestrator_result.get("agent_results", []),
                "rounds": orchestrator_result.get("rounds_executed", 0),
            }
        orchestrator = setup_orchestrator()
        notif_agent = orchestrator._agent_registry.get("notification")
        if notif_agent:
            notif_agent.execute(
                task=f"Notify about completed research: {message}",
                workflow_id=workflow_id,
                context={
                    "session_id": session_id,
                    "orchestrator_results": orchestrator_result,
                },
            )
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "type": "research",
            "confidence": orchestrator_result.get("confidence", 0.0),
            "result": orchestrator_result.get("result", {}),
            "documents": {},
            "agent_details": orchestrator_result.get("agent_results", []),
            "rounds": orchestrator_result.get("rounds_executed", 0),
        }

    # Document / diagram / upload intent → chạy Architect
    orchestrator = setup_orchestrator()
    architect = orchestrator._agent_registry.get("architect")

    if not architect:
        architect_result = {"success": False, "error": "Architect not available"}
    else:
        # Xác định formats theo intent
        if delivery_intent == DELIVERY_DIAGRAM:
            format_hint = "1. Markdown document\n2. Architecture diagram (DOT)\n3. PDF version"
        elif delivery_intent == DELIVERY_UPLOAD:
            format_hint = "1. Markdown document\n2. PDF version\n3. Upload to Google Drive"
        else:  # document
            format_hint = "1. Markdown document with clear structure\n2. PDF version\n3. Upload to Google Drive if configured"

        architect_task = f"""Generate professional documentation for the following task and results:

Original Task: {message}

Results:
{json.dumps(orchestrator_result.get('result', {}), indent=2, ensure_ascii=False)}

Create:
{format_hint}

Provide links and file paths.
"""
        architect_result = architect.execute(
            task=architect_task,
            workflow_id=workflow_id,
            context={
                "session_id": session_id,
                "orchestrator_results": orchestrator_result,
            },
        )
        logger.info("architect_completed", success=architect_result.get("success"))

    return {
        "workflow_id": workflow_id,
        "status": "completed",
        "type": "research",
        "confidence": orchestrator_result.get("confidence", 0.0),
        "result": orchestrator_result.get("result", {}),
        "documents": architect_result.get("result", {}),
        "agent_details": orchestrator_result.get("agent_results", []),
        "rounds": orchestrator_result.get("rounds_executed", 0),
    }


def execute_confirmed_action(
    workflow_id: str,
    action_id: str,
    session_id: str = None,
) -> Dict[str, Any]:
    """Resume a paused workflow after the user confirms a proposed action.

    Reads the saved workflow context (from workflow_states) and runs the
    appropriate delivery step. This is the human-in-the-loop resume entry point.
    """
    memory = get_memory_manager()
    logger.info("resuming_workflow", workflow_id=workflow_id, action_id=action_id)

    # Map action_id → delivery_intent
    action_map = {
        "create_pdf": DELIVERY_DOCUMENT,
        "create_docx": DELIVERY_DOCUMENT,
        "create_diagram": DELIVERY_DIAGRAM,
        "upload_drive": DELIVERY_UPLOAD,
        "notify_lark": DELIVERY_NOTIFY,
        "none": DELIVERY_NONE,
    }
    delivery_intent = action_map.get(action_id, DELIVERY_NONE)

    # Lấy context đã lưu từ workflow_states (short-term memory / DB)
    try:
        state = memory.get_workflow_state(workflow_id)
    except Exception:
        state = None

    if not state:
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": f"Workflow {workflow_id} not found or expired. Please re-submit your request.",
        }

    ctx = state.context if hasattr(state, "context") else {}
    # state có thể là dict (từ DB) hoặc WorkflowState object
    if isinstance(ctx, str):
        ctx = json.loads(ctx)

    original_message = ctx.get("original_task", "")
    orchestrator_result = {
        "success": True,
        "result": ctx.get("orchestrator_result", {}),
        "confidence": ctx.get("confidence", 0.8),
        "agent_results": ctx.get("agent_results", []),
        "rounds_executed": ctx.get("rounds", 0),
    }

    if delivery_intent == DELIVERY_NONE:
        # User chọn "không tạo gì thêm" → chỉ trả lại findings
        _save_workflow_state(
            workflow_id=workflow_id,
            status="completed",
            current_step="completed_no_delivery",
            context=ctx,
            memory=memory,
        )
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "type": "research",
            "confidence": orchestrator_result.get("confidence", 0.0),
            "result": orchestrator_result.get("result", {}),
            "documents": {},
            "agent_details": orchestrator_result.get("agent_results", []),
            "rounds": orchestrator_result.get("rounds_executed", 0),
        }

    # Cập nhật trạng thái → generating
    _save_workflow_state(
        workflow_id=workflow_id,
        status=WORKFLOW_GENERATING,
        current_step=f"generating_{delivery_intent}",
        context=ctx,
        memory=memory,
    )

    result = _execute_delivery(
        workflow_id=workflow_id,
        session_id=session_id or ctx.get("session_id", "default"),
        message=original_message,
        delivery_intent=delivery_intent,
        orchestrator_result=orchestrator_result,
    )

    # Cập nhật trạng thái → completed
    _save_workflow_state(
        workflow_id=workflow_id,
        status="completed",
        current_step="completed",
        context=ctx,
        memory=memory,
    )
    return result


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
        
        # Step 2: Extract tier + delivery intent from precheck
        task_tier = result_data.get("task_tier", TIER_QUICK_RESEARCH)
        delivery_intent = result_data.get("delivery_intent", DELIVERY_NONE)
        logger.info(
            "research_task_detected",
            workflow_id=workflow_id,
            task_tier=task_tier,
            delivery_intent=delivery_intent,
        )

        # Step 3: Run orchestrator (research / data gathering)
        logger.info("step_orchestrator", workflow_id=workflow_id)
        orchestrator = setup_orchestrator()

        orchestrator_result = orchestrator.execute(
            task=message,
            workflow_id=workflow_id,
            context={
                "session_id": session_id,
                "topic": result_data.get("topic"),
                "task_type": result_data.get("task_type"),
                "task_tier": task_tier,
                "delivery_intent": delivery_intent,
            }
        )

        # Step 4: Delivery gate — quyết định có tạo deliverable hay không
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

            # ── DELIVERY GATE ──────────────────────────────────────
            # Chỉ auto-tạo deliverable khi user yêu cầu RÕ (delivery_intent != none).
            # Ngược lại → trả findings + đề xuất options để user confirm (human-in-the-loop).
            auto_deliver = delivery_intent in (
                DELIVERY_DOCUMENT, DELIVERY_DIAGRAM, DELIVERY_UPLOAD, DELIVERY_NOTIFY
            )

            if auto_deliver:
                # User đã yêu cầu rõ → chạy Architect / Notification ngay
                return _execute_delivery(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    message=message,
                    delivery_intent=delivery_intent,
                    orchestrator_result=orchestrator_result,
                )
            else:
                # delivery_intent == none → trả findings + proposed_actions cho UI
                logger.info("awaiting_user_confirmation", workflow_id=workflow_id)
                proposed = _build_proposed_actions(task_tier)

                # Lưu workflow state để user có thể resume sau khi chọn action
                _save_workflow_state(
                    workflow_id=workflow_id,
                    status=WORKFLOW_AWAITING_CONFIRMATION,
                    current_step="awaiting_delivery_confirmation",
                    context={
                        "session_id": session_id,
                        "original_task": message,
                        "orchestrator_result": orchestrator_result.get("result", {}),
                        "task_tier": task_tier,
                        "delivery_intent": delivery_intent,
                    },
                    memory=memory,
                )

                return {
                    "workflow_id": workflow_id,
                    "status": "awaiting_confirmation",
                    "type": "research_with_options",
                    "task_tier": task_tier,
                    "confidence": orchestrator_result.get("confidence", 0.0),
                    "result": orchestrator_result.get("result", {}),
                    "proposed_actions": [a.model_dump() for a in proposed],
                    "agent_details": orchestrator_result.get("agent_results", []),
                    "rounds": orchestrator_result.get("rounds_executed", 0),
                }

        else:
            # Build rich error info from orchestrator result
            error_msg = orchestrator_result.get("error") or "Unknown error"
            error_type = orchestrator_result.get("error_type", "")
            tb = orchestrator_result.get("traceback", "")
            agent = orchestrator_result.get("agent", "orchestrator")

            logger.error(
                "orchestrator_failed",
                workflow_id=workflow_id,
                error=error_msg,
                error_type=error_type,
                agent=agent,
                traceback=tb
            )

            # Send full error to Lark — chỉ khi LARK_NOTIFICATION_ENABLED=true
            if config.LARK_NOTIFICATION_ENABLED and config.LARK_APP_ID and config.LARK_ERROR_CHAT_ID:
                _send_error_to_lark(
                    workflow_id=workflow_id,
                    task=message,
                    error=error_msg,
                    error_type=error_type,
                    agent=agent,
                    traceback=tb
                )

            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": error_msg,
                "error_type": error_type,
                "agent": agent,
                "traceback": tb,
                "details": orchestrator_result
            }
    
    except Exception as e:
        import traceback as _tb
        full_tb = _tb.format_exc()
        
        logger.error(
            "processing_failed",
            workflow_id=workflow_id,
            error=str(e),
            error_type=type(e).__name__,
            traceback=full_tb
        )
        
        if config.LARK_NOTIFICATION_ENABLED and config.LARK_APP_ID and config.LARK_ERROR_CHAT_ID:
            _send_error_to_lark(
                workflow_id=workflow_id,
                task=message,
                error=str(e),
                error_type=type(e).__name__,
                agent="process_message",
                traceback=full_tb
            )
        
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": full_tb
        }
    finally:
        # Clear working memory if auto-clear enabled
        if config.WORKING_MEMORY_AUTO_CLEAR:
            memory.clear_context(workflow_id)
            logger.debug("working_memory_cleared", workflow_id=workflow_id)