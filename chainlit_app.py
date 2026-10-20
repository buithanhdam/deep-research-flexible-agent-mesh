"""Chainlit chat UI for the Agent System.

Replaces streamlit_main.py with an LLM-native interface that supports:
  • Tier-based routing (chat / quick_research / deep_research / multi_domain)
  • Human-in-the-loop delivery gate (proposed actions as clickable buttons)
  • Image rendering for charts / mindmaps / diagrams
  • Step-by-step agent execution visibility

Run:
    chainlit run chainlit_app.py

NOTE: This file lives at the project root so that `agent_flow`
and `src.*` imports resolve correctly.
"""

from __future__ import annotations

import os
import sys
import uuid
import json

# Ensure project root is on sys.path (this file IS at project root)
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import chainlit as cl

from agent_flow import process_message, execute_confirmed_action
from ui.components import (
    render_chat_response,
    render_research_findings,
    render_documents,
    render_error,
    render_escalated,
    build_action_buttons,
    render_delivery_result,
    render_image_if_exists,
)


# ─────────────────────────────────────────────
# Session lifecycle
# ─────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session."""
    session_id = str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)

    await cl.Message(
        content=(
            "🤖 **Multi-Agent Chat** đã sẵn sàng!\n\n"
            "Hệ thống sẽ tự phân loại yêu cầu của bạn:\n"
            "- **Chat**: hỏi đáp nhanh → trả lời trực tiếp\n"
            "- **Quick research**: tra cứu → trả findings + đề xuất options\n"
            "- **Deep research**: nghiên cứu sâu → đề xuất deliverables để bạn chọn\n\n"
            "Gõ yêu cầu của bạn bên dưới 👇"
        ),
        author="assistant",
    ).send()


# ─────────────────────────────────────────────
# Human-in-the-loop: proposed action callback
# ─────────────────────────────────────────────

async def on_proposed_action(action: cl.Action):
    """Handle a proposed-action button click — resume the paused workflow.

    action.payload encodes: {"data": "resume::<workflow_id>::<action_id>"}
    """
    # payload can be a dict or a string depending on Chainlit version
    payload = action.payload or ""
    if isinstance(payload, dict):
        value = payload.get("data", "")
    else:
        value = str(payload)
    parts = value.split("::")

    if len(parts) != 3 or parts[0] != "resume":
        await cl.Message(content="⚠️ Không thể xử lý lựa chọn này.", author="assistant").send()
        return

    workflow_id = parts[1]
    action_id = parts[2]
    session_id = cl.user_session.get("session_id")

    async with cl.Step(name=f"Executing: {action_id}", type="run") as step:
        step.input = f"workflow={workflow_id}, action={action_id}"
        try:
            result = execute_confirmed_action(
                workflow_id=workflow_id,
                action_id=action_id,
                session_id=session_id,
            )
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        step.output = result.get("status", "unknown")

    # Render the delivery result (message + optional images)
    elements = render_delivery_result(result)
    for elem in elements:
        if hasattr(elem, "send"):
            await elem.send()
        else:
            # Image elements need to be attached to a message
            await cl.Message(content="", elements=[elem]).send()


# ─────────────────────────────────────────────
# Main message handler
# ─────────────────────────────────────────────

@cl.on_message
async def on_message(message: cl.Message):
    """Handle an incoming user message through the agent pipeline."""
    session_id = cl.user_session.get("session_id", "default")
    user_text = message.content

    # Run the pipeline (sync call — wrapped in step for visibility)
    async with cl.Step(name="Agent Pipeline", type="run") as step:
        step.input = user_text[:200]
        try:
            result = process_message(
                message=user_text,
                session_id=session_id,
            )
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        step.output = result.get("status", "unknown")

    status = result.get("status")
    result_type = result.get("type")

    # ── Tier 0: Chat ──────────────────────────────
    if status == "completed" and result_type == "chat":
        msg = render_chat_response(result)
        if msg:
            await msg.send()
        return

    # ── Human-in-the-loop: awaiting confirmation ──
    if status == "awaiting_confirmation" and result_type == "research_with_options":
        findings_msg = render_research_findings(result)
        await findings_msg.send()

        # Build action buttons
        proposed = result.get("proposed_actions", [])
        workflow_id = result.get("workflow_id", "")
        actions = build_action_buttons(proposed, workflow_id, callback=on_proposed_action)

        if actions:
            await cl.Message(
                content="**Bạn muốn làm gì tiếp theo?** Chọn một option 👇",
                author="assistant",
                actions=actions,
            ).send()
        return

    # ── Completed research (auto-delivered) ───────
    if status == "completed" and result_type == "research":
        findings_msg = render_research_findings(result)
        await findings_msg.send()

        docs = result.get("documents", {}) or {}
        if docs.get("documents_created") or docs.get("uploaded_files"):
            doc_msg = render_documents(result)
            await doc_msg.send()

            # Render any generated images
            for doc in docs.get("documents_created", []):
                fp = doc.get("file_path", "")
                if fp.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                    img = render_image_if_exists(fp)
                    if img:
                        await cl.Message(content="", elements=[img]).send()
        return

    # ── Escalated ─────────────────────────────────
    if status == "escalated":
        await render_escalated(result).send()
        return

    # ── Error / failed ────────────────────────────
    if status in ("error", "failed"):
        await render_error(result).send()
        return

    # ── Fallback: raw JSON ────────────────────────
    await cl.Message(
        content=f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```",
        author="assistant",
    ).send()
