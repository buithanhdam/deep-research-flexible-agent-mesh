# 🤖 Multi-Agent Task Decomposition System

**Production-ready multi-agent system** với function calling, 26 tools, human-in-the-loop delivery gate, tier-based task routing, multi-round orchestration, và full memory management.

> ✅ **Status**: Production Ready | Function Calling ✅ | 26 Tools ✅ | Human-in-the-Loop ✅ | Chainlit UI ✅ | Memory System ✅

---

## ✨ Highlights

- 🎯 **7 Specialized Agents** with automatic tool selection
- 🛠️ **26 Production Tools**: Search, Research, Visualization, Document Gen, Lark, Google Drive
- 🧑‍💻 **Human-in-the-Loop Delivery Gate**: Research xong → đề xuất options → user confirm mới tạo tài liệu
- 📊 **Tier-Based Task Routing**: chat / quick_research / deep_research / multi_domain
- 🔄 **Multi-Round Orchestration**: Auto evaluate & continue
- 🧠 **3-Layer Memory**: Working/Short-term/Long-term with caching
- 💬 **Chainlit UI**: LLM-native chat interface with action buttons + step visibility
- 📱 **Lark Integration**: Optional (tắt mặc định để tránh duplicate với UI)
- 📊 **Google Drive**: Upload/download with service account
- 🔍 **Web Search**: Tavily API + DuckDuckGo fallback
- 📄 **Document Generation**: MD/PDF/DOCX/Diagrams/Charts/Mindmaps
- 💾 **PostgreSQL Persistence**: Full workflow & chat history in schema `bingx_agent_mesh` (no extra tables)

---

## 🚀 Quick Start

```bash
# 1. Clone & Setup
git clone https://github.com/buithanhdam/agent-mesh-task-decomposition
cd agent-mesh-task-decomposition
python setup.py

# 2. Configure .env (see Configuration section)

# 3. Initialize Database
python scripts/init_database.py

# 4. Run CLI
python main.py --task "Research Python and create PDF guide" --session-id user123

# 5. Or run Chainlit UI (recommended for chat)
chainlit run chainlit_app.py
```

---

## 📦 Installation

### Step 1: Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Upgrade Pip
pip install --upgrade pip
# Install packages
pip install -r requirements.txt
```

### Step 2: External Dependencies

```bash
# For PDF generation (WeasyPrint)
# Linux:
sudo apt-get install python3-dev python3-pip python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Mac:
brew install cairo pango gdk-pixbuf libffi

# For DOCX generation
# Linux: sudo apt-get install pandoc
# Mac: brew install pandoc

# For Diagrams & Mindmaps
# Linux: sudo apt-get install graphviz
# Mac: brew install graphviz
```

### Step 3: Configuration

Create `.env` file:

```bash
cp .env.example .env
```

`.env` Config:

```env
# ============================================
# REQUIRED
# ============================================
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=anthropic/claude-haiku-4.5
TAVILY_API_KEY=tvly-xxx
MAX_RETRIES=3
TIMEOUT_SECONDS=120
AGENT_LOOP_MAX_ROUNDS=5
# ==== Logging ====
LOG_LEVEL=INFO
APP_ENV=dev

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=multi_agent_db
POSTGRES_SCHEMA=bingx_agent_mesh  # Schema riêng, tránh conflict với app khác

# ============================================
# OPTIONAL (but recommended)
# ============================================

# Lark — tắt notification mặc định (tránh duplicate với UI chat)
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
LARK_ERROR_CHAT_ID=oc_xxx
LARK_NOTIFICATION_ENABLED=false  # Bật true khi chạy headless (n8n/cron)

# GitHub API — tăng rate limit (optional, 60→5000 req/h)
GITHUB_TOKEN=ghp_xxx

# Google Drive
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_CREDENTIALS_JSON=credentials/service-account.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id

