"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ── Auth Schemas ──────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    # NOTE: role is intentionally NOT accepted from the client.
    # It is always hardcoded to "reviewer" in the registration endpoint.


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    name: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


# ── Candidate Schemas ─────────────────────────────────────────────

class CandidateOut(BaseModel):
    id: str
    name: str
    email: str
    role_applied: str
    status: str
    skills: list[str]
    created_at: str
    internal_notes: Optional[str] = None  # Only returned for admins


class CandidateDetailOut(CandidateOut):
    scores: list[dict]
    ai_summary: Optional[str] = None


class CandidateListResponse(BaseModel):
    candidates: list[CandidateOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Score Schemas ─────────────────────────────────────────────────

class ScoreCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    score: int = Field(..., ge=1, le=5)
    note: Optional[str] = Field(default="", max_length=500)


class ScoreOut(BaseModel):
    id: str
    candidate_id: str
    category: str
    score: int
    reviewer_id: str
    reviewer_name: Optional[str] = None
    note: str
    created_at: str


# ── Internal Notes Schema ────────────────────────────────────────

class InternalNotesUpdate(BaseModel):
    internal_notes: str = Field(..., max_length=2000)


# ── AI Summary Schema ────────────────────────────────────────────

class AISummaryResponse(BaseModel):
    candidate_id: str
    summary: str
    generated_at: str
