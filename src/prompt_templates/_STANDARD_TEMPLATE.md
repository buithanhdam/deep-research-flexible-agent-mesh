# Standard Prompt Template

All agents should follow this 4-step structure:

## Step 1: Task Classification
Analyze the task and classify it into one of the predefined categories.
Example categories: [TECH], [INTEGRATION], [BUILD], [CODE], [CHAT], etc.

## Step 2: Process by Type
Define specific process for each task type:
- What tools to call
- In what order
- What information to gather

## Step 3: Output Template
Define fixed output structure (Markdown or JSON).
Specify required fields and sections.

Example output template:
```markdown
## Summary
Brief summary of findings

## Details
Detailed information

## Sources
- Source 1
- Source 2

## Confidence Score
0.0 - 1.0
```

## Step 4: Rules (Hard Constraints)
- DO NOT fabricate information
- Find minimum N sources before concluding
- Priority order for sources (official docs > GitHub > blogs > social media)
- If tool returns empty, rewrite query and retry instead of giving up
- Always cite sources for factual claims
- Indicate confidence level in conclusions

## Tool Configuration Guidelines

### Domain-scoped Search
Each specialized agent should have search tools limited to relevant domains:
- Lark agent: larksuite.com, open.larksuite.com
- n8n agent: n8n.io, docs.n8n.io, community.n8n.io
- Code agent: github.com, stackoverflow.com, pypi.org

### Separate Search and Extract
- Use one tool to find URLs
- Use another tool to extract full content from best URL
- Don't combine both into a single tool

### Decision Output Format
When making routing/escalation decisions, use structured JSON:
```json
{
  "decision": "pass|fail|escalate",
  "confidence": 0.85,
  "reason": "explanation",
  "next_action": "specific action"
}
```
