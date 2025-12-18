"""
Configuration module for PharmaAI backend
Centralizes all configuration settings
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration"""
    
    # Server settings
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # LLM settings
    LLM_MODEL = os.getenv("LLM_MODEL", "mistral")
    MISTRAL_MODEL_PATH = os.getenv("MISTRAL_MODEL_PATH", "models/mistral-7b-instruct-v0.1.Q4_K_M.gguf")
    
    # Embedding settings (uses local Mistral)
    EMBEDDING_MODEL_TYPE = os.getenv("EMBEDDING_MODEL_TYPE", "mistral_local")
    
    # Supabase settings
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    # Agent settings
    AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", 10))
    AGENT_TIMEOUT_SECONDS = int(os.getenv("AGENT_TIMEOUT_SECONDS", 120))
    
    # Mock data mode
    USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
    
    @classmethod
    def get_llm_config(cls) -> Dict[str, Any]:
        """Get LLM configuration dict"""
        return {
            "model": cls.LLM_MODEL,
            "model_path": cls.MISTRAL_MODEL_PATH,
            "temperature": 0.7,
            "max_tokens": 2000,
            "timeout": cls.AGENT_TIMEOUT_SECONDS
        }
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production mode"""
        return not cls.USE_MOCK_DATA
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        issues = []
        
        if cls.LLM_MODEL == "mistral" and not os.path.exists(cls.MISTRAL_MODEL_PATH):
            issues.append(f"Mistral model not found at {cls.MISTRAL_MODEL_PATH}")
        
        if issues:
            print("⚠️  Configuration issues detected:")
            for issue in issues:
                print(f"   - {issue}")
            print("   Running in MOCK mode with limited functionality")
            return False
        
        return True


# Validate on import
Config.validate()
