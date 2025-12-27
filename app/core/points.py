from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Points, Transaction, User
from app.core.config import Settings


class PointsService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings

    def ensure_user(self, name: str) -> User:
        """Ensure a User exists; if newly created, create points row and optionally grant starting points."""
        name = (name or "").strip()
        if not name:
            raise ValueError("name is required")

        user = self.db.scalar(select(User).where(User.name == name))
        is_new = False

        if user is None:
            user = User(name=name)
            self.db.add(user)
            self.db.flush()  # get user.id

            # create points row
            self.db.add(Points(user_id=user.id, balance=0))
            is_new = True
        else:
            user.last_seen = datetime.utcnow()

        # Grant starting points only once, for brand new users
        # Do this BEFORE committing so it happens in the same transaction
        if (
            is_new
            and self.settings is not None
            and getattr(self.settings, "POINTS_ENABLED", True)
        ):
            start_amount = int(getattr(self.settings, "POINTS_START_AMOUNT", 0) or 0)
            if start_amount > 0:
                # Get the points record we just created and update it directly
                pts = self.db.get(Points, user.id)
                if pts:
                    pts.balance = start_amount
                    # Add a transaction record for the starting points
                    self.db.add(Transaction(user_id=user.id, type="grant", delta=start_amount, reason="start"))

        # Commit once after all operations are complete
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

    def adjust(
        self,
        user_id: int,
        delta: int,
        reason: str,
        *,
        allow_negative_balance: bool = False,
    ) -> int:
        """Manual adjustment (admin).

        delta can be positive (add points) or negative (remove points).
        """
        if delta == 0:
            return self.get_balance(user_id)

        pts = self.db.get(Points, user_id)
        if pts is None:
            pts = Points(user_id=user_id, balance=0)
            self.db.add(pts)

        new_balance = pts.balance + int(delta)
        if not allow_negative_balance and new_balance < 0:
            raise ValueError("Adjustment would make balance negative")

        pts.balance = new_balance
        self.db.add(Transaction(user_id=user_id, type="adjust", delta=int(delta), reason=reason))
        self.db.commit()
        return pts.balance

    def list_transactions(
        self,
        user_id: int | None = None,
        limit: int = 50,
    ) -> list[Transaction]:
        stmt = select(Transaction).order_by(Transaction.id.desc()).limit(max(1, int(limit)))
        if user_id is not None:
            stmt = stmt.where(Transaction.user_id == int(user_id))
        return list(self.db.scalars(stmt))
