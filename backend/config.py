"""
Configuration management for the multi-agent storyboard system.
Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://infinitai.sifymdp.digital/maas/v1", env="OPENAI_BASE_URL")
    openai_model: str = Field(default="meta/llama-3.3-70b-instruct", env="OPENAI_MODEL")  # Optimized for speed: 3-5x faster than GPT-4
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=30000, env="OPENAI_MAX_TOKENS")
    openai_embedding_model: str = Field(default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    
    # Web Search Configuration
    serper_api_key: Optional[str] = Field(default=None, env="SERPER_API_KEY")
    
    # MongoDB Configuration
    mongodb_uri: str = Field(default="mongodb://localhost:27017", env="MONGODB_URI")
    mongodb_database: str = Field(default="storyboard_db", env="MONGODB_DATABASE")
    
    # ChromaDB Configuration
    chromadb_persist_dir: str = Field(default="./chroma_data", env="CHROMADB_PERSIST_DIR")
    chromadb_rag_collection: str = Field(default="rag_documents", env="CHROMADB_RAG_COLLECTION")
    chromadb_tme_collection: str = Field(default="tme_memories", env="CHROMADB_TME_COLLECTION")
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = Field(default=30, env="WS_HEARTBEAT_INTERVAL")
    ws_max_connections: int = Field(default=100, env="WS_MAX_CONNECTIONS")
    
    # Application Configuration
    app_name: str = Field(default="Multi-Agent Storyboard System", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Paths
    domain_templates_path: str = Field(
        default="prompts/domain_templates.json", 
        env="DOMAIN_TEMPLATES_PATH"
    )
    
    # Agent Configuration
    preact_max_scenes: int = Field(default=10, env="PREACT_MAX_SCENES")
    react_max_iterations: int = Field(default=20, env="REACT_MAX_ITERATIONS")  # Increased to allow completing full plans
    reflect_revision_rounds: int = Field(default=1, env="REFLECT_REVISION_ROUNDS")  # Optimized: Reduced from 2 to 1 for 50% faster validation
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """
    Get settings instance (fresh on each call during development).
    
    Returns:
        Settings: Application settings.
    """
    return Settings()


# Global settings instance - reloaded when server restarts
settings = Settings()

