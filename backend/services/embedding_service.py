"""
Embedding Service
Generates vector embeddings for text using local Mistral model
"""
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class EmbeddingService:
    """
    Generates embeddings for semantic search using local Mistral model
    
    Uses llama-cpp-python with local Mistral GGUF model
    """
    
    def __init__(self, model_type: str = "mistral_local"):
        """
        Initialize embedding service
        
        Args:
            model_type: "mistral_local" (only option, OpenAI removed)
        """
        self.model_type = model_type
        self.dimension = 1536  # Standard embedding dimension
        
        if model_type == "mistral_local":
            self._init_mistral_embeddings()
        else:
            print(f"⚠️  Unknown model_type: {model_type}, using mistral_local")
            self._init_mistral_embeddings()
    
    def _init_mistral_embeddings(self):
        """Initialize Mistral local embeddings"""
        try:
            from llama_cpp import Llama
            
            model_path = os.getenv("MISTRAL_MODEL_PATH", "models/mistral-7b-instruct-v0.1.Q4_K_M.gguf")
            
            if not os.path.exists(model_path):
                print(f"⚠️  Mistral model not found at {model_path}")
                print("Falling back to mock embeddings")
                self.model = None
                return
            
            self.model = Llama(
                model_path=model_path,
                embedding=True,
                n_ctx=2048,
                n_threads=4
            )
            print("✓ Mistral local embeddings initialized")
        except ImportError:
            print("⚠️  llama-cpp-python not installed. Install with: pip install llama-cpp-python")
            self.model = None
        except Exception as e:
            print(f"⚠️  Mistral initialization error: {e}")
            self.model = None
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using local Mistral
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats (1536-dimensional vector)
        """
        return await self._generate_mistral_embedding(text)
    
    async def _generate_mistral_embedding(self, text: str) -> List[float]:
        """Generate embedding using Mistral local model"""
        if not self.model:
            return self._generate_mock_embedding(text)
        
        try:
            embedding = self.model.embed(text)
            
            # Pad or truncate to 1536 dimensions
            if len(embedding) < self.dimension:
                embedding.extend([0.0] * (self.dimension - len(embedding)))
            elif len(embedding) > self.dimension:
                embedding = embedding[:self.dimension]
            
            return embedding
        except Exception as e:
            print(f"Mistral embedding error: {e}")
            return self._generate_mock_embedding(text)
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic mock embedding based on text hash
        Used when no real embedding model is available
        """
        import hashlib
        
        # Create deterministic hash
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Expand to 1536 dimensions
        embedding = []
        for i in range(self.dimension):
            byte_index = i % len(hash_bytes)
            value = (hash_bytes[byte_index] / 255.0) * 2 - 1  # Normalize to [-1, 1]
            embedding.append(value)
        
        return embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings


# Global instance (uses local Mistral)
embedding_service = EmbeddingService(
    model_type=os.getenv("EMBEDDING_MODEL_TYPE", "mistral_local")
)
