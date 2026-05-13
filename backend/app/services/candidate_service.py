"""
Candidate service layer.

All database queries use SQL-level filtering and pagination —
never loading the full table into memory and filtering in Python.
This is the correct approach as explained in the debugging section of the README.
"""

import json
import uuid
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional

import aiosqlite


async def get_candidates(
    db: aiosqlite.Connection,
    status: Optional[str] = None,
    role_applied: Optional[str] = None,
    skill: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List candidates with SQL-level filtering and offset-based pagination.
    
    All filtering happens at the database level using WHERE clauses,
    not in Python after fetching all rows. This is critical for performance
    at scale — see the debugging section in the README.
    """
    page_size = min(max(page_size, 1), 50)  # Clamp between 1 and 50
    page = max(page, 1)

    conditions = ["deleted_at IS NULL"]  # Always exclude soft-deleted candidates
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    
    if role_applied:
        conditions.append("role_applied = ?")
        params.append(role_applied)

    if skill:
        # skills is stored as a JSON array string — use LIKE for searching
        conditions.append("skills LIKE ?")
        params.append(f"%{skill}%")

    if keyword:
        # Search across name, email, and role_applied
        conditions.append("(name LIKE ? OR email LIKE ? OR role_applied LIKE ?)")
        keyword_param = f"%{keyword}%"
        params.extend([keyword_param, keyword_param, keyword_param])

    where_clause = " AND ".join(conditions)

    # Get total count for pagination metadata
    count_query = f"SELECT COUNT(*) FROM candidates WHERE {where_clause}"
    cursor = await db.execute(count_query, params)
    row = await cursor.fetchone()
    total = row[0]

    # Fetch the page with SQL-level LIMIT and OFFSET
    offset = (page - 1) * page_size
    data_query = f"""
        SELECT id, name, email, role_applied, status, skills, internal_notes, created_at
        FROM candidates
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    cursor = await db.execute(data_query, params + [page_size, offset])
    rows = await cursor.fetchall()

    candidates = []
    for row in rows:
        candidates.append({
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "role_applied": row["role_applied"],
            "status": row["status"],
            "skills": json.loads(row["skills"]),
            "internal_notes": row["internal_notes"],
            "created_at": row["created_at"],
        })

    total_pages = max((total + page_size - 1) // page_size, 1)

    return {
        "candidates": candidates,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_candidate_by_id(
    db: aiosqlite.Connection,
    candidate_id: str,
    current_user: dict,
) -> Optional[dict]:
    """
    Get a single candidate with their scores.
    - Reviewers only see their own scores.
    - Admins see all scores.
    """
    cursor = await db.execute(
        """SELECT id, name, email, role_applied, status, skills,
                  internal_notes, ai_summary, created_at
           FROM candidates
           WHERE id = ? AND deleted_at IS NULL""",
        (candidate_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    candidate = {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role_applied": row["role_applied"],
        "status": row["status"],
        "skills": json.loads(row["skills"]),
        "internal_notes": row["internal_notes"],
        "ai_summary": row["ai_summary"],
        "created_at": row["created_at"],
    }

    # Fetch scores — role-aware visibility
    if current_user["role"] == "admin":
        score_cursor = await db.execute(
            """SELECT s.id, s.candidate_id, s.category, s.score,
                      s.reviewer_id, u.name as reviewer_name, s.note, s.created_at
               FROM scores s
               JOIN users u ON s.reviewer_id = u.id
               WHERE s.candidate_id = ?
               ORDER BY s.created_at DESC""",
            (candidate_id,),
        )
    else:
        # Reviewers only see their own scores
        score_cursor = await db.execute(
            """SELECT s.id, s.candidate_id, s.category, s.score,
                      s.reviewer_id, u.name as reviewer_name, s.note, s.created_at
               FROM scores s
               JOIN users u ON s.reviewer_id = u.id
               WHERE s.candidate_id = ? AND s.reviewer_id = ?
               ORDER BY s.created_at DESC""",
            (candidate_id, current_user["id"]),
        )

    score_rows = await score_cursor.fetchall()
    candidate["scores"] = [
        {
            "id": s["id"],
            "candidate_id": s["candidate_id"],
            "category": s["category"],
            "score": s["score"],
            "reviewer_id": s["reviewer_id"],
            "reviewer_name": s["reviewer_name"],
            "note": s["note"],
            "created_at": s["created_at"],
        }
        for s in score_rows
    ]

    return candidate


async def add_score(
    db: aiosqlite.Connection,
    candidate_id: str,
    category: str,
    score: int,
    reviewer_id: str,
    note: str = "",
) -> dict:
    """Add a score for a candidate."""
    score_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO scores (id, candidate_id, category, score, reviewer_id, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (score_id, candidate_id, category, score, reviewer_id, note, now),
    )
    await db.commit()

    return {
        "id": score_id,
        "candidate_id": candidate_id,
        "category": category,
        "score": score,
        "reviewer_id": reviewer_id,
        "note": note,
        "created_at": now,
    }


async def generate_ai_summary(
    db: aiosqlite.Connection,
    candidate_id: str,
) -> dict:
    """
    Mock AI summary generation.
    
    Simulates an async LLM call with a 2-second delay, demonstrating
    how we'd handle external API calls in a production system.
    In production, this would call AWS Bedrock / OpenAI / similar.
    """
    # Fetch candidate data for the mock summary
    cursor = await db.execute(
        "SELECT name, role_applied, skills, status FROM candidates WHERE id = ? AND deleted_at IS NULL",
        (candidate_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    name = row["name"]
    role = row["role_applied"]
    skills = json.loads(row["skills"])

    # Simulate async LLM call with 2-second delay
    await asyncio.sleep(2)

    # Generate a realistic mock summary
    skill_str = ", ".join(skills) if skills else "no listed skills"
    strengths = random.sample(
        [
            "strong problem-solving ability",
            "excellent communication skills",
            "demonstrated leadership potential",
            "solid technical foundation",
            "good cultural fit indicators",
            "proactive learning mindset",
            "collaborative team player",
        ],
        k=min(3, 3),
    )

    summary = (
        f"**Candidate Summary for {name}**\n\n"
        f"{name} is applying for the {role} position. "
        f"Key skills include {skill_str}. "
        f"Based on the assessment data, this candidate demonstrates: "
        f"{', '.join(strengths)}. "
        f"\n\n**Recommendation:** Further review recommended to assess "
        f"alignment with team requirements and project needs."
    )

    now = datetime.now(timezone.utc).isoformat()

    # Store the summary
    await db.execute(
        "UPDATE candidates SET ai_summary = ? WHERE id = ?",
        (summary, candidate_id),
    )
    await db.commit()

    return {
        "candidate_id": candidate_id,
        "summary": summary,
        "generated_at": now,
    }


async def update_internal_notes(
    db: aiosqlite.Connection,
    candidate_id: str,
    notes: str,
) -> bool:
    """Update internal notes for a candidate (admin only)."""
    cursor = await db.execute(
        "UPDATE candidates SET internal_notes = ? WHERE id = ? AND deleted_at IS NULL",
        (notes, candidate_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def soft_delete_candidate(
    db: aiosqlite.Connection,
    candidate_id: str,
) -> bool:
    """
    Soft delete a candidate by setting deleted_at timestamp.
    Never hard-deletes — this is a key requirement.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        "UPDATE candidates SET deleted_at = ?, status = 'archived' WHERE id = ? AND deleted_at IS NULL",
        (now, candidate_id),
    )
    await db.commit()
    return cursor.rowcount > 0
