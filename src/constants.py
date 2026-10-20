"""Constants used throughout the multi-agent system."""

# Agent Names
AGENT_PRECHECK = "precheck"
AGENT_ORCHESTRATOR = "orchestrator"
AGENT_RESEARCH = "research"
AGENT_DATA = "data"
AGENT_NOTIFICATION = "notification"
AGENT_ARCHITECT = "architect"

# Sub-agent Names
SUB_AGENT_N8N = "n8n_research"
SUB_AGENT_CODE = "code_architect"

# Task Types
TASK_TYPE_CHAT = "chat"
TASK_TYPE_RESEARCH = "research"
TASK_TYPE_DATA = "data"
TASK_TYPE_BUILD = "build"

# Task Tiers — phân loại độ phức tạp để chọn flow xử lý
TIER_CHAT = "chat"                      # Tier 0: hỏi đáp nhanh, trả lời trực tiếp
TIER_QUICK_RESEARCH = "quick_research"  # Tier 1: tra cứu/verify, chỉ trả findings
TIER_DEEP_RESEARCH = "deep_research"    # Tier 2: nghiên cứu sâu, đề xuất deliverables
TIER_MULTI_DOMAIN = "multi_domain"      # Tier 3: project nhiều chủ đề, cần decomposition

# Delivery Intent — user có yêu cầu rõ deliverable không?
DELIVERY_NONE = "none"                  # Chỉ cần câu trả lời / findings
DELIVERY_DOCUMENT = "document"          # Yêu cầu rõ tạo tài liệu (PDF/MD/DOCX)
DELIVERY_DIAGRAM = "diagram"            # Yêu cầu rõ tạo diagram
DELIVERY_NOTIFY = "notify"              # Yêu cầu rõ gửi notification
DELIVERY_UPLOAD = "upload"              # Yêu cầu rõ upload lên Drive

# Workflow Status (mở rộng cho human-in-the-loop gate)
WORKFLOW_AWAITING_CONFIRMATION = "awaiting_confirmation"
WORKFLOW_GENERATING = "generating"

# Output Markers (for n8n parsing)
JSON_START_MARKER = "@@JSON_START@@"
JSON_END_MARKER = "@@JSON_END@@"

# Memory Types
MEMORY_WORKING = "working"
MEMORY_SHORT_TERM = "short_term"
MEMORY_LONG_TERM = "long_term"

# Confidence Thresholds
CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.5
CONFIDENCE_LOW = 0.3

# Retry Configuration
MAX_TOOL_RETRIES = 2
TOOL_RETRY_DELAY = 1  # seconds

# Search Configuration
MAX_SEARCH_RESULTS = 5
MAX_EXTRACT_LENGTH = 10000  # characters

# Domain Scopes for Tools
DOMAIN_N8N = ["n8n.io", "docs.n8n.io", "community.n8n.io"]
DOMAIN_CODE = ["github.com", "stackoverflow.com", "pypi.org", "readthedocs.io"]
