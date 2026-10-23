"""
Task Memory Engine (TME) with ChromaDB for vector-based memory storage.
Manages agent context, character definitions, world settings, and scene memories.
"""

from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
import uuid
from datetime import datetime

from config import settings
from models.schemas import MemoryEntry
from services.llm import get_llm_service


class TaskMemoryEngine:
    """
    Task Memory Engine for storing and retrieving agent memories.
    
    Uses ChromaDB for vector-based semantic search of memories,
    enabling context-aware retrieval during content generation.
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialize the Task Memory Engine.
        
        Args:
            persist_directory: ChromaDB persistence directory
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = persist_directory or settings.chromadb_persist_dir
        self.collection_name = collection_name or settings.chromadb_tme_collection
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        self._llm_service = None
    
    @property
    def llm_service(self):
        """Lazy load LLM service."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service
    
    async def add_memory(
        self,
        session_id: str,
        content: str,
        memory_type: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Add a new memory entry.
        
        Args:
            session_id: Session identifier
            content: Memory content
            memory_type: Type of memory (character, world, scene, style, etc.)
            tags: Optional tags for filtering
            metadata: Optional additional metadata
            
        Returns:
            MemoryEntry: The created memory entry
        """
        memory_id = str(uuid.uuid4())
        tags = tags or []
        
        # Get embedding for the content
        embedding = await self.llm_service.get_embedding(content)
        
        # Prepare metadata
        doc_metadata = {
            "session_id": session_id,
            "memory_type": memory_type,
            "tags": ",".join(tags),
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        # Add to ChromaDB
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding] if embedding else None,
            documents=[content],
            metadatas=[doc_metadata]
        )
        
        return MemoryEntry(
            id=memory_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            tags=tags,
            created_at=datetime.utcnow()
        )
    
    async def query_memories(
        self,
        session_id: str,
        query: str,
        n_results: int = 5,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[MemoryEntry]:
        """
        Query memories using semantic search.
        
        Args:
            session_id: Session identifier
            query: Search query
            n_results: Number of results to return
            memory_type: Filter by memory type
            tags: Filter by tags
            
        Returns:
            List[MemoryEntry]: Matching memory entries
        """
        # Build where clause for filtering
        where_clause = {"session_id": session_id}
        
        if memory_type:
            where_clause["memory_type"] = memory_type
        
        # Get query embedding
        query_embedding = await self.llm_service.get_embedding(query)
        
        if not query_embedding:
            # Fall back to text search if embedding fails
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause
            )
        else:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause
            )
        
        # Convert results to MemoryEntry objects
        memories = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                content = results['documents'][0][i] if results['documents'] else ""
                distance = results['distances'][0][i] if results.get('distances') else 0
                
                # Convert distance to relevance score (1 - distance for cosine)
                relevance_score = 1 - distance if distance else 1.0
                
                tags_str = metadata.get('tags', '')
                tags_list = tags_str.split(',') if tags_str else []
                
                memories.append(MemoryEntry(
                    id=doc_id,
                    session_id=metadata.get('session_id', session_id),
                    memory_type=metadata.get('memory_type', 'unknown'),
                    content=content,
                    tags=tags_list,
                    relevance_score=relevance_score
                ))
        
        return memories
    
    async def get_session_memories(
        self,
        session_id: str,
        memory_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """
        Get all memories for a session.
        
        Args:
            session_id: Session identifier
            memory_type: Optional filter by memory type
            
        Returns:
            List[MemoryEntry]: All matching memories
        """
        where_clause = {"session_id": session_id}
        
        if memory_type:
            where_clause["memory_type"] = memory_type
        
        results = self.collection.get(
            where=where_clause
        )
        
        memories = []
        if results and results['ids']:
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                content = results['documents'][i] if results['documents'] else ""
                
                tags_str = metadata.get('tags', '')
                tags_list = tags_str.split(',') if tags_str else []
                
                memories.append(MemoryEntry(
                    id=doc_id,
                    session_id=metadata.get('session_id', session_id),
                    memory_type=metadata.get('memory_type', 'unknown'),
                    content=content,
                    tags=tags_list
                ))
        
        return memories
    
    async def update_memory(
        self,
        memory_id: str,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory identifier
            content: New content
            tags: New tags
            metadata: New metadata
            
        Returns:
            bool: True if update succeeded
        """
        try:
            # Get new embedding
            embedding = await self.llm_service.get_embedding(content)
            
            update_metadata = {
                "updated_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
            
            if tags is not None:
                update_metadata["tags"] = ",".join(tags)
            
            self.collection.update(
                ids=[memory_id],
                embeddings=[embedding] if embedding else None,
                documents=[content],
                metadatas=[update_metadata]
            )
            return True
        except Exception:
            return False
    
    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory entry.
        
        Args:
            memory_id: Memory identifier
            
        Returns:
            bool: True if deletion succeeded
        """
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
    
    async def clear_session_memories(self, session_id: str) -> int:
        """
        Clear all memories for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            int: Number of memories deleted
        """
        results = self.collection.get(
            where={"session_id": session_id}
        )
        
        if results and results['ids']:
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])
        
        return 0
    
    async def get_context_summary(
        self,
        session_id: str,
        query: str,
        max_memories: int = 10
    ) -> str:
        """
        Get a summarized context from relevant memories.
        
        Args:
            session_id: Session identifier
            query: Context query
            max_memories: Maximum memories to include
            
        Returns:
            str: Formatted context summary
        """
        memories = await self.query_memories(
            session_id=session_id,
            query=query,
            n_results=max_memories
        )
        
        if not memories:
            return "No relevant context found."
        
        # Group by memory type
        grouped: Dict[str, List[str]] = {}
        for memory in memories:
            if memory.memory_type not in grouped:
                grouped[memory.memory_type] = []
            grouped[memory.memory_type].append(memory.content)
        
        # Format summary
        summary_parts = []
        for memory_type, contents in grouped.items():
            summary_parts.append(f"## {memory_type.upper()}")
            for content in contents:
                summary_parts.append(f"- {content}")
        
        return "\n".join(summary_parts)


# Singleton instance
_tme_service: Optional[TaskMemoryEngine] = None


def get_tme_service() -> TaskMemoryEngine:
    """
    Get the TME service singleton instance.
    
    Returns:
        TaskMemoryEngine: The TME service instance
    """
    global _tme_service
    if _tme_service is None:
        _tme_service = TaskMemoryEngine()
    return _tme_service

