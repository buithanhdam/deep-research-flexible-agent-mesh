"""Pydantic output models for all agent responses."""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Precheck Agent
# ─────────────────────────────────────────────

class PrecheckOutput(BaseModel):
    is_pass: bool = Field(..., description="True if task should go to orchestrator")
    topic: str = Field(..., description="Brief topic description, max 10 words")
    task_type: Literal["chat", "research", "integration", "build", "data"] = Field(...)
    # Tier phân loại độ phức tác — quyết định flow xử lý
    task_tier: Literal["chat", "quick_research", "deep_research", "multi_domain"] = Field(
        default="quick_research",
        description="Complexity tier: chat=trả lời nhanh, quick_research=tra cứu, "
                    "deep_research=nghiên cứu sâu, multi_domain=project nhiều chủ đề"
    )
    # Delivery intent — user có yêu cầu rõ deliverable (file/notify) không?
    delivery_intent: Literal["none", "document", "diagram", "notify", "upload"] = Field(
        default="none",
        description="none=chỉ cần câu trả lời, document=tạo PDF/MD/DOCX, "
                    "diagram=tạo sơ đồ, notify=gửi thông báo, upload=upload lên Drive"
    )
    response: str = Field(default="", description="Direct reply if chat, empty if research")
    language: str = Field(default="en", description="Detected language of the message")


# ─────────────────────────────────────────────
# Proposed Action — option đề xuất cho user (human-in-the-loop)
# ─────────────────────────────────────────────

class ProposedAction(BaseModel):
    """Một option deliverable đề xuất cho user sau khi research xong."""
    action_id: str = Field(..., description="ID ngắn để user chọn, vd: 'create_pdf'")
    label: str = Field(..., description="Nhãn hiển thị trên UI, vd: 'Tạo tài liệu PDF'")
    description: str = Field(default="", description="Mô tả ngắn kết quả khi chọn")
    action_type: Literal["create_document", "create_diagram", "notify", "upload_drive", "none"] = Field(...)
    formats: List[str] = Field(default_factory=list, description="Định dạng: markdown/pdf/docx")


# ─────────────────────────────────────────────
# Orchestrator Agent
# ─────────────────────────────────────────────

class OrchestratorDecision(BaseModel):
    action: Literal["execute_agent", "complete", "escalate"]
    next_agent: Optional[Literal["research", "data", "notification"]] = None
    next_task: Optional[str] = None
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    assessment: "OrchestratorAssessment"


class OrchestratorAssessment(BaseModel):
    is_complete: bool
    missing_info: List[str] = Field(default_factory=list)
    quality: Literal["high", "medium", "low"]


class OrchestratorFinalOutput(BaseModel):
    summary: str
    details: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    completeness: Literal["complete", "partial", "insufficient"]
    recommendations: List[str] = Field(default_factory=list)


OrchestratorDecision.model_rebuild()


# ─────────────────────────────────────────────
# Research Agent
# ─────────────────────────────────────────────

class ResearchFinding(BaseModel):
    source: str
    title: str
    content: str
    relevance: Literal["high", "medium", "low"]
    verified: bool = False


class ResearchOutput(BaseModel):
    research_type: Literal["general", "technical", "integration", "code"]
    findings: List[ResearchFinding] = Field(default_factory=list)
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    needs_more_search: bool = Field(default=False)
    suggested_queries: List[str] = Field(
        default_factory=list,
        description="Retry queries if current results are insufficient"
    )


# ─────────────────────────────────────────────
# Data Agent
# ─────────────────────────────────────────────

class DataOutput(BaseModel):
    processed_data: Dict[str, Any] = Field(default_factory=dict)
    analysis: str
    statistics: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    data_quality: Literal["good", "partial", "poor"] = "good"
    warnings: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Notification Agent
# ─────────────────────────────────────────────

class NotificationContent(BaseModel):
    title: str
    message: str
    priority: Literal["high", "medium", "low"]
    type: Literal["success", "info", "warning", "error"]
    actions: List[str] = Field(default_factory=list)


class NotificationOutput(BaseModel):
    notification: NotificationContent
    channels: List[Literal["lark", "email"]] = Field(default_factory=lambda: ["lark"])
    confidence: float = Field(..., ge=0.0, le=1.0)
    lark_receive_id: Optional[str] = None
    formatted_blocks: Optional[List[Any]] = None


# ─────────────────────────────────────────────
# Architect Agent
# ─────────────────────────────────────────────

class DocumentInfo(BaseModel):
    type: Literal["markdown", "pdf", "docx"]
    file_path: str
    title: str
    size_bytes: Optional[int] = None


class UploadedFile(BaseModel):
    filename: str
    service: Literal["google_drive", "lark"]
    link: Optional[str] = None
    file_id: Optional[str] = None
    file_key: Optional[str] = None


class ArchitectPlan(BaseModel):
    """Plan to generate before executing tools."""
    document_title: str
    sections: List["ArchitectSection"]
    output_formats: List[Literal["markdown", "pdf", "docx"]] = ["markdown", "pdf"]
    include_diagram: bool = False
    diagram_description: Optional[str] = None
    upload_to_drive: bool = True
    notify_lark: bool = True


class ArchitectSection(BaseModel):
    heading: str
    content_description: str
    level: int = Field(default=2, ge=1, le=4)


class ArchitectOutput(BaseModel):
    documents_created: List[DocumentInfo] = Field(default_factory=list)
    uploaded_files: List[UploadedFile] = Field(default_factory=list)
    summary: str
    tool_calls_made: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


ArchitectPlan.model_rebuild()
