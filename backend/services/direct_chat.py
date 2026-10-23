"""
Direct chat service for normal (non-multi-agent) responses.
Provides simple LLM-based chat without agent orchestration.
Can auto-detect domain from user query for context-aware responses.
"""

from typing import AsyncGenerator, Optional, Dict, Any
from services.llm import get_llm_service


# Domain detection patterns (imported logic from PreAct)
DOMAIN_PATTERNS = {
    "healthcare": ["medical", "health", "clinical", "patient", "hospital", "doctor", "nurse", "diagnosis", "treatment", "pharma", "drug"],
    "finance": ["finance", "banking", "investment", "stock", "trading", "loan", "credit", "insurance", "accounting", "budget", "revenue"],
    "hr": ["hr", "human resources", "employee", "hiring", "recruitment", "onboarding", "payroll", "benefits", "performance review", "talent"],
    "cloud": ["cloud", "aws", "azure", "gcp", "kubernetes", "docker", "devops", "infrastructure", "serverless", "microservices"],
    "software": ["software", "development", "programming", "code", "api", "database", "testing", "agile", "scrum", "deployment"],
    "sales": ["sales", "crm", "lead", "pipeline", "prospect", "deal", "quota", "revenue", "customer", "conversion"],
    "education": ["education", "learning", "teaching", "course", "curriculum", "student", "training", "tutorial", "lesson", "classroom"],
    "marketing": ["marketing", "campaign", "brand", "advertising", "social media", "seo", "content", "promotion", "audience", "engagement"],
    "legal": ["legal", "law", "contract", "compliance", "regulation", "litigation", "attorney", "court", "rights", "policy"],
    "manufacturing": ["manufacturing", "production", "factory", "assembly", "quality control", "supply chain", "inventory", "lean", "six sigma"],
}


class DirectChatService:
    """
    Direct chat service for normal chatbot responses.
    
    This provides a simpler alternative to the multi-agent pipeline,
    generating responses in a single LLM call without the
    preAct → ReAct → ReFlect orchestration.
    
    Features:
    - Auto-detect domain from user query
    - Context-aware responses based on detected domain
    - Normal chatbot mode (no storyboard generation by default)
    """
    
    SYSTEM_PROMPT = """You are ThinkerLLM, an intelligent AI assistant.

You help users with their questions by:
1. Understanding their request COMPLETELY and thoroughly
2. Providing COMPREHENSIVE, COMPLETE responses that address ALL aspects
3. Following ALL instructions provided by the user
4. Ensuring your response is END-TO-END and fully satisfies the request
5. Using markdown formatting for code blocks, lists, and headers

CRITICAL RULES:
- Read ALL instructions in the user's request carefully - do not skip any parts
- Generate COMPLETE responses - do NOT truncate or stop early
- Address EVERY section, requirement, question, and instruction asked
- If the user provides detailed instructions with multiple steps or sections, complete ALL of them
- Ensure your response fully satisfies the user's goals and requirements
- Do NOT assume the user wants a video, storyboard, or any media production
- Do NOT mention durations, scenes, camera angles, or video formats unless EXPLICITLY asked
- Do NOT default to "2 minute video" or any video length - this is NOT a video production tool unless the user asks for one
- Only create storyboards/videos if the user EXPLICITLY uses words like "video", "storyboard", "animation", "film"

RESPONSE COMPLETENESS:
- Provide FULL, END-TO-END answers that cover every aspect requested
- If the user asks for multiple sections, include ALL sections completely
- If the user asks for a step-by-step guide, provide ALL steps in detail
- If the user asks for architecture, implementation, examples, etc., provide ALL requested components
- Never stop mid-response - ensure your answer is fully complete before ending

Just answer questions naturally and comprehensively. If asked about a topic, explain it thoroughly. If asked to create something, create what they asked for completely - not a video about it."""
    
    STORYBOARD_SYSTEM_PROMPT = """You are a professional storyboard creator. Generate detailed, production-ready storyboards ONLY when the user explicitly asks for a storyboard.

Your storyboards should include:
1. A compelling title
2. Overall visual style and tone
3. Detailed scene breakdowns with:
   - Scene number and title
   - Visual description
   - Camera directions
   - Dialogue (if applicable)
   - Sound/music notes
   - Duration estimate

Be creative, specific, and professional."""

    def __init__(self):
        """Initialize the direct chat service."""
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM service."""
        if self._llm is None:
            self._llm = get_llm_service()
        return self._llm
    
    def detect_domain(self, query: str) -> str:
        """
        Auto-detect domain from user query.
        
        Args:
            query: User query
            
        Returns:
            str: Detected domain or 'general'
        """
        query_lower = query.lower()
        domain_scores = {}
        
        for domain, keywords in DOMAIN_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "general"
    
    def is_storyboard_request(self, query: str) -> bool:
        """
        Check if the user is EXPLICITLY asking for a storyboard or video.
        
        This should be restrictive - only return True if the user clearly wants
        video/storyboard content, not just any request.
        
        Args:
            query: User query
            
        Returns:
            bool: True if storyboard/video is explicitly requested
        """
        # Only trigger for very explicit video/storyboard requests
        explicit_video_keywords = [
            "storyboard", "video script", "scene breakdown", 
            "create a video", "make a video", "video production",
            "animation script", "film script", "movie script",
            "create scenes for", "video storyboard"
        ]
        query_lower = query.lower()
        
        # Must contain explicit video/storyboard keywords
        has_explicit_keyword = any(kw in query_lower for kw in explicit_video_keywords)
        
        # Exclude common false positives - questions ABOUT videos, not requests TO CREATE videos
        false_positive_patterns = [
            "what is", "how does", "explain", "tell me about",
            "can you help", "i need help with", "question about"
        ]
        is_likely_question = any(pattern in query_lower for pattern in false_positive_patterns)
        
        return has_explicit_keyword and not is_likely_question
    
    def should_use_web_search(self, query: str) -> bool:
        """
        Lightweight heuristic to decide if web search may be useful.
        This does NOT affect existing logic unless explicitly used.
        """
        triggers = [
            "latest",
            "current",
            "recent",
            "today",
            "version",
            "news",
            "release",
            "update",
            "statistics",
            "according to",
            "data",
        ]
        q = query.lower()
        return any(t in q for t in triggers)
    
    def build_prompt(self, query: str, domain: Optional[str] = None, mode: str = "chat") -> str:
        """
        Build the prompt for direct chat or storyboard generation.
        
        Args:
            query: User query
            domain: Domain type (optional, will auto-detect if not provided)
            mode: "chat" for normal chat, "storyboard" for storyboard generation
            
        Returns:
            str: Formatted prompt
        """
        # Auto-detect domain if not provided
        if not domain or domain == "auto":
            domain = self.detect_domain(query)
        
        if mode == "storyboard":
            return self._build_storyboard_prompt(domain, query)
        else:
            return self._build_chat_prompt(domain, query)
    
    def _build_chat_prompt(self, domain: str, query: str) -> str:
        """Build prompt for normal chat mode - comprehensive and complete."""
        return f"""{query}