# Memory
CACHE_DEFAULT_TTL_HOURS=24
CHAT_HISTORY_MAX_MESSAGES=10
AUTO_CLEANUP_ENABLED=true
CHAT_HISTORY_RETENTION_DAYS=30
```

Set up Drive Credentials:

- Create `credentials/` folder
- Put json file in this folder

### Step 4: Initialize Database

```bash
# If DB already initialized skip this cmd
python scripts/init_database.py
```

### Step 5: Verify

```bash
python tests/test_system.py
```

---

## 🎮 Usage

### CLI

```bash
# Simple chat (Tier 0 — trả lời trực tiếp)
python main.py --task "Hello"

# Research task (Tier 1/2 — trả findings + đề xuất options)
python main.py --task "How to build a REST API with FastAPI?" --session-id user123

# Explicit document request (auto-tạo, không cần confirm)
python main.py --task "Research multi-agent systems, create PDF guide, upload to Google Drive" --session-id project_001
```

### Chainlit UI (recommended)

```bash
chainlit run chainlit_app.py
```

UI mở tại `http://localhost:8000`. Hỗ trợ:
- Action buttons cho human-in-the-loop (click chọn deliverable)
- Step-by-step agent execution visibility
- Image inline (charts, mindmaps, diagrams)

### Management Scripts

```bash
# View statistics
python scripts/view_memory_stats.py

# View chat history
python scripts/view_session.py user123

# Cleanup old data
python scripts/cleanup_memory.py
```

---

## 🏗️ Architecture

```
User Message
    ↓
┌─────────────────────────┐
│   Precheck Agent        │  Classify: chat vs task
│   • task_tier           │  → chat / quick_research / deep_research / multi_domain
│   • delivery_intent     │  → none / document / diagram / notify / upload
└───────────┬─────────────┘
            ↓ (if task)
┌─────────────────────────┐
│ Orchestrator (Manager)  │
│  • Multi-round execution│
│  • Evaluate & Continue  │
└───────────┬─────────────┘
            ↓
┌───────┬────────┬────────┐
│Research│ Data   │ Notif. │
│ Agent  │ Agent  │ Agent  │
│11 tools│7 tools │2 tools │
└───────┴────────┴────────┘
            ↓
┌─────────────────────────┐
│  DELIVERY GATE           │  ← Human-in-the-loop
│  delivery_intent=none?   │
│  YES → proposed_actions  │  → user chọn → resume
│  NO  → auto Architect    │
└───────────┬─────────────┘
            ↓ (if document/diagram/upload)
┌─────────────────────────┐
│   Architect Agent       │
│ •Generate MD/PDF/DOCX   │
│ •Charts/Mindmaps        │
│ •Upload to Drive        │
└─────────────────────────┘
            ↓
      JSON Output → UI / n8n

[On Error] → Lark Notification (if LARK_NOTIFICATION_ENABLED=true)
```

---

## 🧑‍💻 Human-in-the-Loop Delivery Gate

Hệ thống **không tự động tạo tài liệu** mỗi lần có task research. Thay vào đó:

1. **Research xong** → trả findings (summary, sources, recommendations)
2. **Đề xuất options** qua `proposed_actions`:
   - 📄 Tạo tài liệu PDF
   - 📝 Tạo tài liệu DOCX
   - 📊 Tạo sơ đồ kiến trúc
   - ☁️ Tạo PDF & upload Google Drive *(nếu Drive configured)*
   - 💬 Gửi kết quả qua Lark *(nếu LARK_NOTIFICATION_ENABLED=true)*
   - ✅ Chỉ giữ kết quả research
3. **User chọn** → pipeline **resume** workflow → tạo deliverable

**Ngoại lệ**: Nếu user yêu cầu RÕ (`delivery_intent != none`, vd: "tạo PDF báo cáo") → auto-tạo luôn, không cần confirm.

### Resume API

```python
from agent_flow import execute_confirmed_action

result = execute_confirmed_action(
    workflow_id="uuid-from-previous-research",
    action_id="create_pdf",  # or: create_docx, create_diagram, upload_drive, notify_lark, none
    session_id="user123",
)
```

