"""
Database models and SQLite setup for the Candidate Scoring Dashboard.

Uses aiosqlite for async database operations with SQLite.
Includes proper indexes on candidates.status, candidates.role_applied,
and scores.candidate_id for efficient querying.
"""

import aiosqlite
import os
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "data/app.db")


async def get_db():
    """Dependency that provides an async database connection."""
    os.makedirs(os.path.dirname(DATABASE_URL) if os.path.dirname(DATABASE_URL) else ".", exist_ok=True)
    db = await aiosqlite.connect(DATABASE_URL)
    db.row_factory = aiosqlite.Row
    # Enable WAL mode for better concurrent read performance
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Initialize database schema with proper indexes."""
    os.makedirs(os.path.dirname(DATABASE_URL) if os.path.dirname(DATABASE_URL) else ".", exist_ok=True)
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Users table for authentication
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'reviewer' CHECK(role IN ('reviewer', 'admin')),
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Candidates table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                role_applied TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK(status IN ('new', 'reviewed', 'hired', 'rejected', 'archived')),
                skills TEXT NOT NULL DEFAULT '[]',
                internal_notes TEXT DEFAULT '',
                ai_summary TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                deleted_at TEXT DEFAULT NULL
            )
        """)

        # Scores table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                category TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 1 AND score <= 5),
                reviewer_id TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id)
            )
        """)

        # Indexes for efficient querying
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_role_applied ON candidates(role_applied)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_scores_candidate_id ON scores(candidate_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_scores_reviewer_id ON scores(reviewer_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_deleted_at ON candidates(deleted_at)"
        )

        await db.commit()
