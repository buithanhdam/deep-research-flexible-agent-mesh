"""Demo script to show system capabilities without needing OpenRouter API."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def demo_structure():
    """Show the system structure."""
    print("=" * 70)
    print("MULTI-AGENT SYSTEM - STRUCTURE DEMO")
    print("=" * 70)
    
    print("\n📁 Project Structure:")
    print("""
src/
├── agents/
│   ├── base_agent.py           # Base class cho mọi agent
│   ├── precheck_agent.py       # Lọc chat vs research
│   ├── orchestrator_agent.py   # Điều phối agents
│   ├── research_agent.py       # Tìm kiếm thông tin
│   ├── data_agent.py           # Xử lý dữ liệu
│   ├── notification_agent.py   # Chuẩn bị thông báo
│   └── sub_agents/             # Sub-agents (Phase 2)
│
├── llm/
│   └── openrouter_client.py    # OpenRouter API client
│
├── db/
│   ├── supabase_client.py      # Supabase integration
│   └── postgres_client.py      # PostgreSQL client
│
├── memory/
│   ├── models.py               # Data models
│   └── memory_manager.py       # Memory management
│
├── tools/                      # Tools cho agents (Phase 2)
├── prompt_templates/           # Prompts cho từng agent
├── config.py                   # Configuration
├── constants.py                # Constants
├── logger.py                   # Logging setup
└── main.py                     # Entry point
    """)


def demo_flow():
    """Show the execution flow."""
    print("\n🔄 Execution Flow:")
    print("""
1. USER MESSAGE
   ↓
2. PRECHECK AGENT
   ├─ Is it casual chat? → Return direct response
   └─ Is it research task? → Continue to Orchestrator
   ↓
3. ORCHESTRATOR AGENT
   ├─ Analyze task
   ├─ Decompose into sub-tasks
   ├─ Delegate to specialized agents:
   │  ├─ Research Agent (find information)
   │  ├─ Data Agent (process data)
   │  └─ Notification Agent (format response)
   ├─ Synthesize results
   └─ Decide: Return or Escalate?
   ↓
4. OUTPUT
   ├─ Completed: Return results
   ├─ Escalated: Notify for human review
   └─ Error: Return error details
    """)


def demo_examples():
    """Show example interactions."""
    print("\n💬 Example Interactions:")
    
    examples = [
        {
            "input": "Hello",
            "type": "Chat",
            "output": {
                "status": "completed",
                "type": "chat",
                "response": "Hello! How can I help you?"
            }
        },
        {
            "input": "How do I integrate n8n with external APIs?",
            "type": "Research",
            "output": {
                "status": "completed",
                "type": "research",
                "confidence": 0.85,
                "result": {
                    "summary": "Integration summary...",
                    "details": "Step-by-step guide...",
                    "sources": ["docs.n8n.io"]
                }
            }
        },
        {
            "input": "Build a Python multi-agent system",
            "type": "Complex Task",
            "output": {
                "status": "completed",
                "type": "research",
                "confidence": 0.75,
                "result": {
                    "summary": "Architecture recommendations...",
                    "agent_results": [
                        {"agent": "research", "confidence": 0.8},
                        {"agent": "data", "confidence": 0.7}
                    ]
                }
            }
        }
    ]
    
    for i, ex in enumerate(examples, 1):
        print(f"\n{i}. {ex['type']} Example:")
        print(f"   Input: \"{ex['input']}\"")
        print(f"   Output:")
        import json
        print("   " + json.dumps(ex['output'], indent=2).replace('\n', '\n   '))


def demo_agents():
    """Show agent capabilities."""
    print("\n🤖 Agent Capabilities:")
    
    agents = [
        {
            "name": "Precheck Agent",
            "role": "Router/Filter",
            "capabilities": [
                "Phân loại chat thường vs research task",
                "Trả lời nhanh cho câu chào hỏi",
                "Quyết định có cần chạy pipeline nặng không"
            ]
        },
        {
            "name": "Orchestrator Agent",
            "role": "Coordinator",
            "capabilities": [
                "Phân tích và decompose task phức tạp",
                "Delegate cho agent phù hợp",
                "Tổng hợp kết quả từ nhiều agents",
                "Quyết định escalate khi cần"
            ]
        },
        {
            "name": "Research Agent",
            "role": "Information Gatherer",
            "capabilities": [
                "Tìm kiếm thông tin từ nhiều nguồn",
                "Verify và cross-reference",
                "Gọi sub-agents chuyên biệt khi cần",
                "Đánh giá confidence score"
            ]
        },
        {
            "name": "Data Agent",
            "role": "Data Processor",
            "capabilities": [
                "Xử lý và transform dữ liệu",
                "Phân tích thống kê",
                "Tổng hợp và aggregation",
                "Format conversion"
            ]
        },
        {
            "name": "Notification Agent",
            "role": "Message Formatter",
            "capabilities": [
                "Format kết quả thành message đẹp",
                "Adapt tone theo context",
                "Highlight key points",
                "Đề xuất next steps"
            ]
        }
    ]
    
    for agent in agents:
        print(f"\n  • {agent['name']} ({agent['role']})")
        for cap in agent['capabilities']:
            print(f"    - {cap}")


def demo_memory():
    """Show memory architecture."""
    print("\n🧠 Memory Architecture:")
    print("""