Workflow state lưu trong `workflow_states.context` JSONB — **không thêm bảng mới**.

---

## 📊 Task Tier Classification

Precheck Agent phân loại mỗi message theo 4 tier:

| Tier | Khi nào | Hành vi |
|------|---------|---------|
| `chat` | Hỏi đáp nhanh, small talk | Trả lời trực tiếp, không qua pipeline |
| `quick_research` | Tra cứu, verify, so sánh 2-3 thứ | Research → trả findings + đề xuất options |
| `deep_research` | Nghiên cứu sâu, cần 3+ nguồn | Research sâu → đề xuất deliverables |
| `multi_domain` | Project nhiều chủ đề | (Task decomposition — planned) |

---

## 🛠️ Tools (26)

### Original Tools (15)

| Category | Tools |
|----------|-------|
| **Search** | WebSearchTool (Tavily + DuckDuckGo), WebScrapeTool |
| **Data** | JsonProcessorTool, FileExtractorTool (PDF/DOCX/TXT) |
| **Documents** | Markdown, PDF (WeasyPrint), DOCX (pypandoc), Diagrams (Graphviz) |
| **Cloud** | Google Drive Upload/Download |
| **Lark** | Send Message, File Upload/Download |

### New Research Tools (8) — all free, no API key

| Tool | Source | API Key |
|------|--------|---------|
| `arxiv_search` | arXiv RSS | Không cần |
| `huggingface_search` | HuggingFace Hub API | Không cần |
| `github_search` | GitHub Search API | Optional `GITHUB_TOKEN` |
| `wikipedia_search` | MediaWiki REST API | Không cần |
| `news_search` | GDELT DOC API | Không cần |
| `stackoverflow_search` | Stack Exchange API | Không cần |
| `youtube_transcript` | youtube-transcript-api | **Không cần** (scrape trực tiếp) |
| `code_snippet` | Regex extraction | Không cần |

### New Visualization Tools (3) — all free

| Tool | Library | Output |
|------|---------|--------|
| `data_chart` | matplotlib (Agg backend) | PNG (bar/line/pie/scatter) |
| `comparison_table` | Pure Python | Markdown / HTML table |
| `mindmap_generator` | graphviz | PNG concept map |

> **Charts/images on prod**: matplotlib dùng `Agg` backend (non-interactive) → sinh PNG → Chainlit `cl.Image` / Streamlit `st.image` hiển thị inline. Hoàn toàn OK cho prod.

---

## 🤖 Agents (7)

| Agent | Purpose | Tools |
|-------|---------|-------|
| **Precheck** | Classify chat/task + tier + delivery_intent | - |
| **Orchestrator** | Multi-round coordination | - |
| **Research** | Information gathering | WebSearch, WebScrape, FileExtract, Arxiv, HuggingFace, GitHub, Wikipedia, News, StackOverflow, YouTube, CodeSnippet (11) |
| **Data** | Data processing + visualization | Json, FileExtract, DriveDownload, LarkDownload, DataChart, ComparisonTable, Mindmap (7) |
| **Notification** | Lark messaging (optional) | LarkMessage, LarkUpload (2) |
| **Architect** | Document generation | Markdown, PDF, DOCX, Diagram, DriveUpload, LarkUpload (6) |

---

## 📤 Output Format

### Chat (Tier 0)

```json
{
  "workflow_id": "uuid",
  "status": "completed",
  "type": "chat",
  "response": "Direct answer..."
}
```

### Research with Options (awaiting user confirmation)

```json
{
  "workflow_id": "uuid",
  "status": "awaiting_confirmation",
  "type": "research_with_options",
  "task_tier": "quick_research",
  "confidence": 0.85,
  "result": {
    "summary": "...",
    "sources": ["https://..."]
  },
  "proposed_actions": [
    {"action_id": "create_pdf", "label": "📄 Tạo tài liệu PDF", "action_type": "create_document"},
    {"action_id": "none", "label": "✅ Chỉ giữ kết quả research", "action_type": "none"}
  ],
  "rounds": 2
}
```

