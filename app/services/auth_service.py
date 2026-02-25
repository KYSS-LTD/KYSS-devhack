import hashlib

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register(self, db: Session, username: str, password: str) -> User:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        user = User(username=username, password_hash=self.hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, username: str, password: str) -> User:
        user = db.query(User).filter(User.username == username).first()
        if not user or user.password_hash != self.hash_password(password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user


auth_service = AuthService()
