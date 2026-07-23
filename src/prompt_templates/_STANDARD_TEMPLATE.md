# Standard Prompt Template

All agent prompts follow this 4-step structure. Prompts live in their own `*_prompt.py` files.
Output schemas are defined as Pydantic models in `output_models.py`.

---

## Structure of a Prompt File

```
src/prompt_templates/
├── _STANDARD_TEMPLATE.md       ← this file (guidelines)
├── output_models.py            ← Pydantic schemas for every agent
├── precheck_prompt.py
├── orchestrator_prompt.py
├── research_agent_prompt.py
├── data_agent_prompt.py
├── notification_agent_prompt.py
└── architect_agent_prompt.py
```

Each prompt file exports a single `get_<agent>_prompt() -> str` function.
The function injects `current_datetime` at call-time so the LLM always knows the current date.

---

## Step 1 — Task Classification

Every agent classifies the incoming task before acting:

| Tag | Meaning |
|-----|---------|
| `[RESEARCH]` | Lookup, information gathering |
| `[TECHNICAL]` | API docs, SDK, version-specific queries |
| `[INTEGRATION]` | Connecting systems (Lark ↔ n8n, etc.) |
| `[BUILD]` | Architecture, code generation |
| `[DATA]` | Processing, transformation, statistics |
| `[CHAT]` | Casual conversation — answered directly, not passed on |

---

## Step 2 — Process by Type

For each classification the agent follows its own decision tree:
- Which tools to call and in which order
- Minimum number of sources to gather before concluding
- Retry strategy when a tool returns empty results

**Tool call order principle**: search → scrape/extract → synthesize.
Never combine search + extract into a single tool call.

---

## Step 3 — Output

Every agent **must** return a JSON object that exactly matches the Pydantic schema defined
in `output_models.py` for that agent. The prompt file includes the schema as a JSON comment
so the LLM has the exact field names and types.

**Confidence scoring guide**:

| Range | Meaning |
|-------|---------|
| 0.9 – 1.0 | Multiple authoritative sources, fully verified |
| 0.7 – 0.9 | At least 2 good sources, minor gaps |
| 0.5 – 0.7 | Single source or unverified, proceed with caution |
| 0.0 – 0.5 | Insufficient data — escalate instead of guessing |

---

## Step 4 — Hard Constraints (apply to ALL agents)

1. **Never fabricate** — if information is unknown, say so explicitly.
2. **Minimum 2 independent sources** before concluding on any factual claim.
3. **Source priority**: Official docs > GitHub official repo > Stack Overflow > Blogs > Social media.
4. **Empty tool result** → rewrite query with different keywords and retry once before giving up.
5. **Confidence < 0.5** → set action to `escalate`, do NOT return a low-quality answer.
6. **Always cite** source URLs for every factual statement.
7. **Do not mix languages** — respond in the same language the user wrote in.
8. **current_datetime** is injected into every prompt at call time — use it for time-sensitive context.

---

## Tool Guidelines

### Domain-scoped Search
Pass `target_domains` when instantiating `WebSearchTool` to restrict results:

```python
# Lark-specific search
WebSearchTool(name="lark_search", target_domains=["larksuite.com", "open.feishu.cn"])

# n8n-specific search
WebSearchTool(name="n8n_search", target_domains=["n8n.io", "docs.n8n.io", "community.n8n.io"])

# Code/library search
WebSearchTool(name="code_search", target_domains=["github.com", "stackoverflow.com", "pypi.org"])
```

### Two-step Search Pattern
```
1. web_search(query)          → list of {url, title, snippet}
2. web_scrape(best_url)       → full page content
3. Synthesize from full content
```

### Tool Error Handling
- Tool returns `success: false` → log warning, try next tool, never silently skip.
- All tool failures reported in agent result `warnings` field.

---

## Escalation Triggers

An agent must escalate (not guess) when:
- `confidence < 0.5` after exhausting all tool retries
- Required data is behind a paywall / login wall
- Task is outside the agent's defined capability
- Contradictory information found across sources with no resolution
