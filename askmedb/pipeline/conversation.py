"""Conversation history management with thread safety and session lifecycle."""

import threading
import time


class ConversationManager:
    """Manages conversation histories for multi-turn interactions.

    Thread-safe. Supports session TTL and max session limits to prevent
    memory leaks in long-running server deployments.

    Args:
        max_turns: Maximum number of conversation turns to keep per session.
        session_ttl_seconds: Seconds before an idle session expires. 0 = no expiry.
        max_sessions: Maximum concurrent sessions. 0 = unlimited.
            When exceeded, the oldest session is evicted.
    """

    def __init__(
        self,
        max_turns: int = 10,
        session_ttl_seconds: int = 0,
        max_sessions: int = 0,
    ):
        self.max_turns = max_turns
        self.session_ttl_seconds = session_ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, list[dict]] = {}
        self._last_access: dict[str, float] = {}
        self._lock = threading.Lock()

    def add_turn(self, role: str, content: str, conversation_id: str = "default"):
        """Add a message to a conversation's history."""
        with self._lock:
            self._evict_expired()

            if conversation_id not in self._sessions:
                self._enforce_max_sessions()
                self._sessions[conversation_id] = []

            history = self._sessions[conversation_id]
            history.append({"role": role, "content": content})

            max_messages = self.max_turns * 2
            if len(history) > max_messages:
                self._sessions[conversation_id] = history[-max_messages:]

            self._last_access[conversation_id] = time.monotonic()

    def get_history(self, conversation_id: str = "default") -> list[dict]:
        """Get the conversation history for a session."""
        with self._lock:
            self._evict_expired()
            if conversation_id in self._sessions:
                self._last_access[conversation_id] = time.monotonic()
            return list(self._sessions.get(conversation_id, []))

    def reset(self, conversation_id: str = "default"):
        """Clear a conversation's history."""
        with self._lock:
            self._sessions.pop(conversation_id, None)
            self._last_access.pop(conversation_id, None)

    def reset_all(self):
        """Clear all conversation histories."""
        with self._lock:
            self._sessions.clear()
            self._last_access.clear()

    @property
    def active_session_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            self._evict_expired()
            return len(self._sessions)

    def _evict_expired(self):
        """Remove sessions that have exceeded the TTL. Must be called with lock held."""
        if not self.session_ttl_seconds:
            return

        now = time.monotonic()
        expired = [
            sid for sid, ts in self._last_access.items()
            if (now - ts) > self.session_ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._last_access.pop(sid, None)

    def _enforce_max_sessions(self):
        """Evict the oldest session if at capacity. Must be called with lock held."""
        if not self.max_sessions or len(self._sessions) < self.max_sessions:
            return

        # Find the session with the oldest last_access time
        oldest_id = min(self._last_access, key=self._last_access.get)
        self._sessions.pop(oldest_id, None)
        self._last_access.pop(oldest_id, None)
