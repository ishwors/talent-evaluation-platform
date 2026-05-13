# Security Vulnerability Report

## 1. Outdated Packages with Known CVEs
Scanned backend dependencies using `pip-audit`. The following packages have known vulnerabilities and need to be upgraded:
- `pyjwt` (CVE-2026-32597)
- `pytest` (CVE-2025-71176)
- `starlette` (CVE-2025-54121, CVE-2025-62727)

Remediation:
- Update `pyjwt` to `>= 2.12.0`
- Update `fastapi` to `>= 0.115.8` (which resolves the `starlette` vulnerabilities)
- Remove `pytest` from production dependencies

## 2. Deprecated, Unmaintained, or Malicious Packages
- Backend: `passlib` is deprecated and unmaintained. It should eventually be replaced with a modern alternative like `bcrypt` directly, or `argon2-cffi`.

## 3. Development Dependencies Bundled into Production
- Backend: `pytest` and `pytest-asyncio` are included in `backend/requirements.txt` (the production requirements file).
- Frontend: `frontend/Dockerfile` spins up the Vite development server (`npm run dev`) and does not explicitly set `NODE_ENV`. This means dev dependencies and dev-specific build tools are included and running in production.

Remediation:
- Remove `pytest` and `pytest-asyncio` from `backend/requirements.txt`.
- Modify `frontend/Dockerfile` to use a multi-stage build, running `npm run build` and serving the static files via Nginx.

## 4. Environment Configuration
- The `.env.example` file is properly committed without exposing actual secrets. No hardcoded `.env` files with sensitive data were found committed to the repository.
- `NODE_ENV` is not set in production for the frontend, defaulting to dev behavior in the current Docker setup.

## 5. IAM Permissions / Database Roles
- The backend uses SQLite with a single shared file (`app.db`), so there is no database role separation (all queries execute with full permissions to the DB).
- There is no cloud IAM configuration checked in, so nothing overly broad was found in the infrastructure configs.

## 6. Dangerous Dynamic Code Execution
- Scanned the codebase for `eval()`, `Function()`, and `exec()`. No unsafe dynamic code execution patterns were detected.

## 7. OS Privileges
- Both the `backend/Dockerfile` and `frontend/Dockerfile` run as the default `root` user. Running containers as `root` is a security risk.

Remediation:
- Add a non-root user (e.g., `appuser`) to the Dockerfiles and switch to it using the `USER` directive.
