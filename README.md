# 🤖 Multi-Agent Task Decomposition System

**Production-ready multi-agent system** với function calling, 15 tools, multi-round orchestration, và full memory management.

> ✅ **Status**: Production Ready | Function Calling ✅ | 15 Tools ✅ | Memory System ✅ | Error Handling ✅

---

## ✨ Highlights

- 🎯 **7 Specialized Agents** with automatic tool selection
- 🛠️ **15 Production Tools**: Search, Document Gen, Lark, Google Drive
- 🔄 **Multi-Round Orchestration**: Auto evaluate & continue (max 3 rounds)
- 🧠 **3-Layer Memory**: Working/Short-term/Long-term with caching
- 📱 **Lark Integration**: Full API support with auto error notifications
- 📊 **Google Drive**: Upload/download with service account
- 🔍 **Web Search**: Tavily API + DuckDuckGo fallback
- 📄 **Document Generation**: MD/PDF/DOCX/Diagrams
- 💾 **PostgreSQL Persistence**: Full workflow & chat history

---

## 🚀 Quick Start

```bash
# 1. Clone & Setup
git clone <repo>
cd agent-mesh-task-decomposition
python setup.py

# 2. Configure .env (see Configuration section)

# 3. Initialize Database
python scripts/init_database.py

# 4. Run
python main.py --task "Research Python and create PDF guide" --session-id user123
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

# For Diagrams
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
# ==== Logging ====
LOG_LEVEL=INFO
APP_ENV=dev

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=multi_agent_db

# ============================================
# OPTIONAL (but recommended)
# ============================================

# Lark
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
LARK_ERROR_CHAT_ID=oc_xxx  # For error notifications

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

Set up Drive Credentials"

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

### Basic Commands

```bash
# Simple chat
python main.py --task "Hello"

# Research task
python main.py --task "How to build a REST API with FastAPI?" --session-id user123

# Complex task with document generation
python main.py --task "Research multi-agent systems, create comprehensive PDF guide with diagrams, upload to Google Drive" --session-id project_001
```

### Management Scripts

```bash
# View statistics
python scripts/view_memory_stats.py

# View chat history
python scripts/view_session.py user123

# Cleanup old data
python scripts/cleanup_memory.py
```


### Streamlit chat UI

```bash
streamlit run streamlit_main.py
```

---

## 🏗️ Architecture

```
User Message
    ↓
┌─────────────────────────┐
│   Precheck Agent        │  Filter: chat vs research
└───────────┬─────────────┘
            ↓ (if research)
┌─────────────────────────┐
│ Orchestrator (Manager)  │
│  • Multi-round execution│
│  • Evaluate & Continue  │
│  • Max 3 rounds         │
└───────────┬─────────────┘
            ↓
┌───────┬────────┬────────┐
│Research│ Data   │ Notif. │
│ Agent  │ Agent  │ Agent  │
│        │        │        │
│Tools:  │Tools:  │Tools:  │
│•Search │•JSON   │•Lark   │
│•Scrape │•Extract│•Upload │
└───────┴────────┴────────┘
            ↓
┌─────────────────────────┐
│  Memory (3 Layers)      │
│ •Working •Short •Long   │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│    PostgreSQL/Supabase  │
└───────────┬─────────────┘
            ↓ (if complete)
┌─────────────────────────┐
│   Architect Agent       │
│ •Generate MD/PDF/DOCX   │
│ •Upload to Drive/Lark   │
└─────────────────────────┘
            ↓
     JSON Output → n8n

[On Error] → Lark Notification
```

---

## 🛠️ Tools (15)

| Category | Tools |
|----------|-------|
| **Search** | WebSearchTool (Tavily + DuckDuckGo), WebScrapeTool |
| **Data** | JsonProcessorTool, FileExtractorTool (PDF/DOCX/TXT) |
| **Documents** | Markdown, PDF (WeasyPrint), DOCX (pypandoc), Diagrams (Graphviz) |
| **Cloud** | Google Drive Upload/Download |
| **Lark** | Send Message (text/post), File Upload/Download |

---

## 🤖 Agents (7)

| Agent | Purpose | Tools |
|-------|---------|-------|
| **Precheck** | Filter chat/research | - |
| **Orchestrator** | Multi-round coordination | - |
| **Research** | Information gathering | Search, Scrape, FileExtract |
| **Data** | Data processing | Json, FileExtract, DriveDownload |
| **Notification** | Lark messaging | LarkMessage, LarkUpload |
| **Architect** | Document generation | All doc tools + uploads |

---

## 📤 Output Format

### Completed Research

```json
{
  "workflow_id": "uuid",
  "status": "completed",
  "confidence": 0.85,
  "result": {
    "summary": "...",
    "details": "...",
    "sources": ["https://..."]
  },
  "documents": {
    "markdown": "/path/to/doc.md",
    "pdf": "/path/to/doc.pdf",
    "drive_link": "https://drive.google.com/file/d/xxx"
  },
  "rounds": 2
}
```

### Error (auto sends to Lark)

```json
{
  "workflow_id": "uuid",
  "status": "error",
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
- ✅ Resume on error
- ✅ Performance analytics

---

## 🐛 Troubleshooting

### Common Issues

**`ModuleNotFoundError`**
```bash
source venv/bin/activate
pip install -r requirements.txt
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
# Verify credentials
python -c "from src.integrations.lark_client import get_lark_client; get_lark_client()._get_tenant_access_token()"
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
python main.py --task "Research FastAPI best practices, create PDF guide with code examples and architecture diagrams, upload to Drive"
```

### 2. Data Analysis
```bash
python main.py --task "Download sales data from Drive, analyze trends, create visualizations, send report to Lark"
```

### 3. Workflow Automation
```bash
python main.py --task "Monitor Lark channel for questions about Python, research answers, post responses automatically"
```
