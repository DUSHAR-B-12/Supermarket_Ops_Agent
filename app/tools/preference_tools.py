from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.services.preference_service import PreferenceService

def get_preference(db: Session, user_id: str, key: str) -> Dict[str, Any]:
    service = PreferenceService(db)
    val = service.get_preference(user_id=user_id, key=key)
    return {"user_id": str(user_id), "key": key, "value": val}

def set_preference(db: Session, user_id: str, key: str, value: str) -> Dict[str, Any]:
    service = PreferenceService(db)
    pref = service.set_preference(user_id=user_id, key=key, value=value)
    return {"user_id": str(pref.user_id), "key": pref.key, "value": pref.value}
