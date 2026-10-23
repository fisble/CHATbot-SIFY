"""
RAG Retriever with ChromaDB for domain-specific content retrieval.
Provides semantic search over pre-loaded reference documents.
"""

from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
import uuid
from datetime import datetime

from config import settings
from models.schemas import RAGResult
from services.llm import get_llm_service


class RAGRetriever:
    """
    RAG Retriever for domain-specific content retrieval.
    
    Uses ChromaDB to store and retrieve reference documents
    that provide context for AI-assisted content generation.
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialize the RAG Retriever.
        
        Args:
            persist_directory: ChromaDB persistence directory
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = persist_directory or settings.chromadb_persist_dir
        self.collection_name = collection_name or settings.chromadb_rag_collection
        
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
        self._initialized = False
    
    @property
    def llm_service(self):
        """Lazy load LLM service."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service
    
    async def initialize_domain_content(self) -> None:
        """
        Initialize the RAG collection with domain-specific reference content.
        This should be called once during application startup.
        """
        if self._initialized:
            return
        
        # Check if collection already has documents
        count = self.collection.count()
        if count > 0:
            self._initialized = True
            return
        
        # Domain-specific reference content
        domain_content = self._get_domain_reference_content()
        
        for domain, documents in domain_content.items():
            for doc in documents:
                await self.add_document(
                    content=doc["content"],
                    domain=domain,
                    source=doc.get("source", f"{domain}_reference"),
                    metadata=doc.get("metadata", {})
                )
        
        self._initialized = True
    
    def _get_domain_reference_content(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get pre-defined domain reference content for general AI assistance."""
        return {
            "software": [
                {
                    "content": "Software development best practices include writing clean, maintainable code with proper documentation. Follow SOLID principles and design patterns appropriate to the problem domain.",
                    "source": "software_dev_guide",
                    "metadata": {"category": "development"}
                },
                {
                    "content": "Code reviews should focus on correctness, readability, and maintainability. Look for potential bugs, security issues, and opportunities for optimization.",
                    "source": "code_review_guide",
                    "metadata": {"category": "quality"}
                },
                {
                    "content": "API design should follow RESTful conventions: use proper HTTP methods, meaningful status codes, consistent naming, and comprehensive documentation.",
                    "source": "api_design_guide",
                    "metadata": {"category": "architecture"}
                }
            ],
            "education": [
                {
                    "content": "Educational content should follow the 'Tell-Show-Do' methodology. First explain the concept, then demonstrate with examples, finally provide practice opportunities.",
                    "source": "education_methodology",
                    "metadata": {"category": "pedagogy"}
                },
                {
                    "content": "Use analogies and real-world examples to explain complex concepts. Break information into digestible chunks. Include summaries and key takeaways.",
                    "source": "instructional_design",
                    "metadata": {"category": "design"}
                },
                {
                    "content": "Effective learning materials include clear objectives, structured progression from simple to complex, practice exercises, and assessment opportunities.",
                    "source": "curriculum_design",
                    "metadata": {"category": "structure"}
                }
            ],
            "healthcare": [
                {
                    "content": "Medical content requires accuracy, proper citations, and appropriate disclaimers. Always recommend consulting healthcare professionals for personal medical decisions.",
                    "source": "medical_guidelines",
                    "metadata": {"category": "compliance"}
                },
                {
                    "content": "Patient education materials should use plain language (6th-grade reading level). Explain procedures step-by-step with clear expectations and warning signs.",
                    "source": "patient_education",
                    "metadata": {"category": "communication"}
                },
                {
                    "content": "Healthcare information must balance accuracy with accessibility. Use proper medical terminology but also provide lay explanations.",
                    "source": "health_communication",
                    "metadata": {"category": "writing"}
                }
            ],
            "marketing": [
                {
                    "content": "Marketing content should establish clear value propositions. Use the AIDA framework: Attention (hook), Interest (problem), Desire (benefits), Action (call to action).",
                    "source": "marketing_framework",
                    "metadata": {"category": "strategy"}
                },
                {
                    "content": "Effective marketing uses storytelling: identify the audience's pain points, present solutions, and demonstrate transformation through your product/service.",
                    "source": "storytelling_marketing",
                    "metadata": {"category": "narrative"}
                },
                {
                    "content": "Brand consistency is crucial: maintain consistent voice, messaging, and visual identity across all content. Know your target audience deeply.",
                    "source": "brand_guidelines",
                    "metadata": {"category": "branding"}
                }
            ],
            "finance": [
                {
                    "content": "Financial analysis should include clear methodology, data sources, assumptions, and limitations. Present findings with appropriate context and caveats.",
                    "source": "financial_analysis_guide",
                    "metadata": {"category": "analysis"}
                },
                {
                    "content": "Investment advice requires disclaimers about risk. Past performance doesn't guarantee future results. Consider individual circumstances and risk tolerance.",
                    "source": "investment_guidelines",
                    "metadata": {"category": "compliance"}
                },
                {
                    "content": "Financial reports should be clear, accurate, and compliant with relevant standards (GAAP, IFRS). Include executive summaries for non-technical stakeholders.",
                    "source": "financial_reporting",
                    "metadata": {"category": "reporting"}
                }
            ],
            "legal": [
                {
                    "content": "Legal content must include disclaimers that it is not legal advice. Recommend consulting qualified attorneys for specific situations.",
                    "source": "legal_disclaimer",
                    "metadata": {"category": "compliance"}
                },
                {
                    "content": "Legal documents should be precise and unambiguous. Define terms clearly, use consistent language, and structure content logically.",
                    "source": "legal_writing",
                    "metadata": {"category": "writing"}
                },
                {
                    "content": "Contract analysis should identify key terms, obligations, rights, risks, and potential issues. Highlight areas requiring negotiation or clarification.",
                    "source": "contract_analysis",
                    "metadata": {"category": "analysis"}
                }
            ],
            "general": [
                {
                    "content": "Clear communication requires knowing your audience, organizing information logically, using appropriate language, and providing actionable insights.",
                    "source": "communication_guide",
                    "metadata": {"category": "writing"}
                },
                {
                    "content": "Problem-solving follows a structured approach: define the problem, gather information, generate solutions, evaluate options, implement, and review results.",
                    "source": "problem_solving",
                    "metadata": {"category": "methodology"}
                },
                {
                    "content": "Research should use credible sources, cross-reference information, acknowledge limitations, and present findings objectively with proper attribution.",
                    "source": "research_methodology",
                    "metadata": {"category": "research"}
                }
            ]
        }
    
    async def add_document(
        self,
        content: str,
        domain: str,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a document to the RAG collection.
        
        Args:
            content: Document content
            domain: Domain category
            source: Source URL or reference
            metadata: Additional metadata
            
        Returns:
            str: Document ID
        """
        doc_id = str(uuid.uuid4())
        
        # Get embedding
        embedding = await self.llm_service.get_embedding(content)
        
        # Prepare metadata
        doc_metadata = {
            "domain": domain,
            "source": source or "unknown",
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        # Add to ChromaDB
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding] if embedding else None,
            documents=[content],
            metadatas=[doc_metadata]
        )
        
        return doc_id
    
    async def search(
        self,
        query: str,
        domain: Optional[str] = None,
        n_results: int = 5
    ) -> List[RAGResult]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            domain: Optional domain filter
            n_results: Number of results to return
            
        Returns:
            List[RAGResult]: Matching documents with relevance scores
        """
        # Build where clause
        where_clause = None
        if domain:
            where_clause = {"domain": domain}
        
        # Get query embedding
        query_embedding = await self.llm_service.get_embedding(query)
        
        if not query_embedding:
            # Fall back to text search
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
        
        # Convert to RAGResult objects
        rag_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                content = results['documents'][0][i] if results['documents'] else ""
                distance = results['distances'][0][i] if results.get('distances') else 0
                
                # Convert distance to relevance score
                relevance_score = 1 - distance if distance else 1.0
                
                rag_results.append(RAGResult(
                    content=content,
                    source=metadata.get('source'),
                    relevance_score=relevance_score,
                    metadata=metadata
                ))
        
        return rag_results
    
    async def search_with_context(
        self,
        query: str,
        domain: str,
        context: str,
        n_results: int = 3
    ) -> List[RAGResult]:
        """
        Search with additional context for better results.
        
        Args:
            query: Search query
            domain: Domain filter
            context: Additional context to enhance search
            n_results: Number of results
            
        Returns:
            List[RAGResult]: Matching documents
        """
        # Combine query with context for better semantic matching
        enhanced_query = f"{query}\n\nContext: {context}"
        return await self.search(enhanced_query, domain, n_results)
    
    async def get_domain_documents(self, domain: str) -> List[RAGResult]:
        """
        Get all documents for a specific domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List[RAGResult]: All domain documents
        """
        results = self.collection.get(
            where={"domain": domain}
        )
        
        rag_results = []
        if results and results['ids']:
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                content = results['documents'][i] if results['documents'] else ""
                
                rag_results.append(RAGResult(
                    content=content,
                    source=metadata.get('source'),
                    relevance_score=1.0,
                    metadata=metadata
                ))
        
        return rag_results
    
    def get_document_count(self, domain: Optional[str] = None) -> int:
        """
        Get the number of documents in the collection.
        
        Args:
            domain: Optional domain filter
            
        Returns:
            int: Document count
        """
        if domain:
            results = self.collection.get(where={"domain": domain})
            return len(results['ids']) if results and results['ids'] else 0
        return self.collection.count()


# Singleton instance
_rag_service: Optional[RAGRetriever] = None


def get_rag_service() -> RAGRetriever:
    """
    Get the RAG service singleton instance.
    
    Returns:
        RAGRetriever: The RAG service instance
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGRetriever()
    return _rag_service

