from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, update, insert
from sqlalchemy.orm import Session
from app.core.models import User, Points, Transaction


class PointsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_user(self, name: str) -> User:
        user = self.db.scalar(select(User).where(User.name == name))
        if user is None:
            user = User(name=name)
            self.db.add(user)
            self.db.flush()
            # create points row
            self.db.add(Points(user_id=user.id, balance=0))
        else:
            user.last_seen = datetime.utcnow()
        self.db.commit()
        return user

    def get_balance(self, user_id: int) -> int:
        pts = self.db.get(Points, user_id)
        return pts.balance if pts else 0

    def grant(self, user_id: int, amount: int, reason: str) -> int:
        if amount == 0:
            return self.get_balance(user_id)
        pts = self.db.get(Points, user_id)
        if pts is None:
            pts = Points(user_id=user_id, balance=0)
            self.db.add(pts)
        pts.balance += amount
        self.db.add(Transaction(user_id=user_id, type="grant", delta=amount, reason=reason))
        self.db.commit()
        return pts.balance

    def spend(self, user_id: int, amount: int, reason: str) -> int:
        if amount <= 0:
            return self.get_balance(user_id)
        pts = self.db.get(Points, user_id)
        if pts is None or pts.balance < amount:
            raise ValueError("Insufficient points")
        pts.balance -= amount
        self.db.add(Transaction(user_id=user_id, type="spend", delta=-amount, reason=reason))
        self.db.commit()
        return pts.balance