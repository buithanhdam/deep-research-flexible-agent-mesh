"""Script to view chat history for a session."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.memory_manager import get_memory_manager
from src.config import config


def main():
    """View session chat history."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/view_session.py <session_id> [limit]")
        print("\nExample:")
        print("  python scripts/view_session.py user123")
        print("  python scripts/view_session.py user123 20")
        return 1
    
    session_id = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    print("=" * 60)
    print(f"Chat History for Session: {session_id}")
    print("=" * 60)
    
    if not config.POSTGRES_DSN:
        print("\n❌ Error: POSTGRES_DSN not configured")
        return 1
    
    try:
        memory = get_memory_manager()
        messages = memory.get_chat_history(session_id, limit)
        
        if not messages:
            print(f"\nNo messages found for session: {session_id}")
            return 0
        
        print(f"\nShowing {len(messages)} messages (limit: {limit})\n")
        
        for i, msg in enumerate(messages, 1):
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            role_icon = "👤" if msg.role == "user" else "🤖"
            agent_info = f" [{msg.agent_name}]" if msg.agent_name else ""
            
            print(f"{i}. {role_icon} {msg.role.upper()}{agent_info}")
            print(f"   Time: {timestamp}")
            print(f"   {msg.content[:200]}")
            if len(msg.content) > 200:
                print(f"   ... ({len(msg.content)} chars total)")
            print()
        
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
