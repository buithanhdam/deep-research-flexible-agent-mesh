"""Script to view memory system statistics."""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.memory_manager import get_memory_manager
from src.config import config


def print_table(title, data, headers=None):
    """Print data as a formatted table."""
    if not data:
        print(f"\n{title}")
        print("  (No data)")
        return
    
    print(f"\n{title}")
    print("-" * 60)
    
    if headers:
        print("  " + " | ".join(str(h).ljust(15) for h in headers))
        print("  " + "-" * (len(headers) * 17))
    
    for row in data:
        if isinstance(row, dict):
            print("  " + " | ".join(str(v)[:15].ljust(15) for v in row.values()))
        else:
            print(f"  {row}")


def main():
    """Display memory statistics."""
    print("=" * 60)
    print("Memory System Statistics")
    print("=" * 60)
    
    if not config.POSTGRES_DSN:
        print("\n⚠️  Database not configured (POSTGRES_DSN missing)")
        print("   Statistics will show in-memory data only.")
    
    try:
        memory = get_memory_manager()
        stats = memory.get_statistics()
        
        if 'error' in stats:
            print(f"\n❌ Error: {stats['error']}")
            return 1
        
        # Working Memory
        print(f"\n📊 Working Memory")
        print(f"   Active workflows: {stats.get('working_memory_workflows', 0)}")
        
        # Agent Performance
        perf = stats.get('agent_performance', [])
        if perf:
            print_table(
                "🤖 Agent Performance (Last 7 days)",
                perf,
                ['Agent', 'Total', 'Success', 'Failed', 'Avg Conf', 'Avg Dur(s)', 'Last Exec']
            )
        
        # Cache Statistics
        cache = stats.get('cache_statistics', [])
        if cache:
            print_table(
                "💾 Cache Statistics",
                cache,
                ['Agent', 'Total', 'Hits', 'Avg Conf', 'Active', 'Expired']
            )
        
        # Workflow Statistics
        workflows = stats.get('workflow_statistics', [])
        if workflows:
            print_table(
                "🔄 Workflow Statistics (Last 7 days)",
                workflows,
                ['Status', 'Count', 'Avg Duration(s)']
            )
        
        print("\n" + "=" * 60)
        
        # Additional info
        if config.POSTGRES_DSN:
            print("\n💡 Tips:")
            print("   - Run cleanup: python scripts/cleanup_memory.py")
            print("   - View specific session: python scripts/view_session.py <session_id>")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
