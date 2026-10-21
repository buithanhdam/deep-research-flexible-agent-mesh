"""Configuration management for the multi-agent system."""

import os
from typing import Optional, Dict
from dotenv import load_dotenv
from urllib.parse import quote_plus
# Load environment variables
load_dotenv()


class Config:
    """Central configuration object for DRF Agent Mesh."""
    
    # LLM Provider selection: openrouter | chatgpt | gemini | custom
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "gemini").lower()
    
    # OpenRouter Configuration (optional provider)
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.1")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # ChatGPT / OpenAI Configuration (optional provider)
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    
    # Custom OpenAI-compatible provider (optional provider)
    CUSTOM_LLM_BASE_URL: str = os.environ.get("CUSTOM_LLM_BASE_URL", "")
    CUSTOM_LLM_API_KEY: str = os.environ.get("CUSTOM_LLM_API_KEY", "")
    CUSTOM_LLM_MODEL: str = os.environ.get("CUSTOM_LLM_MODEL", "")
    CUSTOM_LLM_NAME: str = os.environ.get("CUSTOM_LLM_NAME", "custom")
    
    # Postgres
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "")
    POSTGRES_PORT: str = os.environ.get("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "postgres")
    # Schema riêng cho hệ multi-agent — tránh conflict với các app khác cùng DB
    POSTGRES_SCHEMA: str = os.environ.get("POSTGRES_SCHEMA", "bingx_agent_mesh")
    
    # Logging
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    
    # GitHub API (optional — tăng rate limit, không bắt buộc)
    GITHUB_TOKEN: Optional[str] = os.environ.get("GITHUB_TOKEN")
    
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
    EXA_API_KEY: str = os.environ.get("EXA_API_KEY", "")

    # Search fallback chain: Tavily → Exa → Gemini Grounding → DuckDuckGo
    # (DuckDuckGo luôn được thêm làm backup cuối vì không cần key)
    SEARCH_ENGINE_CHAIN: Dict[str, list] = {
        "default": ["tavily", "exa", "gemini", "duckduckgo"],
    }

    # YouTube Data API v3 (Google Cloud — enable "YouTube Data API v3", tạo API key)
    # https://console.cloud.google.com/apis/library/youtube.googleapis.com
    YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")

    # Speech-to-Text (Whisper local — faster-whisper)
    # Model: tiny | base | small | medium | large-v3 (default: base — cân bằng tốc độ/quality)
    WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "base")

    # Text-to-Speech (edge-tts — free, no API key)
    # Voice list: https://github.com/rany2/edge-tts (vd: en-US-AriaNeural, vi-VN-HoaiMyNeural)
    TTS_VOICE: str = os.environ.get("TTS_VOICE", "en-US-AriaNeural")

    # Google Gemini Configuration (optional — for Search Grounding & alt LLM)
    # google-genai SDK; Search Grounding is a native Gemini feature not available via OpenRouter.
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
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
        """Validate required configuration (dynamic based on LLM_PROVIDER)."""
        provider_requirements = {
            "openrouter": [("OPENROUTER_API_KEY", cls.OPENROUTER_API_KEY)],
            "chatgpt": [("OPENAI_API_KEY", cls.OPENAI_API_KEY)],
            "gemini": [("GEMINI_API_KEY", cls.GEMINI_API_KEY)],
            "custom": [
                ("CUSTOM_LLM_API_KEY", cls.CUSTOM_LLM_API_KEY),
                ("CUSTOM_LLM_BASE_URL", cls.CUSTOM_LLM_BASE_URL),
            ],
        }
        required_fields = provider_requirements.get(
            cls.LLM_PROVIDER,
            provider_requirements["gemini"]  # Default fallback to Gemini
        )

        missing = [field for field, value in required_fields if not value]

        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        return True
    


# Create singleton instance
config = Config()

# Exa search engine configuration (uses EXA_API_KEY from .env)
EXA_CONFIG: Dict[str, str] = {
    "api_key": config.EXA_API_KEY,
}

# Tavily search engine configuration
TAVILY_CONFIG: Dict[str, str] = {
    "api_key": config.TAVILY_API_KEY,
}
