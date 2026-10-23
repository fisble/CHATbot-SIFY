"""
MongoDB storage service for sessions, chat history, and storyboards.
Handles persistent storage of user data and generated content.
"""

from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from datetime import datetime
import uuid

from config import settings
from models.schemas import (
    SessionInfo,
    ChatMessage,
    Storyboard,
    AgentEvent,
    AgentName,
    AgentEventType
)


class MongoDBStorage:
    """
    MongoDB storage service for persistent data.
    
    Manages three collections:
    - sessions: User session information
    - chat_history: Agent events and messages
    - storyboards: Final generated storyboards
    """
    
    def __init__(
        self,
        mongodb_uri: Optional[str] = None,
        database_name: Optional[str] = None
    ):
        """
        Initialize MongoDB storage.
        
        Args:
            mongodb_uri: MongoDB connection URI
            database_name: Database name
        """
        self.mongodb_uri = mongodb_uri or settings.mongodb_uri
        self.database_name = database_name or settings.mongodb_database
        
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection to MongoDB."""
        if self._connected:
            return
        
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[self.database_name]
        
        # Create indexes
        await self._create_indexes()
        
        self._connected = True
    
    async def _create_indexes(self) -> None:
        """Create database indexes for efficient queries."""
        # Sessions collection indexes
        await self.db.sessions.create_index("session_id", unique=True)
        await self.db.sessions.create_index("created_at")
        
        # Chat history collection indexes
        await self.db.chat_history.create_index("session_id")
        await self.db.chat_history.create_index([("session_id", 1), ("timestamp", 1)])
        
        # Storyboards collection indexes
        await self.db.storyboards.create_index("id", unique=True)
        await self.db.storyboards.create_index("session_id")
        await self.db.storyboards.create_index("created_at")
    
    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
    
    # ==================== Session Operations ====================
    
    async def create_session(
        self,
        domain: Optional[str] = None,
        query: Optional[str] = None
    ) -> SessionInfo:
        """
        Create a new session.
        
        Args:
            domain: Selected domain
            query: User query
            
        Returns:
            SessionInfo: Created session
        """
        await self.connect()
        
        session = SessionInfo(
            session_id=str(uuid.uuid4()),
            domain=domain,
            query=query,
            status="created"
        )
        
        await self.db.sessions.insert_one(session.model_dump())
        return session
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[SessionInfo]: Session if found
        """
        await self.connect()
        
        doc = await self.db.sessions.find_one({"session_id": session_id})
        if doc:
            doc.pop('_id', None)
            return SessionInfo(**doc)
        return None
    
    async def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update session fields.
        
        Args:
            session_id: Session identifier
            updates: Fields to update
            
        Returns:
            bool: True if update succeeded
        """
        await self.connect()
        
        updates["updated_at"] = datetime.utcnow()
        result = await self.db.sessions.update_one(
            {"session_id": session_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and associated data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deletion succeeded
        """
        await self.connect()
        
        # Delete session
        result = await self.db.sessions.delete_one({"session_id": session_id})
        
        # Delete associated chat history
        await self.db.chat_history.delete_many({"session_id": session_id})
        
        # Delete associated storyboards
        await self.db.storyboards.delete_many({"session_id": session_id})
        
        return result.deleted_count > 0
    
    async def list_sessions(
        self,
        limit: int = 50,
        skip: int = 0
    ) -> List[SessionInfo]:
        """
        List sessions with pagination.
        
        Args:
            limit: Maximum sessions to return
            skip: Number of sessions to skip
            
        Returns:
            List[SessionInfo]: List of sessions
        """
        await self.connect()
        
        cursor = self.db.sessions.find().sort("created_at", -1).skip(skip).limit(limit)
        sessions = []
        async for doc in cursor:
            doc.pop('_id', None)
            sessions.append(SessionInfo(**doc))
        return sessions
    
    # ==================== Chat History Operations ====================
    
    async def add_chat_message(
        self,
        session_id: str,
        agent: AgentName,
        event_type: AgentEventType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Add a chat message to history.
        
        Args:
            session_id: Session identifier
            agent: Agent name
            event_type: Event type
            content: Message content
            metadata: Optional metadata
            
        Returns:
            ChatMessage: Created message
        """
        await self.connect()
        
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            agent=agent,
            event_type=event_type,
            content=content,
            metadata=metadata
        )
        
        await self.db.chat_history.insert_one(message.model_dump())
        return message
    
    async def add_agent_event(
        self,
        session_id: str,
        event: AgentEvent
    ) -> ChatMessage:
        """
        Add an agent event to chat history.
        
        Args:
            session_id: Session identifier
            event: Agent event
            
        Returns:
            ChatMessage: Created message
        """
        return await self.add_chat_message(
            session_id=session_id,
            agent=event.agent,
            event_type=event.event,
            content=event.content,
            metadata=event.metadata
        )
    
    async def get_chat_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Get chat history for a session.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on messages
            
        Returns:
            List[ChatMessage]: Chat messages
        """
        await self.connect()
        
        query = self.db.chat_history.find(
            {"session_id": session_id}
        ).sort("timestamp", 1)
        
        if limit:
            query = query.limit(limit)
        
        messages = []
        async for doc in query:
            doc.pop('_id', None)
            # Convert string enums back to enum types
            doc['agent'] = AgentName(doc['agent'])
            doc['event_type'] = AgentEventType(doc['event_type'])
            messages.append(ChatMessage(**doc))
        
        return messages
    
    async def get_recent_events(
        self,
        session_id: str,
        agent: Optional[AgentName] = None,
        event_type: Optional[AgentEventType] = None,
        limit: int = 10
    ) -> List[ChatMessage]:
        """
        Get recent events with optional filters.
        
        Args:
            session_id: Session identifier
            agent: Optional agent filter
            event_type: Optional event type filter
            limit: Maximum events to return
            
        Returns:
            List[ChatMessage]: Recent events
        """
        await self.connect()
        
        filter_query = {"session_id": session_id}
        if agent:
            filter_query["agent"] = agent.value
        if event_type:
            filter_query["event_type"] = event_type.value
        
        cursor = self.db.chat_history.find(filter_query).sort("timestamp", -1).limit(limit)
        
        messages = []
        async for doc in cursor:
            doc.pop('_id', None)
            doc['agent'] = AgentName(doc['agent'])
            doc['event_type'] = AgentEventType(doc['event_type'])
            messages.append(ChatMessage(**doc))
        
        return list(reversed(messages))
    
    # ==================== Storyboard Operations ====================
    
    async def save_storyboard(self, storyboard: Storyboard) -> str:
        """
        Save a storyboard.
        
        Args:
            storyboard: Storyboard to save
            
        Returns:
            str: Storyboard ID
        """
        await self.connect()
        
        doc = storyboard.model_dump()
        
        # Use upsert to update if exists
        await self.db.storyboards.update_one(
            {"id": storyboard.id},
            {"$set": doc},
            upsert=True
        )
        
        # Update session with storyboard reference
        await self.update_session(
            storyboard.session_id,
            {"storyboard_id": storyboard.id}
        )
        
        return storyboard.id
    
    async def get_storyboard(self, storyboard_id: str) -> Optional[Storyboard]:
        """
        Get storyboard by ID.
        
        Args:
            storyboard_id: Storyboard identifier
            
        Returns:
            Optional[Storyboard]: Storyboard if found
        """
        await self.connect()
        
        doc = await self.db.storyboards.find_one({"id": storyboard_id})
        if doc:
            doc.pop('_id', None)
            return Storyboard(**doc)
        return None
    
    async def get_session_storyboard(self, session_id: str) -> Optional[Storyboard]:
        """
        Get storyboard for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Storyboard]: Storyboard if found
        """
        await self.connect()
        
        doc = await self.db.storyboards.find_one({"session_id": session_id})
        if doc:
            doc.pop('_id', None)
            return Storyboard(**doc)
        return None
    
    async def update_storyboard(
        self,
        storyboard_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update storyboard fields.
        
        Args:
            storyboard_id: Storyboard identifier
            updates: Fields to update
            
        Returns:
            bool: True if update succeeded
        """
        await self.connect()
        
        updates["updated_at"] = datetime.utcnow()
        result = await self.db.storyboards.update_one(
            {"id": storyboard_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    async def list_storyboards(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Storyboard]:
        """
        List storyboards with optional domain filter.
        
        Args:
            domain: Optional domain filter
            limit: Maximum storyboards to return
            skip: Number to skip
            
        Returns:
            List[Storyboard]: List of storyboards
        """
        await self.connect()
        
        filter_query = {}
        if domain:
            filter_query["domain"] = domain
        
        cursor = self.db.storyboards.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
        
        storyboards = []
        async for doc in cursor:
            doc.pop('_id', None)
            storyboards.append(Storyboard(**doc))
        
        return storyboards


# Singleton instance
_mongodb_service: Optional[MongoDBStorage] = None


async def get_mongodb_service() -> MongoDBStorage:
    """
    Get the MongoDB service singleton instance.
    
    Returns:
        MongoDBStorage: The MongoDB service instance
    """
    global _mongodb_service
    if _mongodb_service is None:
        _mongodb_service = MongoDBStorage()
        await _mongodb_service.connect()
    return _mongodb_service

