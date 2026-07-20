"""Constants used throughout the multi-agent system."""

# Agent Names
AGENT_PRECHECK = "precheck"
AGENT_ORCHESTRATOR = "orchestrator"
AGENT_RESEARCH = "research"
AGENT_DATA = "data"
AGENT_NOTIFICATION = "notification"
AGENT_ARCHITECT = "architect"

# Sub-agent Names
SUB_AGENT_LARK = "lark_research"
SUB_AGENT_N8N = "n8n_research"
SUB_AGENT_CODE = "code_architect"

# Task Types
TASK_TYPE_CHAT = "chat"
TASK_TYPE_RESEARCH = "research"
TASK_TYPE_DATA = "data"
TASK_TYPE_BUILD = "build"

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
DOMAIN_LARK = ["larksuite.com", "open.larksuite.com", "open.feishu.cn"]
DOMAIN_N8N = ["n8n.io", "docs.n8n.io", "community.n8n.io"]
DOMAIN_CODE = ["github.com", "stackoverflow.com", "pypi.org", "readthedocs.io"]
