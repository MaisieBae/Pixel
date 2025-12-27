"""Batch operations for points and XP.

Provides utilities for mass-granting or adjusting points/XP across multiple users.
"""
from __future__ import annotations

from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import User
from app.core.points import PointsService
from app.core.xp import XpService
from app.core.config import Settings


def batch_adjust_points(
    db: Session,
    delta: int,
    user_ids: list[int] | None = None,
    reason: str = "batch_admin",
    allow_negative: bool = False,
) -> dict:
    """Adjust points for multiple users.
    
    Args:
        db: Database session
        delta: Amount to add (positive) or subtract (negative)
        user_ids: List of specific user IDs, or None for all users
        reason: Reason for transaction log
        allow_negative: Allow negative balances
    
    Returns:
        Dict with success/failure counts and any errors
    """
    ps = PointsService(db)
    
    # Get target users
    if user_ids:
        users = [db.get(User, uid) for uid in user_ids]
        users = [u for u in users if u is not None]
    else:
        users = list(db.scalars(select(User)))
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
        "total_users": len(users),
    }
    
    for user in users:
        try:
            ps.adjust(
                user.id,
                delta=delta,
                reason=reason,
                allow_negative_balance=allow_negative,
            )
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "user_id": user.id,
                "user_name": user.name,
                "error": str(e),
            })
    
    return results


def batch_adjust_xp(
    db: Session,
    settings: Settings,
    delta: int,
    user_ids: list[int] | None = None,
    reason: str = "batch_admin",
) -> dict:
    """Adjust XP for multiple users.
    
    Args:
        db: Database session
        settings: Application settings
        delta: Amount of XP to add (positive) or subtract (negative)
        user_ids: List of specific user IDs, or None for all users
        reason: Reason for transaction log
    
    Returns:
        Dict with success/failure counts and any errors
    """
    xs = XpService(db, settings)
    
    # Get target users
    if user_ids:
        users = [db.get(User, uid) for uid in user_ids]
        users = [u for u in users if u is not None]
    else:
        users = list(db.scalars(select(User)))
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
        "total_users": len(users),
        "level_ups": [],
    }
    
    for user in users:
        try:
            result = xs.adjust(user.name, delta=delta, reason=reason, source="batch_admin")
            results["success"] += 1
            
            # Track level changes
            if result.level_after != result.level_before:
                results["level_ups"].append({
                    "user_name": user.name,
                    "level_before": result.level_before,
                    "level_after": result.level_after,
                })
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "user_id": user.id,
                "user_name": user.name,
                "error": str(e),
            })
    
    return results
