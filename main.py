"""Main entry point for the multi-agent system."""

import sys
import json
import argparse
from typing import Dict, Any
import uuid

from src.config import config
from src.logger import get_logger
from src.constants import JSON_START_MARKER, JSON_END_MARKER
from src.memory.memory_manager import get_memory_manager
from agent_flow import process_message

logger = get_logger(__name__)


def print_json_output(data: Dict[str, Any]) -> None:
    """Print JSON output with markers for n8n parsing.
    
    Args:
        data: Data to output as JSON
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    print(f"{JSON_START_MARKER}", flush=True)
    print(json_str, flush=True)
    print(f"{JSON_END_MARKER}", flush=True)

def run_auto_cleanup():
    """Run automatic cleanup if enabled."""
    if not config.AUTO_CLEANUP_ENABLED:
        return
    
    try:
        from datetime import datetime, timedelta
        import os
        
        # Check last cleanup time
        cleanup_marker = ".last_cleanup"
        should_cleanup = True
        
        if os.path.exists(cleanup_marker):
            with open(cleanup_marker, 'r') as f:
                last_cleanup = datetime.fromisoformat(f.read().strip())
                next_cleanup = last_cleanup + timedelta(hours=config.AUTO_CLEANUP_INTERVAL_HOURS)
                should_cleanup = datetime.utcnow() >= next_cleanup
        
        if should_cleanup:
            logger.info("auto_cleanup_started")
            memory = get_memory_manager()
            deleted = memory.cleanup_old_data(config.AUTO_CLEANUP_RETENTION_DAYS)
            
            logger.info(
                "auto_cleanup_completed",
                chat_messages=deleted.get('chat_messages', 0),
                cached_results=deleted.get('cached_results', 0),
                workflows=deleted.get('workflows', 0)
            )
            
            # Update marker
            with open(cleanup_marker, 'w') as f:
                f.write(datetime.utcnow().isoformat())
    
    except Exception as e:
        logger.error("auto_cleanup_failed", error=str(e))


def main():
    """Main entry point."""
    # Run auto cleanup if enabled
    run_auto_cleanup()
    
    parser = argparse.ArgumentParser(
        description="Multi-Agent System for Research and Task Processing"
    )
    
    parser.add_argument(
        "--task",
        type=str,
        required=False,
        help="Task or message to process"
    )

    parser.add_argument(
        "--daily-research",
        action="store_true",
        help="Run the daily IT/AI/ML research pipeline (collect sources, generate report, upload to Drive)"
    )

    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session identifier for tracking conversation"
    )

    args = parser.parse_args()

    if args.daily_research:
        from src.agents.daily_research_agent import DailyResearchAgent

        agent = DailyResearchAgent()
        result = agent.run(upload=True)
        print_json_output(result)
        sys.exit(0 if result.get("success") else 1)

    if not args.task:
        parser.error("--task is required unless --daily-research is used")
    
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error("config_invalid", error=str(e))
        print_json_output({
            "status": "error",
            "error": f"Configuration error: {str(e)}"
        })
        sys.exit(1)
    
    # Process message
    result = process_message(args.task, args.session_id)
    
    # Output result as JSON with markers
    print_json_output(result)
    
    # Exit with appropriate code
    if result.get("status") == "error":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
