"""
Conversation Memory
===================

Tracks conversation history and entities for multi-turn support.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ..config.logging_config import setup_logger
from ..config.settings import MAX_CONVERSATION_HISTORY, MAX_TRACKED_ENTITIES

logger = setup_logger("conversation_memory")

@dataclass
class Message:
    """Single conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str

@dataclass
class Session:
    """Conversation session."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    tracked_entities: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

class ConversationMemory:
    """
    Manages conversation history and entity tracking.
    """
    
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def add_turn(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
        entities: List[str] = None
    ):
        """
        Add a conversation turn.
        
        Args:
            session_id: Session identifier
            user_query: User query
            assistant_response: Assistant response
            entities: Extracted entities from this turn
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id=session_id)
            logger.info(f"Created new session: {session_id}")
        
        session = self.sessions[session_id]
        
        # Add messages
        session.messages.append(Message("user", user_query, datetime.now().isoformat()))
        session.messages.append(Message("assistant", assistant_response, datetime.now().isoformat()))
        
        # Track entities
        if entities:
            for entity in entities:
                if entity not in session.tracked_entities:
                    session.tracked_entities.append(entity)
        
        # Limit history
        if len(session.messages) > MAX_CONVERSATION_HISTORY * 2:  # *2 for user+assistant pairs
            session.messages = session.messages[-MAX_CONVERSATION_HISTORY * 2:]
        
        # Limit tracked entities
        if len(session.tracked_entities) > MAX_TRACKED_ENTITIES:
            session.tracked_entities = session.tracked_entities[-MAX_TRACKED_ENTITIES:]
        
        session.last_updated = datetime.now().isoformat()
    
    def get_history(self, session_id: str) -> str:
        """
        Get conversation history as formatted string.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Formatted conversation history
        """
        if session_id not in self.sessions:
            return ""
        
        session = self.sessions[session_id]
        history_parts = []
        
        for msg in session.messages[-MAX_CONVERSATION_HISTORY * 2:]:  # Last N turns
            role_label = "User" if msg.role == "user" else "Assistant"
            history_parts.append(f"{role_label}: {msg.content}")
        
        return "\n".join(history_parts)
    
    def get_tracked_entities(self, session_id: str) -> List[str]:
        """Get tracked entities for session."""
        if session_id not in self.sessions:
            return []
        
        return self.sessions[session_id].tracked_entities[:MAX_TRACKED_ENTITIES]
    
    def clear_session(self, session_id: str):
        """Clear session data."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
