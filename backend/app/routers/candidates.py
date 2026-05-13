"""
Candidates router — CRUD operations, scoring, AI summary, and SSE streaming.

Implements role-based access control:
- Reviewers: can score, see only own scores, cannot view internal_notes
- Admins: see all scores, can view/edit internal_notes
"""

import json
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import aiosqlite

from app.auth import get_current_user, require_admin
from app.models import get_db
from app.schemas import (
    CandidateListResponse,
    CandidateOut,
    CandidateDetailOut,
    ScoreCreate,
    ScoreOut,
    InternalNotesUpdate,
    AISummaryResponse,
)
from app.services.candidate_service import (
    get_candidates,
    get_candidate_by_id,
    add_score,
    generate_ai_summary,
    update_internal_notes,
    soft_delete_candidate,
)

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=CandidateListResponse)
async def list_candidates(
    status: Optional[str] = Query(None, description="Filter by status: new, reviewed, hired, rejected"),
    role_applied: Optional[str] = Query(None, description="Filter by role applied for"),
    skill: Optional[str] = Query(None, description="Filter by skill"),
    keyword: Optional[str] = Query(None, description="Search keyword across name, email, role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page (max 50)"),
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    List candidates with filters and pagination.
    
    Filtering happens at the SQL level — not in Python.
    Pagination is offset-based with configurable page size (default 20, max 50).
    """
    result = await get_candidates(
        db,
        status=status,
        role_applied=role_applied,
        skill=skill,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    # Strip internal_notes for non-admin users
    candidates = []
    for c in result["candidates"]:
        candidate_data = {
            "id": c["id"],
            "name": c["name"],
            "email": c["email"],
            "role_applied": c["role_applied"],
            "status": c["status"],
            "skills": c["skills"],
            "created_at": c["created_at"],
        }
        if current_user["role"] == "admin":
            candidate_data["internal_notes"] = c.get("internal_notes", "")
        candidates.append(candidate_data)

    return CandidateListResponse(
        candidates=candidates,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Get candidate detail with scores and AI summary.
    
    - Reviewers see only their own scores, cannot see internal_notes.
    - Admins see all scores and internal_notes.
    """
    candidate = await get_candidate_by_id(db, candidate_id, current_user)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Strip internal_notes for non-admin users
    if current_user["role"] != "admin":
        candidate.pop("internal_notes", None)

    return candidate


@router.post("/{candidate_id}/scores", response_model=ScoreOut, status_code=status.HTTP_201_CREATED)
async def create_score(
    candidate_id: str,
    score_data: ScoreCreate,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Submit a score for a candidate in a specific category."""
    # Verify candidate exists
    cursor = await db.execute(
        "SELECT id FROM candidates WHERE id = ? AND deleted_at IS NULL",
        (candidate_id,),
    )
    if not await cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    result = await add_score(
        db,
        candidate_id=candidate_id,
        category=score_data.category,
        score=score_data.score,
        reviewer_id=current_user["id"],
        note=score_data.note or "",
    )

    return ScoreOut(
        id=result["id"],
        candidate_id=result["candidate_id"],
        category=result["category"],
        score=result["score"],
        reviewer_id=result["reviewer_id"],
        reviewer_name=current_user.get("name", ""),
        note=result["note"],
        created_at=result["created_at"],
    )


@router.post("/{candidate_id}/summary", response_model=AISummaryResponse)
async def trigger_ai_summary(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Trigger mock AI summary generation for a candidate.
    
    Simulates an async LLM call with a 2-second delay.
    In production, this would call an external AI service
    (e.g., AWS Bedrock, OpenAI) asynchronously.
    """
    result = await generate_ai_summary(db, candidate_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return AISummaryResponse(**result)


@router.put("/{candidate_id}/notes")
async def update_notes(
    candidate_id: str,
    notes_data: InternalNotesUpdate,
    current_user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Update internal notes for a candidate. Admin only."""
    success = await update_internal_notes(db, candidate_id, notes_data.internal_notes)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return {"message": "Internal notes updated", "candidate_id": candidate_id}


@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    current_user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Soft delete a candidate (admin only).
    
    Sets deleted_at timestamp and status to 'archived'.
    Never performs a hard delete — this is intentional.
    """
    success = await soft_delete_candidate(db, candidate_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found or already deleted",
        )
    return {"message": "Candidate archived", "candidate_id": candidate_id}


@router.get("/{candidate_id}/stream")
async def stream_scores(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    SSE endpoint that streams score updates in real time (stretch goal).
    
    Uses Server-Sent Events to push new scores as they are added.
    In a production system, this would be backed by a pub/sub mechanism
    (e.g., Redis Pub/Sub, DynamoDB Streams + EventBridge).
    
    For this demo, it polls the database every 2 seconds for new scores.
    """
    # Verify candidate exists
    cursor = await db.execute(
        "SELECT id FROM candidates WHERE id = ? AND deleted_at IS NULL",
        (candidate_id,),
    )
    if not await cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    async def event_generator():
        last_count = 0
        try:
            while True:
                async with aiosqlite.connect("data/app.db") as poll_db:
                    poll_db.row_factory = aiosqlite.Row
                    
                    if current_user["role"] == "admin":
                        cursor = await poll_db.execute(
                            """SELECT s.id, s.category, s.score, s.reviewer_id,
                                      u.name as reviewer_name, s.note, s.created_at
                               FROM scores s
                               JOIN users u ON s.reviewer_id = u.id
                               WHERE s.candidate_id = ?
                               ORDER BY s.created_at DESC""",
                            (candidate_id,),
                        )
                    else:
                        cursor = await poll_db.execute(
                            """SELECT s.id, s.category, s.score, s.reviewer_id,
                                      u.name as reviewer_name, s.note, s.created_at
                               FROM scores s
                               JOIN users u ON s.reviewer_id = u.id
                               WHERE s.candidate_id = ? AND s.reviewer_id = ?
                               ORDER BY s.created_at DESC""",
                            (candidate_id, current_user["id"]),
                        )

                    rows = await cursor.fetchall()
                    current_count = len(rows)

                    if current_count != last_count:
                        scores = [
                            {
                                "id": r["id"],
                                "category": r["category"],
                                "score": r["score"],
                                "reviewer_id": r["reviewer_id"],
                                "reviewer_name": r["reviewer_name"],
                                "note": r["note"],
                                "created_at": r["created_at"],
                            }
                            for r in rows
                        ]
                        data = json.dumps({"scores": scores, "total": current_count})
                        yield f"data: {data}\n\n"
                        last_count = current_count

                await asyncio.sleep(2)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