---
IMPORTANT INSTRUCTIONS:
1. Read ALL instructions in the user's request carefully - pay attention to every detail
2. Provide a COMPLETE, END-TO-END response that addresses EVERY aspect requested
3. Do NOT stop mid-response - ensure all sections are fully completed
4. If the user requested specific sections, steps, or components, include ALL of them completely
5. Use markdown formatting for code blocks, headers, lists, and structure
6. Be thorough and comprehensive - complete every part of the request
7. Ensure your response fully satisfies the user's goals and requirements

Respond with the FULL answer covering all requested points completely."""
    
    def _build_storyboard_prompt(self, domain: str, query: str) -> str:
        """Build prompt for storyboard generation mode - only when explicitly requested."""
        return f"""## STORYBOARD REQUEST

**User Request:** {query}

## YOUR TASK

Generate a complete storyboard with 5-7 scenes. For each scene include:
- Scene number and title
- Detailed visual description (2-3 sentences)
- Camera direction
- Dialogue (if any)
- Sound/music notes
- Estimated duration in seconds

Format your response as a well-structured storyboard document."""
    
    async def generate(
        self,
        query: str,
        domain: Optional[str] = None,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Generate a response using direct LLM call.
        Auto-detects domain and mode (chat vs storyboard).
        
        Args:
            query: User query
            domain: Domain type (optional, will auto-detect)
            stream: Whether to stream the response
            
        Yields:
            str: Response chunks
        """
        # Auto-detect domain if not provided
        detected_domain = domain if domain and domain != "auto" else self.detect_domain(query)
        
        # Determine mode based on query
        mode = "storyboard" if self.is_storyboard_request(query) else "chat"
        system_prompt = self.STORYBOARD_SYSTEM_PROMPT if mode == "storyboard" else self.SYSTEM_PROMPT
        
        prompt = self.build_prompt(query, detected_domain, mode)
        
        if stream:
            async for chunk in self.llm.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=30000  # Explicitly set high limit for comprehensive responses
            ):
                yield chunk
        else:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3
            )
            yield response
    
    async def generate_full(
        self, 
        query: str, 
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete response without streaming.
        Auto-detects domain and mode.
        
        Args:
            query: User query
            domain: Domain type (optional, will auto-detect)
            
        Returns:
            Dict containing response and metadata
        """
        # Auto-detect domain if not provided
        detected_domain = domain if domain and domain != "auto" else self.detect_domain(query)
        
        # Determine mode based on query
        mode = "storyboard" if self.is_storyboard_request(query) else "chat"
        system_prompt = self.STORYBOARD_SYSTEM_PROMPT if mode == "storyboard" else self.SYSTEM_PROMPT
        
        prompt = self.build_prompt(query, detected_domain, mode)
        
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=30000  # Explicitly set high limit for comprehensive responses
        )
        
        return {
            "response": response,
            "detected_domain": detected_domain,
            "mode": mode,
            "is_storyboard": mode == "storyboard"
        }


# Singleton instance
_direct_chat_service: Optional[DirectChatService] = None


def get_direct_chat_service() -> DirectChatService:
    """Get the direct chat service singleton."""
    global _direct_chat_service
    if _direct_chat_service is None:
        _direct_chat_service = DirectChatService()
    return _direct_chat_service

