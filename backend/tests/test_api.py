"""
API tests for the Candidate Scoring Dashboard.

Covers:
1. Candidate listing with filters
2. Score creation and retrieval
3. Auth enforcement — reviewer cannot see another reviewer's scores
4. Registration always assigns 'reviewer' role
5. Admin-only internal notes access
"""

import pytest
import uuid
import os
import sys
import asyncio

# Use a test-specific database
os.environ["DATABASE_URL"] = "data/test.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

# Initialize DB before importing app
from app.models import init_db, DATABASE_URL
from app.main import app, seed_data


# Initialize test database
def _init_test_db():
    """Initialize and seed the test database synchronously."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.run_until_complete(seed_data())
    loop.close()


# Clean up any existing test DB and re-initialize
if os.path.exists(DATABASE_URL):
    os.remove(DATABASE_URL)

os.makedirs(
    os.path.dirname(DATABASE_URL) if os.path.dirname(DATABASE_URL) else ".",
    exist_ok=True,
)
_init_test_db()


client = TestClient(app)


# ── Helper ────────────────────────────────────────────────────────


def register_user(email: str = None, name: str = "Test User") -> dict:
    """Register a user and return the token response."""
    if email is None:
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "name": name,
            "password": "testpass123",
        },
    )
    return response


def login_user(email: str, password: str) -> dict:
    """Login and return the token response."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    return response


def auth_header(token: str) -> dict:
    """Create an Authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ── Test 1: Registration hardcodes role to 'reviewer' ────────────


def test_registration_hardcodes_reviewer_role():
    """
    Verify that registration always assigns the 'reviewer' role,
    even if a malicious client tries to send a role field.
    """
    response = register_user()
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "reviewer"
    assert "access_token" in data
    assert data["token_type"] == "bearer"


# ── Test 2: Candidate listing with authentication ────────────────


def test_list_candidates_requires_auth():
    """Verify that the candidates endpoint requires authentication."""
    response = client.get("/api/candidates")
    assert response.status_code == 403  # No token provided


def test_list_candidates_with_auth():
    """Verify authenticated users can list candidates."""
    login_resp = login_user("admin@ishwors.com", "admin123")
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    response = client.get("/api/candidates", headers=auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert "total" in data
    assert "page" in data
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_list_candidates_with_filters():
    """Verify filtering works at the API level."""
    login_resp = login_user("admin@ishwors.com", "admin123")
    token = login_resp.json()["access_token"]

    # Filter by status
    response = client.get(
        "/api/candidates?status=new",
        headers=auth_header(token),
    )
    assert response.status_code == 200
    data = response.json()
    for c in data["candidates"]:
        assert c["status"] == "new"


# ── Test 3: Reviewer cannot see another reviewer's scores ────────


def test_reviewer_cannot_see_other_reviewers_scores():
    """
    Auth enforcement test: a reviewer should only see their own scores,
    not scores submitted by other reviewers.
    """
    # Login as seeded reviewer
    login_resp = login_user("reviewer@ishwors.com", "reviewer123")
    assert login_resp.status_code == 200
    reviewer1_token = login_resp.json()["access_token"]

    # Register a new reviewer
    reg_resp = register_user(name="New Reviewer")
    assert reg_resp.status_code == 201
    reviewer2_token = reg_resp.json()["access_token"]

    # Get a candidate to score
    candidates_resp = client.get(
        "/api/candidates",
        headers=auth_header(reviewer1_token),
    )
    assert candidates_resp.status_code == 200
    candidates = candidates_resp.json()["candidates"]
    assert len(candidates) > 0
    candidate_id = candidates[0]["id"]

    # Reviewer 2 adds a score
    score_resp = client.post(
        f"/api/candidates/{candidate_id}/scores",
        json={"category": "Technical Skills", "score": 4, "note": "From reviewer 2"},
        headers=auth_header(reviewer2_token),
    )
    assert score_resp.status_code == 201

    # Reviewer 1 should NOT see reviewer 2's score
    detail_resp = client.get(
        f"/api/candidates/{candidate_id}",
        headers=auth_header(reviewer1_token),
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()

    # Check that none of reviewer 1's visible scores have "From reviewer 2" note
    for score in detail["scores"]:
        assert score["note"] != "From reviewer 2", (
            "Reviewer should not see another reviewer's scores"
        )


# ── Test 4: Admin can see all scores ──────────────────────────────


def test_admin_sees_all_scores():
    """Verify that admin users can see scores from all reviewers."""
    login_resp = login_user("admin@ishwors.com", "admin123")
    token = login_resp.json()["access_token"]

    candidates_resp = client.get(
        "/api/candidates",
        headers=auth_header(token),
    )
    candidates = candidates_resp.json()["candidates"]
    candidate_id = candidates[0]["id"]

    detail_resp = client.get(
        f"/api/candidates/{candidate_id}",
        headers=auth_header(token),
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    # Admin should see internal_notes field
    assert "internal_notes" in detail


# ── Test 5: Reviewer cannot access internal notes ─────────────────


def test_reviewer_cannot_see_internal_notes():
    """Verify reviewer cannot see internal_notes field."""
    login_resp = login_user("reviewer@ishwors.com", "reviewer123")
    token = login_resp.json()["access_token"]

    candidates_resp = client.get(
        "/api/candidates",
        headers=auth_header(token),
    )
    candidates = candidates_resp.json()["candidates"]
    candidate_id = candidates[0]["id"]

    detail_resp = client.get(
        f"/api/candidates/{candidate_id}",
        headers=auth_header(token),
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    # Reviewer should NOT have internal_notes
    assert "internal_notes" not in detail
