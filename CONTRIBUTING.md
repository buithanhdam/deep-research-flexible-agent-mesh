# CONTRIBUTING.md — Trạng thái & Kế hoạch phát triển

File này dùng để **theo dõi tiến độ thực tế của project qua các version**. Cập nhật file này mỗi khi hoàn thành 1 bước — README.md không nhắc lại nội dung này, chỉ mô tả cách dùng hệ thống ở trạng thái hiện tại.

---

## 🔖 Trạng thái hiện tại

**Version**: 0.1.0 (MVP)
**Step**: MVP hoàn chỉnh — chạy được end-to-end qua CLI, chưa có persistence/tool thật.
**Cập nhật lần cuối**: _(điền ngày bạn sửa file này)_

### Đã implement ở version này
- Precheck agent (lọc chat / research)
- Orchestrator agent (decompose & delegate)
- Research / Data / Notification agent (chỉ dùng LLM knowledge, chưa gọi tool ngoài)
- Memory manager 3 lớp — **working memory (in-memory) hoạt động**, short/long-term mới có interface, chưa lưu thật
- OpenRouter client (retry, JSON mode)
- Postgres client (khởi tạo được, chưa dùng để persist)
- CLI entry point, output JSON chuẩn cho n8n

---

## 🗺️ Kế hoạch các version tiếp theo

### Version 0.2.0 — Tools thật
**Mục tiêu**: Research agent lấy được thông tin thật từ internet thay vì chỉ dùng LLM knowledge.

- [ ] `src/tools/search_engine.py` — web search (tavily, duckduckgo và các search engine free để fallback,domain scoping theo prompt template)
- [ ] `src/tools/web_extract.py` — extract nội dung từ URL kết quả search (sse, rss, bs4, giả lập trình duyệt,...)
- [ ] Cập nhật `research_agent.py` để gọi 2 tool trên qua tool-calling
- [ ] Cập nhật `research_agent_prompt.py` để agent biết khi nào cần gọi tool
- **Cần quyết định trước khi code**: dùng search API nào (Serper, Tavily, Brave Search API...)? có giới hạn domain không?

### Version 0.3.0 — Database persistence
**Mục tiêu**: Memory không mất khi restart; lưu được lịch sử chat theo session.

- [ ] Thiết kế schema (bảng `workflow_states`, `agent_executions`, `chat_messages`, `cached_results` — map theo `src/memory/models.py`)
- [ ] Implement các hàm CRUD thật trong `postgres_client.py` (hiện tại chỉ có connection, chưa có query)
- [ ] Nối `memory_manager.py` short-term/long-term layer vào DB thay vì no-op
- [ ] Thêm cache layer (tránh gọi lại LLM cho câu hỏi giống hệt trong session)
- **Cần quyết định trước**: Postgres thuần? TTL cho short-term memory là bao lâu?

### Version 0.4.0 — Sub-agents chuyên biệt
**Mục tiêu**: Agent-as-tool pattern cho các domain cụ thể.

- [ ] `src/agents/sub_agents/lark_research_agent.py`
- [ ] `src/agents/sub_agents/n8n_workflow_research_agent.py`
- [ ] `src/agents/sub_agents/code_architect_agent.py`
- [ ] Orchestrator cần biết route task tới đúng sub-agent (mở rộng orchestrator_prompt.py)

### Version 0.5.0 — Vận hành ổn định (production-readiness)
- [ ] Parallel task execution trong orchestrator (hiện đang chạy tuần tự)
- [ ] Rate limiting cho OpenRouter calls
- [ ] Input validation kỹ hơn ở `main.py`
- [ ] Performance metrics / monitoring cơ bản
- [ ] Authentication layer nếu expose qua HTTP (hiện tại chỉ CLI nên chưa cần)

---

## 🐛 Known issues (đang tồn tại ở version hiện tại)

- Research agent trả lời dựa trên kiến thức có sẵn của LLM, không phải thông tin real-time
- Memory mất hết khi process kết thúc (chỉ in-memory)
- Không có rate limiting → dễ hit giới hạn OpenRouter nếu gọi nhiều
- Lỗi chỉ trả về error dict đơn giản, chưa phân loại lỗi

---

## ✅ Quy trình cập nhật file này

Khi hoàn thành 1 task trong roadmap:
1. Đánh dấu `- [x]` cho task đó
2. Nếu cả 1 version hoàn thành → chuyển mục đó lên phần **Trạng thái hiện tại**, đổi số version, xóa phần roadmap version đó
3. Ghi ngày cập nhật