┌─────────────────────────────────────────────────────────┐
│                    MEMORY MANAGER                        │
│            (Gateway giữa Agents và Database)             │
└─────────────────────────────────────────────────────────┘
                            ▼
         ┌──────────────────┬──────────────────┬──────────────────┐
         │                  │                  │                  │
    ┌────▼────┐      ┌──────▼──────┐    ┌─────▼──────┐
    │ Working │      │ Short-term  │    │ Long-term  │
    │ Memory  │      │   Memory    │    │   Memory   │
    └─────────┘      └─────────────┘    └────────────┘
         │                  │                  │
    Runtime only     Recent workflows    Cached results
    In-memory        Resume support      Experience learning
    Context share    Audit trail         Performance stats
    """)


def demo_integration():
    """Show n8n integration."""
    print("\n🔗 n8n Integration:")
    print("""
┌──────────────┐
│ Webhook Call │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│         n8n Workflow                     │
│                                          │
│  1. Webhook Trigger                      │
│  2. Execute Command Node                 │
│     └─ python -m src.main --task "..."  │
│  3. Extract JSON                         │
│     └─ Between @@JSON_START@@ markers   │
│  4. If Decision                          │
│     ├─ completed → Webhook Response     │
│     └─ escalated → Notify Admin         │
└──────────────────────────────────────────┘
    """)


def demo_prompt_template():
    """Show standard prompt template."""
    print("\n📝 Standard Prompt Template (4 Steps):")
    print("""
Step 1: TASK CLASSIFICATION
  └─ Phân loại task: [TECH], [INTEGRATION], [BUILD], [CODE]...

Step 2: PROCESS BY TYPE
  └─ Quy trình cụ thể cho từng loại
     ├─ Tool nào?
     ├─ Thứ tự ra sao?
     └─ Thu thập thông tin gì?

Step 3: OUTPUT TEMPLATE
  └─ Cấu trúc cố định (JSON/Markdown)
     ├─ Summary
     ├─ Details
     ├─ Sources
     └─ Confidence Score

Step 4: RULES (Hard Constraints)
  ├─ KHÔNG bịa thông tin
  ├─ Tối thiểu N nguồn trước khi kết luận
  ├─ Ưu tiên: Official docs > GitHub > Blogs
  ├─ Tool trả rỗng → retry với query khác
  └─ Luôn cite sources
    """)


def demo_commands():
    """Show common commands."""
    print("\n⚡ Common Commands:")
    print("""
# Setup
python -m venv venv
venv\\Scripts\\activate  # Windows
pip install -r requirements.txt

# Test system
python test_system.py

# Run system
python -m src.main --task "Hello"
python -m src.main --task "Research Python agents"
python -m src.main --task "..." --session-id user123

# View logs (stderr)
python -m src.main --task "..." 2>&1 | more

# Parse JSON output
python -m src.main --task "..." | findstr /C:"@@JSON"
    """)


def main():
    """Run all demos."""
    demo_structure()
    demo_flow()
    demo_agents()
    demo_memory()
    demo_prompt_template()
    demo_integration()
    demo_examples()
    demo_commands()
    
    print("\n" + "=" * 70)
    print("🎯 Next Steps:")
    print("=" * 70)
    print("""
1. Tạo file .env với OPENROUTER_API_KEY
2. Chạy: python test_system.py
3. Test: python -m src.main --task "Hello"
4. Đọc: QUICKSTART.md để biết thêm chi tiết
5. Tích hợp vào n8n workflow của bạn
    """)
    print("=" * 70)


if __name__ == "__main__":
    main()
