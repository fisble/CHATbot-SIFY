"""
OpenAI LLM wrapper service with async streaming support.
Provides a unified interface for text generation and embeddings.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from openai import AsyncOpenAI
import asyncio
from functools import lru_cache

from config import settings


class LLMService:
    """
    Async OpenAI LLM service with streaming support.
    
    Provides methods for:
    - Streaming text generation
    - Non-streaming text generation
    - Text embeddings
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Initialize the LLM service.
        
        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
            temperature: Generation temperature (defaults to settings)
            max_tokens: Maximum tokens (defaults to settings)
            embedding_model: Embedding model (defaults to settings)
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.temperature = temperature if temperature is not None else settings.openai_temperature
        self.max_tokens = max_tokens or settings.openai_max_tokens
        self.embedding_model = embedding_model or settings.openai_embedding_model
        
        # Use configured base URL
        self.base_url = settings.openai_base_url
        
        # Debug: verify API key is loaded
        if not self.api_key:
            print("WARNING: OpenAI API key is empty!")
        else:
            print(f"LLM Service initialized: model={self.model}, base_url={self.base_url}, api_key={self.api_key[:15]}***")
        
        # Add timeout to prevent hanging requests (30 seconds default for faster failure)
        import httpx
        timeout = httpx.Timeout(30.0, connect=5.0)  # 30s total, 5s connect (reduced for faster error detection)
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=2
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate text with streaming output.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            stop_sequences: Stop sequences
            
        Yields:
            str: Text chunks as they are generated
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stop=stop_sequences,
                stream=True
            )
            
            chunk_count = 0
            async for chunk in stream:
                # Defensive check: handle cases where choices array is empty or structure is different
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta if hasattr(chunk.choices[0], 'delta') else None
                    if delta and hasattr(delta, 'content') and delta.content:
                        chunk_count += 1
                        yield delta.content
                # If chunk has no valid content, skip it (some chunks are just metadata)
                    
        except asyncio.TimeoutError:
            print(f"[LLM] Timeout error in generate_stream")
            yield "[Error: Request timed out. Please try again.]"
        except Exception as e:
            print(f"[LLM] Error in generate_stream: {str(e)}")
            yield f"[Error: {str(e)}]"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text without streaming.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            stop_sequences: Stop sequences
            response_format: Response format (e.g., {"type": "json_object"})
            
        Returns:
            str: Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        
        if stop_sequences:
            kwargs["stop"] = stop_sequences
            
        if response_format:
            kwargs["response_format"] = response_format
        
        try:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except asyncio.TimeoutError:
            print(f"[LLM] Timeout error in generate")
            return "[Error: Request timed out. Please try again.]"
        except Exception as e:
            print(f"[LLM] Error in generate: {str(e)}")
            return f"[Error: {str(e)}]"
    
    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text with conversation history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            str: Generated text
        """
        full_messages = []
        
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        
        full_messages.extend(messages)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[Error: {str(e)}]"
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            # Return empty vector on error
            return []
    
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embedding vectors for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors
        """
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            # Return empty vectors on error
            return [[] for _ in texts]
    
    async def collect_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Convenience method to collect all chunks from stream into a single string.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            str: Complete generated text
        """
        chunks = []
        async for chunk in self.generate_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            chunks.append(chunk)
        return "".join(chunks)


# Singleton instance - reset on module reload
_llm_service: Optional[LLMService] = None


def get_llm_service(force_new: bool = False) -> LLMService:
    """
    Get the LLM service instance.
    
    Args:
        force_new: If True, create a new instance
    
    Returns:
        LLMService: The LLM service instance
    """
    global _llm_service
    if _llm_service is None or force_new:
        _llm_service = LLMService()
    return _llm_service


def reset_llm_service():
    """Reset the LLM service singleton (useful for testing/reload)."""
    global _llm_service
    _llm_service = None

