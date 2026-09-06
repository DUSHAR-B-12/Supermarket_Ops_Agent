import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import UserSession

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(self, user_id: str) -> UserSession:
        user_str = str(user_id)
        session = self.db.query(UserSession).filter(UserSession.user_id == user_str).first()
        if not session:
            session = UserSession(
                user_id=user_str,
                active_draft_bill_id=None,
                conversation_history=json.dumps([]),
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        else:
            try:
                self.db.refresh(session)
            except Exception:
                pass
        return session

    def set_active_draft_bill(self, user_id: str, bill_id: Optional[int]) -> None:
        session = self.get_or_create_session(user_id)
        session.active_draft_bill_id = bill_id
        self.db.commit()

    def get_active_draft_bill(self, user_id: str) -> Optional[int]:
        session = self.get_or_create_session(user_id)
        return session.active_draft_bill_id

    def add_message(self, user_id: str, role: str, content: str) -> None:
        session = self.get_or_create_session(user_id)
        history: List[Dict[str, str]] = json.loads(session.conversation_history or "[]")
        history.append({"role": role, "content": content})
        # Keep last 10 messages for context
        if len(history) > 10:
            history = history[-10:]
        session.conversation_history = json.dumps(history)
        self.db.commit()

    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        session = self.get_or_create_session(user_id)
        return json.loads(session.conversation_history or "[]")

    def reset_session(self, user_id: str) -> None:
        """
        Implements Telegram /new command:
        Clears conversation history and active draft bill state for user_id.
        Does NOT delete historical bills, inventory, Khata accounts, or preferences.
        """
        session = self.get_or_create_session(user_id)
        session.active_draft_bill_id = None
        session.conversation_history = json.dumps([])
        self.db.commit()
        logger.info(f"Conversational session reset for user_id={user_id}")
