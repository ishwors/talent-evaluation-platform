"""
Authentication router — handles user registration and login.

IMPORTANT: Registration always hardcodes role to 'reviewer'.
The role is NEVER accepted from the client payload.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from app.schemas import UserRegister, UserLogin, TokenResponse, UserOut
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.models import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: aiosqlite.Connection = Depends(get_db)):
    """
    Register a new user.
    
    Role is ALWAYS set to 'reviewer' — never accepted from the client.
    This prevents privilege escalation attacks.
    """
    # Check if email already exists
    cursor = await db.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
    if await cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_id = str(uuid.uuid4())
    password_hash = hash_password(user_data.password)
    now = datetime.now(timezone.utc).isoformat()

    # Role is hardcoded to 'reviewer' — this is intentional and critical
    role = "reviewer"

    await db.execute(
        "INSERT INTO users (id, email, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, user_data.email, password_hash, role, user_data.name, now),
    )
    await db.commit()

    token = create_access_token({
        "sub": user_id,
        "email": user_data.email,
        "role": role,
        "name": user_data.name,
    })

    return TokenResponse(
        access_token=token,
        role=role,
        user_id=user_id,
        name=user_data.name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: aiosqlite.Connection = Depends(get_db)):
    """Authenticate a user and return a JWT token."""
    cursor = await db.execute(
        "SELECT id, email, password_hash, role, name FROM users WHERE email = ?",
        (credentials.email,),
    )
    user = await cursor.fetchone()

    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
    })

    return TokenResponse(
        access_token=token,
        role=user["role"],
        user_id=user["id"],
        name=user["name"],
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the current authenticated user's info."""
    return UserOut(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
    )