### Completed Research (auto-delivered or after confirmation)

```json
{
  "workflow_id": "uuid",
  "status": "completed",
  "type": "research",
  "confidence": 0.85,
  "result": {
    "summary": "...",
    "sources": ["https://..."]
  },
  "documents": {
    "documents_created": [{"type": "pdf", "file_path": "/path/to/doc.pdf"}],
    "uploaded_files": [{"filename": "report.pdf", "link": "https://drive.google.com/..."}]
  },
  "rounds": 2
}
```

### Error

```json
{
  "workflow_id": "uuid",
  "status": "failed",
  "error": "Error description"
}
```

---

## 🔗 n8n Integration

### Basic Workflow

```
Lark Trigger
    ↓
Execute Command
  python main.py --task "{{ $json.message }}" --session-id "{{ $json.user_id }}"
    ↓
Parse JSON (between @@JSON_START@@ and @@JSON_END@@)
    ↓
If status == "completed"
    ↓
Lark Send Message (results + Drive links)
```

> **Note**: Khi chạy qua n8n (headless), bật `LARK_NOTIFICATION_ENABLED=true` để nhận kết quả qua Lark. Khi chạy qua UI, để `false` để tránh duplicate.

### Parse JSON in n8n

```javascript
const output = $input.first().json.stdout;
const match = output.match(/@@JSON_START@@([\s\S]*)@@JSON_END@@/);
if (match) {
  return [{json: JSON.parse(match[1])}];
}
```

---

## 🧠 Memory System

### 3-Layer Architecture

1. **Working Memory** (runtime): Context sharing between agents in same workflow
2. **Short-term Memory** (database): Workflow states, execution history, resume support
3. **Long-term Memory** (database): Cached results, agent experiences, performance stats

### Features

- ✅ Session-based chat history
- ✅ High-confidence result caching (configurable TTL)
- ✅ Automatic cleanup
- ✅ Resume on error / awaiting confirmation
- ✅ Performance analytics
- ✅ Task state stored in `workflow_states.context` JSONB (no extra tables)
- ✅ All objects in schema `bingx_agent_mesh` (configurable via `POSTGRES_SCHEMA`)

---

## 🐛 Troubleshooting

### Common Issues

**`ModuleNotFoundError`**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Missing new dependencies (chainlit, matplotlib, youtube-transcript-api)**
```bash
pip install chainlit matplotlib youtube-transcript-api
```

**Database connection failed**
```bash
python scripts/init_database.py
```

**Tool execution failed**
```bash
# Check external dependencies
which pandoc graphviz
```

**Lark API errors**
```bash
# Verify credentials + notification enabled
python -c "from src.integrations.lark_client import get_lark_client; get_lark_client()._get_tenant_access_token()"
```

**GitHub rate limited**
```bash
# Set GITHUB_TOKEN in .env for higher limits (5000 req/h)
```

---

## 📚 Documentation

- [MEMORY_USAGE.md](./MEMORY_USAGE.md) - Memory system details
- [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute

---

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## 📄 License

MIT License - see [LICENSE](./LICENSE)

---

## 🎯 Use Cases

### 1. Research & Documentation
```bash
# Research → user chọn tạo PDF → upload Drive
chainlit run chainlit_app.py
# Chat: "Research FastAPI best practices"
# → Click "📄 Tạo tài liệu PDF"
```

### 2. Data Analysis with Visualization
```bash
python main.py --task "Download sales data from Drive, analyze trends, create bar chart visualization" --session-id project_001
```

### 3. Multi-source Research
```bash
# Uses arxiv, github, stackoverflow, wikipedia, news tools automatically
python main.py --task "Research latest multi-agent frameworks, compare LangGraph vs CrewAI vs AutoGen" --session-id research_001
```

### 4. Workflow Automation (headless)
```bash
# LARK_NOTIFICATION_ENABLED=true for headless delivery
python main.py --task "Monitor tech news about AI agents, create weekly summary PDF, send to Lark" --session-id cron_001
```
