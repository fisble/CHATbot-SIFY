"""
Base agent class for the multi-agent storyboard system.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any
from dataclasses import dataclass, field

from models.schemas import AgentEvent, AgentName, Storyboard, MasterPlan
from services.llm import LLMService, get_llm_service
from memory.tme import TaskMemoryEngine, get_tme_service
from rag.retriever import RAGRetriever, get_rag_service
from prompts.dynamic_prompt_builder import DynamicPromptBuilder, get_prompt_builder


@dataclass
class AgentContext:
    """
    Context object passed between agents containing all necessary data.
    """
    session_id: str
    domain: str
    query: str
    master_plan: Optional[MasterPlan] = None
    storyboard: Optional[Storyboard] = None
    current_scene_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "session_id": self.session_id,
            "domain": self.domain,
            "query": self.query,
            "master_plan": self.master_plan.model_dump() if self.master_plan else None,
            "storyboard": self.storyboard.model_dump() if self.storyboard else None,
            "current_scene_index": self.current_scene_index,
            "metadata": self.metadata
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the pipeline.
    
    Provides common functionality and interface for:
    - LLM interactions
    - Memory management (TME)
    - RAG retrieval
    - Event streaming
    """
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        tme_service: Optional[TaskMemoryEngine] = None,
        rag_service: Optional[RAGRetriever] = None,
        prompt_builder: Optional[DynamicPromptBuilder] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            llm_service: LLM service instance
            tme_service: Task Memory Engine instance
            rag_service: RAG retriever instance
            prompt_builder: Dynamic prompt builder instance
        """
        self._llm_service = llm_service
        self._tme_service = tme_service
        self._rag_service = rag_service
        self._prompt_builder = prompt_builder
    
    @property
    def llm(self) -> LLMService:
        """Get LLM service, lazy loading if needed."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service
    
    @property
    def tme(self) -> TaskMemoryEngine:
        """Get TME service, lazy loading if needed."""
        if self._tme_service is None:
            self._tme_service = get_tme_service()
        return self._tme_service
    
    @property
    def rag(self) -> RAGRetriever:
        """Get RAG service, lazy loading if needed."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service
    
    @property
    def prompt_builder(self) -> DynamicPromptBuilder:
        """Get prompt builder, lazy loading if needed."""
        if self._prompt_builder is None:
            self._prompt_builder = get_prompt_builder()
        return self._prompt_builder
    
    @property
    @abstractmethod
    def name(self) -> AgentName:
        """Return the agent's name."""
        pass
    
    @abstractmethod
    async def run(self, context: AgentContext) -> AsyncGenerator[AgentEvent, None]:
        """
        Execute the agent's main logic.
        
        Args:
            context: Agent context containing all necessary data
            
        Yields:
            AgentEvent: Events generated during execution
        """
        pass
    
    def create_event(
        self,
        event_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentEvent:
        """
        Create an agent event.
        
        Args:
            event_type: Type of event
            content: Event content
            metadata: Optional metadata
            
        Returns:
            AgentEvent: Created event
        """
        from models.schemas import AgentEventType
        return AgentEvent(
            agent=self.name,
            event=AgentEventType(event_type),
            content=content,
            metadata=metadata
        )
    
    async def get_memory_context(
        self,
        session_id: str,
        query: str,
        n_results: int = 5
    ) -> str:
        """
        Get relevant memory context for a query.
        
        Args:
            session_id: Session identifier
            query: Context query
            n_results: Number of results
            
        Returns:
            str: Formatted memory context
        """
        memories = await self.tme.query_memories(
            session_id=session_id,
            query=query,
            n_results=n_results
        )
        
        if not memories:
            return "No relevant context from previous scenes."
        
        context_parts = []
        for memory in memories:
            context_parts.append(f"[{memory.memory_type}] {memory.content}")
        
        return "\n".join(context_parts)
    
    async def search_rag(
        self,
        query: str,
        domain: str,
        n_results: int = 3
    ) -> str:
        """
        Search RAG for relevant content.
        
        Args:
            query: Search query
            domain: Domain to search in
            n_results: Number of results
            
        Returns:
            str: Formatted RAG results
        """
        results = await self.rag.search(
            query=query,
            domain=domain,
            n_results=n_results
        )
        
        if not results:
            return "No relevant domain knowledge found."
        
        result_parts = []
        for r in results:
            source = r.source or "unknown"
            result_parts.append(f"[Source: {source}]\n{r.content}")
        
        return "\n\n".join(result_parts)
    
    async def update_memory(
        self,
        session_id: str,
        content: str,
        memory_type: str,
        tags: Optional[list] = None
    ) -> None:
        """
        Update memory with new information.
        
        Args:
            session_id: Session identifier
            content: Memory content
            memory_type: Type of memory
            tags: Optional tags
        """
        await self.tme.add_memory(
            session_id=session_id,
            content=content,
            memory_type=memory_type,
            tags=tags or []
        )

