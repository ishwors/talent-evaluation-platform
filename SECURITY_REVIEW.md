# Security Vulnerability Review Report

## 1. Hardcoded JWT Secret Key
- **Vulnerability:** Insecure JWT Handling (Weak Secret/Hardcoded Secret)
- **Severity:** Critical
- **Description:** The JWT secret key has a hardcoded default value (`"dev-secret-change-in-production"`). If this default value is inadvertently used in a production environment (i.e. if the `JWT_SECRET_KEY` environment variable is not set), an attacker can easily forge JWT access tokens and completely bypass authentication, allowing them to perform actions as any user, including an administrator.
- **Affected Code (`backend/app/auth.py`):**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
```
- **Fixed Code Snippet:**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")
```

## 2. Broken Authentication Flow (Missing Database Validation)
- **Vulnerability:** Broken Authentication Flow (Missing token validation against the current database state)
- **Severity:** High
- **Description:** The `get_current_user` dependency only decodes and verifies the JWT signature and expiration. It completely trusts the claims within the payload (such as `user_id`, `role`, etc.) and does not verify whether the user still exists in the database or if their role/status has changed. This means that if a user's account is deleted or their privileges are revoked, they will still retain access until their JWT token expires.
- **Affected Code (`backend/app/auth.py`):**
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency that extracts and validates the current user from JWT."""
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email")
    name = payload.get("name")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return {"id": user_id, "role": role, "email": email, "name": name}
```
- **Fixed Code Snippet:**
```python
# Assuming you import get_db and aiosqlite as needed
from app.models import get_db
import aiosqlite

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: aiosqlite.Connection = Depends(get_db)
) -> dict:
    """FastAPI dependency that extracts and validates the current user from JWT against the database."""
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Validate against DB
    cursor = await db.execute(
        "SELECT id, email, role, name FROM users WHERE id = ?",
        (user_id,)
    )
    user = await cursor.fetchone()

    if not user:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return {"id": user["id"], "role": user["role"], "email": user["email"], "name": user["name"]}
```

## 3. Hardcoded Administrative Credentials in Seeding Code
- **Vulnerability:** Hardcoded Credentials
- **Severity:** High
- **Description:** The application's database seeding script hardcodes an administrator's email and password (`admin@ishwors.com` / `admin123`). If this seeding code is executed in a non-local or production environment, it creates a well-known, high-privileged account with a weak password, allowing attackers easy access to the system.
- **Affected Code (`backend/app/main.py`):**
```python
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
```
- **Fixed Code Snippet:**
```python
        # Create admin user
        admin_id = str(uuid.uuid4())
        admin_email = os.getenv("ADMIN_EMAIL", "admin@ishwors.com") # Note: Default is only for dev, prod must override
        admin_password = os.getenv("ADMIN_PASSWORD")
        if not admin_password:
             raise ValueError("ADMIN_PASSWORD environment variable is not set")

        await db.execute(
            "INSERT INTO users (id, email, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                admin_id,
                admin_email,
                hash_password(admin_password),
                "admin",
                "Admin User",
                now,
            ),
        )
```
