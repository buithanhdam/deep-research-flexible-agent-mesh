"""Script to initialize database schema for memory system."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.memory_manager import get_memory_manager
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


def main():
    """Initialize database schema."""
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    
    # Check configuration
    if not config.POSTGRES_DSN:
        print("\n❌ Error: POSTGRES_DSN not configured in .env")
        print("   Please add your PostgreSQL connection string:")
        print("   POSTGRES_DSN=postgresql://user:password@host:port/database")
        return 1
    
    print(f"\n📦 Database: {config.POSTGRES_DSN.split('@')[1] if '@' in config.POSTGRES_DSN else 'configured'}")
    
    # Confirm
    response = input("\n⚠️  This will create tables and functions. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return 0
    
    # Initialize
    print("\n🔧 Initializing database schema...")
    
    try:
        memory = get_memory_manager()
        success = memory.init_database()
        
        if success:
            print("\n✅ Database initialized successfully!")
            print(f"\nSchema: {config.POSTGRES_SCHEMA}")
            print("\nCreated tables:")
            print("  - chat_history")
            print("  - workflow_states")
            print("  - agent_executions")
            print("  - cached_results")
            print("\nCreated functions:")
            print("  - cleanup_old_chat_history(days)")
            print("  - cleanup_expired_cache()")
            print("  - cleanup_old_workflows(days)")
            print("\nCreated views:")
            print("  - agent_performance")
            print("  - cache_statistics")
            print("  - workflow_statistics")
            
            # Test connection
            print("\n🔍 Testing database connection...")
            stats = memory.get_statistics()
            
            if 'error' not in stats:
                print("✅ Connection test passed!")
                print(f"   Working memory workflows: {stats.get('working_memory_workflows', 0)}")
            else:
                print(f"⚠️  Warning: {stats.get('error')}")
            
            return 0
        else:
            print("\n❌ Database initialization failed!")
            print("   Check logs for details.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
