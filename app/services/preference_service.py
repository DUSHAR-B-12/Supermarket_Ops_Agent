from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import Preference

class PreferenceService:
    def __init__(self, db: Session):
        self.db = db

    def set_preference(self, user_id: str, key: str, value: str) -> Preference:
        user_str = str(user_id)
        key_str = key.strip().lower()
        pref = (
            self.db.query(Preference)
            .filter(Preference.user_id == user_str, Preference.key == key_str)
            .first()
        )
        if pref:
            pref.value = value.strip()
        else:
            pref = Preference(user_id=user_str, key=key_str, value=value.strip())
            self.db.add(pref)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def get_preference(self, user_id: str, key: str) -> Optional[str]:
        user_str = str(user_id)
        key_str = key.strip().lower()
        pref = (
            self.db.query(Preference)
            .filter(Preference.user_id == user_str, Preference.key == key_str)
            .first()
        )
        return pref.value if pref else None
