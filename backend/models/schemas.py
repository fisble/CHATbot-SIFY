"""
Pydantic schemas for the multi-agent storyboard system.
Defines all data models for agents, events, scenes, and storage.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class AgentName(str, Enum):
    """Names of available agents in the pipeline."""
    PREACT = "preAct"
    REACT = "ReAct"
    REFLECT = "ReFlect"
    TME = "TME"
    RAG = "RAG"
    SYSTEM = "system"


class AgentEventType(str, Enum):
    """Types of events that agents can emit."""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    PLAN = "plan"
    SCENE = "scene"
    MEMORY_UPDATE = "memory_update"
    RAG_RESULT = "rag_result"
    ERROR = "error"
    COMPLETE = "complete"
    STATUS = "status"


class ActionType(str, Enum):
    """Types of actions that ReAct agent can perform."""
    LLM_CALL = "llm_call"
    RAG_SEARCH = "rag_search"
    MEMORY_UPDATE = "memory_update"
    MEMORY_QUERY = "memory_query"


class AgentRequest(BaseModel):
    """Request to start the agent pipeline."""
    domain: str = Field(..., description="Domain type for storyboard generation")
    query: str = Field(..., description="User query describing the storyboard")
    session_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session identifier"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "product_demo",
                "query": "Create a storyboard for a smartphone app demo showing key features"
            }
        }


class AgentEvent(BaseModel):
    """Event emitted by an agent during processing."""
    agent: AgentName = Field(..., description="Name of the agent emitting the event")
    event: AgentEventType = Field(..., description="Type of event")
    content: str = Field(..., description="Event content/message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional event metadata"
    )
    
    def to_ws_message(self) -> Dict[str, Any]:
        """Convert to WebSocket message format."""
        return {
            "agent": self.agent.value,
            "event": self.event.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class AgentAction(BaseModel):
    """Action performed by ReAct agent."""
    action_type: ActionType = Field(..., description="Type of action")
    action_input: str = Field(..., description="Input for the action")
    reasoning: Optional[str] = Field(None, description="Reasoning behind the action")


class Scene(BaseModel):
    """A single scene in the storyboard."""
    scene_number: int = Field(..., description="Scene sequence number")
    title: str = Field(..., description="Scene title")
    description: str = Field(..., description="Detailed scene description")
    visual_elements: List[str] = Field(
        default_factory=list,
        description="Visual elements in the scene"
    )
    camera_direction: str = Field(default="", description="Camera movement/angle")
    dialogue: Optional[str] = Field(None, description="Any dialogue in the scene")
    sound_effects: Optional[str] = Field(None, description="Sound effects/music")
    duration_seconds: Optional[int] = Field(None, description="Scene duration")
    notes: Optional[str] = Field(None, description="Additional production notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "scene_number": 1,
                "title": "Opening Shot",
                "description": "Wide shot of the city skyline at dawn",
                "visual_elements": ["skyline", "sunrise", "clouds"],
                "camera_direction": "Slow pan left to right",
                "duration_seconds": 5
            }
        }


class MasterPlan(BaseModel):
    """Master plan created by preAct agent."""
    title: str = Field(..., description="Storyboard title")
    domain: str = Field(..., description="Domain type")
    total_scenes: int = Field(..., description="Total number of planned scenes")
    world_setting: str = Field(..., description="World/environment description")
    characters: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Character descriptions"
    )
    visual_style: str = Field(..., description="Overall visual style")
    camera_rules: str = Field(..., description="Camera guidelines")
    tone: str = Field(..., description="Tone and mood")
    scene_outline: List[str] = Field(
        default_factory=list,
        description="Brief outline of each scene"
    )


class Storyboard(BaseModel):
    """Complete storyboard with all scenes."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="Associated session ID")
    domain: str = Field(..., description="Domain type")
    query: str = Field(..., description="Original user query")
    title: str = Field(..., description="Storyboard title")
    master_plan: Optional[MasterPlan] = Field(None, description="Master plan from preAct")
    scenes: List[Scene] = Field(default_factory=list, description="All scenes")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="in_progress", description="Generation status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "product_demo",
                "query": "Create a smartphone demo",
                "title": "Smartphone App Demo Storyboard",
                "status": "complete"
            }
        }


class MemoryEntry(BaseModel):
    """Memory entry stored in TME."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="Session this memory belongs to")
    memory_type: str = Field(..., description="Type of memory (character, world, scene, etc.)")
    content: str = Field(..., description="Memory content")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    relevance_score: Optional[float] = Field(None, description="Relevance score from retrieval")
    
    class Config:
        json_schema_extra = {
            "example": {
                "memory_type": "character",
                "content": "Main character: A young entrepreneur with innovative ideas",
                "tags": ["character", "protagonist"]
            }
        }


class RAGResult(BaseModel):
    """Result from RAG retrieval."""
    content: str = Field(..., description="Retrieved content")
    source: Optional[str] = Field(None, description="Source URL or reference")
    relevance_score: float = Field(..., description="Relevance score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatMessage(BaseModel):
    """Chat message for history storage."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="Session ID")
    agent: AgentName = Field(..., description="Agent that generated the message")
    event_type: AgentEventType = Field(..., description="Event type")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(None)


class SessionInfo(BaseModel):
    """User session information."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: Optional[str] = Field(None, description="Selected domain")
    query: Optional[str] = Field(None, description="User query")
    status: str = Field(default="created", description="Session status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    storyboard_id: Optional[str] = Field(None, description="Associated storyboard ID")

