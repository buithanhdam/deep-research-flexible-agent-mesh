"""Configuration management for the multi-agent system."""

import os
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote_plus
# Load environment variables
load_dotenv()


class Config:
    """Central configuration object."""
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Postgres
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "")
    POSTGRES_PORT: str = os.environ.get("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "postgres")
    
    # Logging
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    
    # Lark Integration (optional)
    LARK_APP_ID: Optional[str] = os.environ.get("LARK_APP_ID")
    LARK_APP_SECRET: Optional[str] = os.environ.get("LARK_APP_SECRET")
    LARK_ERROR_CHAT_ID: Optional[str] = os.environ.get("LARK_ERROR_CHAT_ID")  # Chat ID for error notifications
    
    # Agent Configuration
    MAX_RETRIES: int = int(os.environ.get("MAX_RETRIES", "3"))
    TIMEOUT_SECONDS: int = int(os.environ.get("TIMEOUT_SECONDS", "120"))
    AGENT_LOOP_MAX_ROUNDS: int = int(os.environ.get("AGENT_LOOP_MAX_ROUNDS", "5"))
    
    # Memory Configuration
    CACHE_DEFAULT_TTL_HOURS: int = int(os.environ.get("CACHE_DEFAULT_TTL_HOURS", "24"))
    CACHE_MAX_TTL_HOURS: int = int(os.environ.get("CACHE_MAX_TTL_HOURS", "168"))
    CHAT_HISTORY_MAX_MESSAGES: int = int(os.environ.get("CHAT_HISTORY_MAX_MESSAGES", "10"))
    CHAT_HISTORY_RETENTION_DAYS: int = int(os.environ.get("CHAT_HISTORY_RETENTION_DAYS", "30"))
    
    # Working Memory
    WORKING_MEMORY_AUTO_CLEAR: bool = os.environ.get("WORKING_MEMORY_AUTO_CLEAR", "true").lower() == "true"
    
    # Cleanup Configuration
    AUTO_CLEANUP_ENABLED: bool = os.environ.get("AUTO_CLEANUP_ENABLED", "false").lower() == "true"
    AUTO_CLEANUP_INTERVAL_HOURS: int = int(os.environ.get("AUTO_CLEANUP_INTERVAL_HOURS", "24"))
    AUTO_CLEANUP_RETENTION_DAYS: int = int(os.environ.get("AUTO_CLEANUP_RETENTION_DAYS", "30"))
    
    # Search API Configuration
    TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")
    
    # Google Drive Configuration
    GOOGLE_DRIVE_ENABLED: bool = os.environ.get("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
    GOOGLE_DRIVE_CREDENTIALS_JSON: Optional[str] = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON")
    GOOGLE_DRIVE_CREDENTIALS: Optional[str] = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    @property
    def POSTGRES_DSN(self) -> str:
        """Tự build DSN từ các phần rời, tự động URL-encode user/password.
 
        Trả về chuỗi rỗng nếu chưa cấu hình đủ (host/user/password) —
        PostgresClient sẽ tự coi là "not configured" như logic hiện tại.
        """
        if not (self.POSTGRES_HOST and self.POSTGRES_USER and self.POSTGRES_PASSWORD):
            return ""
 
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
 
        return (
            f"postgresql://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        required_fields = [
            ("OPENROUTER_API_KEY", cls.OPENROUTER_API_KEY),
        ]
        
        missing = [field for field, value in required_fields if not value]
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
    


# Create singleton instance
config = Config()
