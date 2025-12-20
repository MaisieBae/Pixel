from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Item, Inventory


class ItemsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_item(self, key: str, name: str, description: str = "", enabled: bool = True) -> Item:
        k = (key or "").strip().lower()
        if not k:
            raise ValueError("Item key required")
        it = self.db.scalar(select(Item).where(Item.key == k))
        if it is None:
            it = Item(key=k, name=name.strip() or k, description=description.strip(), enabled=bool(enabled))
            self.db.add(it)
        else:
            it.name = name.strip() or it.name
            it.description = description.strip()
            it.enabled = bool(enabled)
        self.db.commit()
        return it

    def list_items(self, enabled_only: bool = False) -> list[Item]:
        stmt = select(Item).order_by(Item.key.asc())
        if enabled_only:
            stmt = stmt.where(Item.enabled == True)  # noqa: E712
        return list(self.db.scalars(stmt))

    def grant_item(self, user_id: int, item_key: str, qty: int = 1) -> Inventory:
        k = (item_key or "").strip().lower()
        if not k:
            raise ValueError("Item key required")
        qty = int(qty)
        if qty == 0:
            raise ValueError("qty must be non-zero")

        # Ensure item exists (optional: allow "implicit" items)
        it = self.db.scalar(select(Item).where(Item.key == k))
        if it is None:
            it = Item(key=k, name=k, description="", enabled=True)
            self.db.add(it)
            self.db.flush()

        inv = self.db.scalar(select(Inventory).where(Inventory.user_id == user_id, Inventory.item_key == k))
        if inv is None:
            inv = Inventory(user_id=user_id, item_key=k, qty=max(0, qty))
            self.db.add(inv)
        else:
            inv.qty = max(0, int(inv.qty) + qty)
        self.db.commit()
        return inv

    def get_inventory(self, user_id: int) -> list[Inventory]:
        return list(
            self.db.scalars(
                select(Inventory).where(Inventory.user_id == user_id).order_by(Inventory.item_key.asc())
            )
        )
