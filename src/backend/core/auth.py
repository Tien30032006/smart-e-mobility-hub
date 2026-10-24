"""Mock authentication shared by all modules. SHARED FILE.

MVP rule: log in with an e-mail from the seed data, the "token" is the user_id.
Send it as ``Authorization: Bearer <user_id>``. No passwords (not required by
the assignment). Use the dependencies below in your routes:

    @router.post("/x")
    def x(user: Student = Depends(require_student)): ...
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException

from .entities import Operator, Student, User
from .state_manager import network


def login(email: str) -> Optional[User]:
    email = email.strip().lower()
    return next((u for u in network.users.values() if u.email.lower() == email), None)


def current_user(authorization: Optional[str] = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing 'Authorization: Bearer <user_id>'")
    user = network.users.get(authorization.split(" ", 1)[1].strip())
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def require_student(user: User = Depends(current_user)) -> Student:
    if not isinstance(user, Student):
        raise HTTPException(status_code=403, detail="Student only")
    return user


def require_operator(user: User = Depends(current_user)) -> Operator:
    if not isinstance(user, Operator):
        raise HTTPException(status_code=403, detail="Operator only")
    return user
