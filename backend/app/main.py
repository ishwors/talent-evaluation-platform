"""
FastAPI application entry point.

Initializes the database, seeds sample data, and mounts API routers.
Includes CORS middleware for frontend communication.
"""

import json
import uuid
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import init_db, get_db, DATABASE_URL
from app.auth import hash_password
from app.routers import auth, candidates

import aiosqlite


async def seed_data():
    """Seed the database with sample data for demonstration."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row

        # Check if data already exists
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cursor.fetchone())[0]
        if count > 0:
            return  # Already seeded

        now = datetime.now(timezone.utc).isoformat()

        # Create admin user
        admin_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, email, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                admin_id,
                "admin@ishwors.com",
                hash_password("admin123"),
                "admin",
                "Admin User",
                now,
            ),
        )

        # Create reviewer user
        reviewer_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, email, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                reviewer_id,
                "reviewer@ishwors.com",
                hash_password("reviewer123"),
                "reviewer",
                "Jane Reviewer",
                now,
            ),
        )

        # Create second reviewer
        reviewer2_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO users (id, email, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                reviewer2_id,
                "reviewer2@ishwors.com",
                hash_password("reviewer123"),
                "reviewer",
                "Bob Reviewer",
                now,
            ),
        )

        # Create sample candidates
        sample_candidates = [
            {
                "id": str(uuid.uuid4()),
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "role_applied": "Full-Stack Engineer",
                "status": "new",
                "skills": json.dumps(["Python", "React", "FastAPI", "Docker"]),
                "internal_notes": "Referred by CTO. Strong background in AI systems.",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Bob Smith",
                "email": "bob@example.com",
                "role_applied": "Backend Developer",
                "status": "reviewed",
                "skills": json.dumps(["Python", "Django", "PostgreSQL", "AWS"]),
                "internal_notes": "Second round pending. Good cultural fit.",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Charlie Chen",
                "email": "charlie@example.com",
                "role_applied": "Full-Stack Engineer",
                "status": "new",
                "skills": json.dumps(["TypeScript", "React", "Node.js", "MongoDB"]),
                "internal_notes": "",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Diana Patel",
                "email": "diana@example.com",
                "role_applied": "DevOps Engineer",
                "status": "hired",
                "skills": json.dumps(
                    ["Terraform", "Docker", "Kubernetes", "AWS", "CI/CD"]
                ),
                "internal_notes": "Exceptional candidate. Offer accepted.",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Ethan Williams",
                "email": "ethan@example.com",
                "role_applied": "Frontend Developer",
                "status": "rejected",
                "skills": json.dumps(["React", "Vue.js", "CSS", "Figma"]),
                "internal_notes": "Insufficient experience for senior role.",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Fiona Garcia",
                "email": "fiona@example.com",
                "role_applied": "Backend Developer",
                "status": "new",
                "skills": json.dumps(["Python", "FastAPI", "DynamoDB", "Lambda"]),
                "internal_notes": "",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "George Kim",
                "email": "george@example.com",
                "role_applied": "Full-Stack Engineer",
                "status": "reviewed",
                "skills": json.dumps(["Python", "React", "AWS", "Docker", "LangChain"]),
                "internal_notes": "Strong AI/ML background. Schedule final interview.",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Hannah Lee",
                "email": "hannah@example.com",
                "role_applied": "Data Engineer",
                "status": "new",
                "skills": json.dumps(["Python", "Spark", "Airflow", "SQL", "dbt"]),
                "internal_notes": "",
            },
        ]

        for c in sample_candidates:
            await db.execute(
                """INSERT INTO candidates (id, name, email, role_applied, status, skills, internal_notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    c["id"],
                    c["name"],
                    c["email"],
                    c["role_applied"],
                    c["status"],
                    c["skills"],
                    c["internal_notes"],
                    now,
                ),
            )

        # Add some sample scores from the reviewers
        categories = [
            "Technical Skills",
            "Communication",
            "Problem Solving",
            "Cultural Fit",
            "Leadership",
        ]
        import random

        for i, candidate in enumerate(sample_candidates[:4]):
            for j, cat in enumerate(categories[:3]):
                await db.execute(
                    "INSERT INTO scores (id, candidate_id, category, score, reviewer_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        candidate["id"],
                        cat,
                        random.randint(2, 5),
                        reviewer_id,
                        f"Good {cat.lower()} demonstrated.",
                        now,
                    ),
                )

        await db.commit()
        print("[OK] Database seeded with sample data")
        print("   Admin: admin@ishwors.com / admin123")
        print("   Reviewer: reviewer@ishwors.com / reviewer123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize DB and seed data on startup."""
    await init_db()
    await seed_data()
    yield


app = FastAPI(
    title="Candidate Scoring Dashboard",
    description="Internal candidate scoring and review dashboard for TalentScan's recruitment workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "candidate-scoring-api"}
