"""PostgreSQL client for database operations."""

from typing import Optional, Any, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class PostgresClient:
    """Client for PostgreSQL operations."""
    
    def __init__(self, dsn: Optional[str] = None):
        """Initialize PostgreSQL client.
        
        Args:
            dsn: PostgreSQL connection string (defaults to config)
        """
        self.dsn = dsn or config.POSTGRES_DSN
        
        if not self.dsn:
            logger.warning("postgres_not_configured")
            self._available = False
        else:
            self._available = True
            logger.info("postgres_client_initialized")
    
    def is_available(self) -> bool:
        """Check if PostgreSQL is configured and available."""
        return self._available
    
    @contextmanager
    def get_connection(self):
        """Get a PostgreSQL connection context manager.
        
        Yields:
            psycopg2 connection
        """
        if not self._available:
            raise RuntimeError("PostgreSQL client not initialized. Check configuration.")
        
        conn = None
        try:
            conn = psycopg2.connect(self.dsn)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("postgres_connection_error", error=str(e))
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
        
        Returns:
            Query results as list of dicts, or None
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if fetch:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                
                return None
    def execute_script(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script as a single command.
        
        Unlike execute_query, this does NOT split the script or bind
        parameters — it sends the whole script to Postgres as-is, so
        constructs like $$ ... $$ function bodies (which contain their
        own semicolons) are handled correctly.
        
        Args:
            sql_script: Raw SQL script, potentially with multiple statements
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_script)
    
    def execute_many(
        self,
        query: str,
        params_list: List[tuple]
    ) -> None:
        """Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)


# Singleton instance
_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
    """Get or create PostgreSQL client singleton."""
    global _client
    if _client is None:
        _client = PostgresClient()
    return _client
