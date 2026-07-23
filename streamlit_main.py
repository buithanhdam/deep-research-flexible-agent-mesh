"""
Streamlit chat UI để test nhanh hệ multi-agent (gọi trực tiếp process_message() trong main.py).

Chạy:
    streamlit run streamlit_chat_app.py

Lưu ý: file này phải được đặt CÙNG THƯ MỤC với main.py (root của project),
để import "from main import process_message" hoạt động đúng.
"""

import uuid
import streamlit as st

from agent_flow import process_message  # import trực tiếp hàm xử lý chính của bạn

st.set_page_config(page_title="Agent Chat (Test)", page_icon="🤖", layout="wide")
st.title("🤖 Multi-Agent Chat - Test UI")

# --- Khởi tạo session state ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": str}

# Sidebar: thông tin session + nút reset
with st.sidebar:
    st.markdown("### Thông tin phiên")
    st.code(st.session_state.session_id, language=None)
    if st.button("🔄 Reset hội thoại"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

# --- Hiển thị lịch sử chat ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Xử lý input mới ---
user_input = st.chat_input("Nhập yêu cầu / câu hỏi cho agent...")

if user_input:
    # Hiển thị tin nhắn user
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Gọi hệ thống agent thật
    with st.chat_message("assistant"):
        with st.spinner("Agent đang xử lý... (có thể mất 1-2 phút với task research)"):
            try:
                result = process_message(
                    message=user_input,
                    session_id=st.session_state.session_id,
                )
            except Exception as e:
                result = {"status": "error", "error": str(e)}

        status = result.get("status")

        if status == "completed" and result.get("type") == "chat":
            content = result.get("response", "(không có phản hồi)")

        elif status == "completed" and result.get("type") == "research":
            content = (
                f"✅ **Hoàn thành** (confidence: {result.get('confidence', 0):.2f}, "
                f"rounds: {result.get('rounds', 0)})\n\n"
                f"**Kết quả:**\n```json\n{result.get('result', {})}\n```\n\n"
                f"**Tài liệu tạo ra:**\n```json\n{result.get('documents', {})}\n```"
            )

        elif status == "escalated":
            content = (
                f"⚠️ **Escalated** - {result.get('reason', 'Cần review')}\n\n"
                f"Confidence: {result.get('confidence', 0):.2f}"
            )

        elif status in ("error", "failed"):
            content = f"❌ **Lỗi**: {result.get('error', 'Unknown error')}"

        else:
            content = f"```json\n{result}\n```"

        st.markdown(content)

        # Hiện toàn bộ JSON raw trong expander để debug
        with st.expander("🔍 Raw result (debug)"):
            st.json(result)

    st.session_state.messages.append({"role": "assistant", "content": content})