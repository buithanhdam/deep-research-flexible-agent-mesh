"""Reusable rendering components for the Chainlit UI.

These helpers convert agent_flow result dicts into Chainlit messages,
images, and action buttons. Kept separate from chainlit_app.py so each
piece stays small and testable.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import chainlit as cl  # noqa: F401  (type-only; avoids "variable in type expr")

# Runtime import (may be None if chainlit not installed)
try:
    import chainlit as _cl
except ImportError:  # allow import without chainlit installed (for testing)
    _cl = None


def render_chat_response(result: Dict[str, Any]) -> Optional[Any]:
    """Render a simple chat response (Tier 0)."""
    if _cl is None:
        return None
    content = result.get("response", "(không có phản hồi)")
    return _cl.Message(content=content, author="assistant")


def render_research_findings(result: Dict[str, Any]) -> Any:
    """Render research findings (summary, sources, recommendations).

    Used for both 'awaiting_confirmation' and 'completed' research results.
    """
    res = result.get("result", {}) or {}
    confidence = res.get("confidence", result.get("confidence", 0))
    rounds = result.get("rounds", 0)
    task_tier = result.get("task_tier", "research")
    summary = res.get("summary", "").strip()
    recommendations = res.get("recommendations", [])
    sources = res.get("sources", [])

    parts: List[str] = []
    parts.append(f"🔬 **Kết quả research** (tier: `{task_tier}`, confidence: {confidence:.2f}, rounds: {rounds})\n")

    if summary:
        parts.append(f"**Tóm tắt:**\n{summary}\n")
    if recommendations:
        rec_lines = "\n".join(f"- {r}" for r in recommendations[:5])
        parts.append(f"**Khuyến nghị:**\n{rec_lines}\n")
    if sources:
        src_lines = "\n".join(f"- {s}" for s in sources[:8])
        parts.append(f"**Nguồn tham khảo:**\n{src_lines}\n")

    content = "\n".join(parts)
    return _cl.Message(content=content, author="assistant")


def render_documents(result: Dict[str, Any]) -> Any:
    """Render document/deliverable info from an Architect result."""
    docs = result.get("documents", {}) or {}
    created = docs.get("documents_created", [])
    uploaded = docs.get("uploaded_files", [])

    parts: List[str] = ["✅ **Đã hoàn thành deliverable**\n"]

    for doc in created:
        parts.append(f"📄 **{doc.get('title', 'Untitled')}** — `{doc.get('file_path', '')}`")

    for up in uploaded:
        if up.get("link"):
            parts.append(f"🔗 [Xem tài liệu]({up['link']})")

    if not created and not uploaded:
        parts.append("_Không tạo tài liệu thêm (theo lựa chọn của bạn)._")

    return _cl.Message(content="\n".join(parts), author="assistant")


def render_error(result: Dict[str, Any]) -> Any:
    """Render an error response."""
    error = result.get("error", "Unknown error")
    return _cl.Message(content=f"❌ **Lỗi**: {error}", author="assistant")


def render_escalated(result: Dict[str, Any]) -> Any:
    """Render an escalated response."""
    reason = result.get("reason", "Cần review")
    confidence = result.get("confidence", 0)
    return _cl.Message(
        content=f"⚠️ **Escalated** — {reason}\n\nConfidence: {confidence:.2f}",
        author="assistant",
    )


def build_action_buttons(
    proposed_actions: List[Dict[str, Any]],
    workflow_id: str,
    callback=None,
) -> List[Any]:
    """Build Chainlit Action buttons for proposed deliverable options.

    Each action's `value` encodes both the workflow_id and action_id so the
    callback can resume the correct workflow.

    Args:
        proposed_actions: List of action dicts from the agent pipeline.
        workflow_id: The workflow to resume when an action is clicked.
        callback: Async callback function invoked on click (receives cl.Action).
    """
    if _cl is None:
        return []

    actions = []
    for action in proposed_actions:
        aid = action.get("action_id", "")
        label = action.get("label", aid)
        desc = action.get("description", "")
        # Encode: "resume::<workflow_id>::<action_id>"
        payload_str = f"resume::{workflow_id}::{aid}"
        # Chainlit Action requires `payload` (not `value`).
        # Some versions accept a dict, others a string — use dict for safety.
        kwargs = {"name": label, "payload": {"data": payload_str}, "description": desc}
        if callback is not None:
            kwargs["callback"] = callback
        actions.append(_cl.Action(**kwargs))
    return actions


def render_image_if_exists(file_path: str) -> Optional[Any]:
    """Render an image (chart/mindmap/diagram) if the file exists."""
    if _cl is None:
        return None
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        name = os.path.basename(file_path)
        return _cl.Image(name=name, path=file_path, display="inline")
    except Exception:
        return None


def render_delivery_result(result: Dict[str, Any]) -> List[Any]:
    """Render the result of a confirmed action (resume).

    Returns a list of Chainlit elements (Message + optional Image).
    """
    status = result.get("status")
    elements: List[Any] = []

    if status == "completed":
        elements.append(render_documents(result))

        # Check for generated images (charts, mindmaps, diagrams)
        docs = result.get("documents", {}) or {}
        for doc in docs.get("documents_created", []):
            fp = doc.get("file_path", "")
            if fp.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                img = render_image_if_exists(fp)
                if img:
                    elements.append(img)
    elif status in ("error", "failed"):
        elements.append(render_error(result))
    else:
        elements.append(_cl.Message(content=f"```json\n{result}\n```", author="assistant"))

    return elements
