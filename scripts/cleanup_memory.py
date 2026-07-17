"""Script to cleanup old memory data."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.memory_manager import get_memory_manager
from src.config import config


def main():
    """Cleanup old memory data."""
    print("=" * 60)
    print("Memory Cleanup Script")
    print("=" * 60)
    
    if not config.POSTGRES_DSN:
        print("\n❌ Error: POSTGRES_DSN not configured")
        return 1
    
    # Get retention days
    try:
        retention_days = int(input("\nRetention period in days (default 30): ") or "30")
    except ValueError:
        print("Invalid number, using default: 30")
        retention_days = 30
    
    print(f"\n⚠️  This will delete:")
    print(f"   - Chat messages older than {retention_days} days")
    print(f"   - Expired cached results")
    print(f"   - Completed/failed workflows older than {retention_days} days")
    
    response = input("\nContinue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return 0
    
    print("\n🧹 Cleaning up...")
    
    try:
        memory = get_memory_manager()
        deleted = memory.cleanup_old_data(retention_days)
        
        print("\n✅ Cleanup completed!")
        print(f"   Chat messages deleted: {deleted.get('chat_messages', 0)}")
        print(f"   Cached results deleted: {deleted.get('cached_results', 0)}")
        print(f"   Workflows deleted: {deleted.get('workflows', 0)}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
