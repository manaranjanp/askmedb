"""Conversation history management."""


class ConversationManager:
    """Manages conversation histories for multi-turn interactions.

    Supports multiple named conversations via conversation_id.

    Args:
        max_turns: Maximum number of conversation turns to keep per session.
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._sessions: dict[str, list[dict]] = {}

    def add_turn(self, role: str, content: str, conversation_id: str = "default"):
        """Add a message to a conversation's history."""
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = []

        history = self._sessions[conversation_id]
        history.append({"role": role, "content": content})

        max_messages = self.max_turns * 2
        if len(history) > max_messages:
            self._sessions[conversation_id] = history[-max_messages:]

    def get_history(self, conversation_id: str = "default") -> list[dict]:
        """Get the conversation history for a session."""
        return list(self._sessions.get(conversation_id, []))

    def reset(self, conversation_id: str = "default"):
        """Clear a conversation's history."""
        self._sessions.pop(conversation_id, None)

    def reset_all(self):
        """Clear all conversation histories."""
        self._sessions.clear()
