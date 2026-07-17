# agent-mesh-task-decomposition

Hệ thống multi-agent Python (CLI, không cần API server/Docker) theo Design Spec v3: lọc chat vs research, điều phối nhiều agent chuyên biệt, quản lý memory 3 lớp, output JSON cho n8n.

> **Trạng thái**: MVP hoàn chỉnh — chạy được end-to-end. Chưa có: web search thật, database persistence, sub-agents chuyên biệt, parallel execution (xem [Roadmap](#roadmap--giới-hạn-hiện-tại)).

---

## Kiến trúc

```
USER INPUT (n8n)
      │
      ▼
Precheck Agent ──────► lọc chat / research
      │ (nếu research)
      ▼
Orchestrator Agent ───► decompose & delegate
      │
  ┌───┴────────┬─────────────┐
  ▼            ▼             ▼
Research     Data        Notification
 Agent       Agent          Agent
  │            │             │
  └────────────┴──────┬──────┘
                       ▼
              Memory Manager (3 layers)
                       ▼
             Supabase / PostgreSQL
                       ▼
                 JSON OUTPUT ──► n8n
```

## Cấu trúc thư mục

```
project-root/
├── src/
│   ├── agents/
│   │   ├── base_agent.py, precheck_agent.py, orchestrator_agent.py
│   │   ├── research_agent.py, data_agent.py, notification_agent.py
│   │   └── sub_agents/            (trống — Phase 2)
│   ├── llm/openrouter_client.py
│   ├── db/supabase_client.py, postgres_client.py
│   ├── memory/models.py, memory_manager.py
│   ├── tools/                     (trống — Phase 2)
│   ├── prompt_templates/          (4 template + _STANDARD_TEMPLATE.md)
│   ├── config.py, constants.py, logger.py, main.py
├── test_system.py                 verification script
├── demo.py                        demo không cần API key
├── setup.py                       setup tự động
├── requirements.txt
└── .gitignore
```

## Cài đặt

```bash
# 1. Tạo & kích hoạt virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\Activate.ps1       # Windows PowerShell

# 2. Cài dependencies (hoặc chạy python setup.py để làm tự động cả bước 1-3)
pip install -r requirements.txt

# 3. Tạo file .env ở thư mục root
```

`.env`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here   # bắt buộc — lấy tại https://openrouter.ai/
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet
LOG_LEVEL=INFO

# Tùy chọn — để trống nếu chưa cần persist memory
POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

```

## Chạy nhanh

```bash
python test_system.py                          # kiểm tra setup (imports, config, agents)
python demo.py                                  # xem demo, không cần API key

python -m src.main --task "Hello"                                    # chat
python -m src.main --task "How to use n8n with Python?"               # research
python -m src.main --task "What is OpenRouter?" --session-id user123  # có session tracking

python -m src.main --task "test" 2>&1           # xem log (log ghi ra stderr)
```

## Output format

Mọi output nằm giữa marker `@@JSON_START@@` / `@@JSON_END@@` để n8n dễ parse.

```json
// chat
{"status": "completed", "type": "chat", "response": "..."}

// research
{
  "status": "completed", "type": "research", "confidence": 0.85,
  "result": {"summary": "...", "details": "...", "sources": ["..."]}
}

// escalated (confidence thấp)
{"status": "escalated", "reason": "...", "confidence": 0.45, "partial_results": {...}}
```

## Tích hợp n8n

```
Lark Trigger → Execute Command (python -m src.main --task "{{ $json.message }}")
             → Extract JSON (giữa 2 marker)
             → If status == "completed" → Lark: gửi kết quả
             → Else (escalated)         → Telegram: báo admin
```

## Roadmap / giới hạn hiện tại

| Đã có (MVP) | Chưa có (Phase 2) |
|---|---|
| Precheck, Orchestrator, Research/Data/Notification agent | Web search & extract tool thật (research agent hiện chỉ dùng LLM knowledge) |
| Memory manager 3 lớp (working in-memory; short/long-term interface sẵn sàng) | Database persistence thật (Supabase/Postgres đã có client) |
| OpenRouter client + retry | Sub-agents chuyên biệt (Lark, n8n, Code architect) |
| JSON output chuẩn cho n8n | Parallel task execution, caching nâng cao, performance monitoring |
| Structured logging (stderr) | Rate limiting, authentication, input validation kỹ hơn |

**Phù hợp cho**: local testing, dev workflow, proof of concept, test tích hợp n8n.
**Chưa phù hợp cho**: production nhiều traffic, multi-user, workflow quan trọng cần monitoring.

## Troubleshooting

| Lỗi | Cách xử lý |
|---|---|
| `OpenRouter API key is required` | Kiểm tra `.env` đã có `OPENROUTER_API_KEY` chưa |
| Import module thất bại | Đảm bảo đã activate virtualenv, chạy lại `pip install -r requirements.txt` |
| Lỗi kết nối database | Không bắt buộc cho MVP — để trống `POSTGRES SETUP`, hệ thống vẫn chạy (không lưu memory) |
| Không thấy log | Log ghi ra stderr, không phải stdout — chạy với `2>&1` để xem |