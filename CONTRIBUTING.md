# CONTRIBUTING.md — Trạng thái & Kế hoạch phát triển

File này dùng để **theo dõi tiến độ thực tế của project qua các version**. Cập nhật file này mỗi khi hoàn thành 1 bước — README.md không nhắc lại nội dung này, chỉ mô tả cách dùng hệ thống ở trạng thái hiện tại.

---

## 🔖 Trạng thái hiện tại

**Version**: 1.0.0 (Production Ready)
**Step**: Toàn bộ roadmap MVP → Production đã hoàn thành. Hệ thống chạy end-to-end với tool thật, persistence thật, và multi-agent routing đầy đủ.
**Cập nhật lần cuối**: _(điền ngày bạn sửa file này)_

### Đã implement ở version này

**Core**
- Precheck agent (lọc chat / research)
- Orchestrator agent (multi-round, evaluate & continue, max 3 rounds)
- Research / Data / Notification / Architect agent — gọi tool thật, không còn chỉ dựa vào LLM knowledge
- OpenRouter client (retry, JSON mode)
- CLI entry point, output JSON chuẩn cho n8n

**Tools thật (15 tools)**
- `search_engine.py` — Tavily + DuckDuckGo fallback
- `web_extract.py` — web scraping
- JsonProcessorTool, FileExtractorTool (PDF/DOCX/TXT)
- Document generation: Markdown, PDF (WeasyPrint), DOCX (pypandoc), Diagrams (Graphviz)
- Google Drive Upload/Download (service account)
- Lark: Send Message (text/post), File Upload/Download, error notifications

**Memory — 3 lớp, hoạt động đầy đủ**
- Working memory (in-memory, chia sẻ context giữa agent trong 1 workflow)
- Short-term memory — lưu thật vào Postgres (`workflow_states`, `agent_executions`), hỗ trợ resume khi lỗi
- Long-term memory — cache kết quả confidence cao (TTL cấu hình được), agent performance stats

**Persistence**
- `postgres_client.py` — CRUD đầy đủ, không còn là interface rỗng
- Schema: `workflow_states`, `agent_executions`, `chat_messages`, `cached_results`
- Auto cleanup cho dữ liệu cũ

---

## 🗺️ Roadmap tiếp theo (sau production)

Các mục dưới đây là cải tiến sau khi hệ thống đã production-ready, không phải điều kiện để coi là "hoàn thành".

### Version 1.1.0 — Sub-agents chuyên biệt
**Mục tiêu**: Agent-as-tool pattern cho các domain cụ thể.

- [ ] `src/agents/sub_agents/lark_research_agent.py`
- [ ] `src/agents/sub_agents/n8n_workflow_research_agent.py`
- [ ] `src/agents/sub_agents/code_architect_agent.py`
- [ ] Orchestrator route task tới đúng sub-agent (mở rộng orchestrator_prompt.py)

### Version 1.2.0 — Hiệu năng & vận hành nâng cao
- [ ] Parallel task execution trong orchestrator (hiện đang chạy tuần tự)
- [ ] Rate limiting cho OpenRouter calls
- [ ] Input validation kỹ hơn ở `main.py`
- [ ] Performance metrics / monitoring nâng cao (hiện đã có agent performance stats cơ bản)
- [ ] Authentication layer nếu expose qua HTTP (hiện tại chỉ CLI nên chưa cần)
- [ ] Phân loại lỗi chi tiết hơn thay vì error dict đơn giản

---

## 🐛 Known issues

- Orchestrator chạy task tuần tự, chưa parallelize
- Chưa có rate limiting cho OpenRouter → có thể hit giới hạn nếu gọi dồn dập
- Chưa có authentication layer (chỉ dùng qua CLI/n8n nội bộ)
- Error handling còn ở mức cơ bản, chưa phân loại theo mức độ nghiêm trọng

---

## ✅ Quy trình cập nhật file này

Khi hoàn thành 1 task trong roadmap:
1. Đánh dấu `- [x]` cho task đó
2. Nếu cả 1 version hoàn thành → chuyển mục đó lên phần **Trạng thái hiện tại**, đổi số version, xóa phần roadmap version đó
3. Ghi ngày cập nhật