# Security Audit Report

This document addresses the security audit checklist for the API layer and data handling.

## 1. Sensitive Fields in API Responses
- **Exposure:** No highly sensitive fields (passwords, SSNs) are currently being leaked. Tokens are only returned securely upon authentication. However, the `GET /api/candidates/{candidate_id}` endpoint does not specify a `response_model=CandidateDetailOut` in its route decorator. Because of this, FastAPI skips schema filtering and returns the raw dictionary. While the service function currently builds a safe dictionary, any future addition of sensitive fields to that dictionary would be exposed to the client.
- **Risk:** Low (Fragile architecture that could lead to future leakage).
- **Affected Code:** `GET /api/candidates/{candidate_id}` in `backend/app/routers/candidates.py`.
- **Remediation:** Explicitly add `response_model=CandidateDetailOut` to the route decorator to ensure FastAPI strictly filters the output.

## 2. Rate Limiting and Brute-Force Protection
- **Exposure:** Rate limiting and brute-force protection are entirely missing across the application.
- **Risk:** High. The `/auth/login` endpoint is vulnerable to brute-force and credential stuffing attacks. Other endpoints are vulnerable to DoS attacks.
- **Affected Code:** All endpoints, notably `/api/auth/login` and `/api/auth/register`.
- **Remediation:** Implement a rate-limiting mechanism (e.g., using `slowapi` or `fastapi-limiter`). Add strict limits for authentication endpoints (e.g., 5 requests per minute) and account lockout after repeated failed attempts.

## 3. Permissive CORS Headers
- **Exposure:** The CORS configuration uses `allow_methods=["*"]` and `allow_headers=["*"]`. Furthermore, `allow_origins` is read from the `CORS_ORIGINS` environment variable. If `CORS_ORIGINS` is ever set to `*` while `allow_credentials=True` is enabled, it violates CORS security best practices and can be rejected by modern browsers, or lead to broad origin acceptance.
- **Risk:** Medium. Overly permissive methods and headers increase the attack surface for Cross-Site Request Forgery (CSRF).
- **Affected Code:** `CORSMiddleware` setup in `backend/app/main.py`.
- **Remediation:** Restrict `allow_methods` to specifically required HTTP methods (e.g., `["GET", "POST", "PUT", "DELETE"]`) and `allow_headers` to only necessary headers (e.g., `["Authorization", "Content-Type"]`).

## 4. Internal Error Stack Traces
- **Exposure:** Stack traces are **not** being leaked to the client. The FastAPI application is not running with `debug=True`, meaning unhandled exceptions result in a generic `500 Internal Server Error` response without exposing internal code paths or database queries.
- **Risk:** None (Currently Secure).
- **Affected Code:** N/A.
- **Remediation:** Ensure `debug` remains `False` in production environments and continue avoiding passing raw exception strings into `HTTPException` details.

## 5. Pagination and Mass Data Extraction
- **Exposure:** Pagination is correctly implemented on the main `/api/candidates` list endpoint (using `LIMIT` and `OFFSET` capped at a `page_size` of 50). Thus, mass data extraction via a single request is prevented. However, due to the lack of rate limiting (noted in #2), an attacker can easily write a script to iterate through pages and scrape the entire database. Additionally, endpoints like `/candidates/{id}/scores` do not paginate the scores.
- **Risk:** Medium. Mass extraction is possible via page iteration.
- **Affected Code:** `/api/candidates` and `/api/candidates/{id}/stream`.
- **Remediation:** Enforce rate limiting on the list endpoints to deter scraping. Implement pagination on nested lists (like scores) if they are expected to grow significantly.

## 6. Unauthenticated Endpoints Requiring Auth
- **Exposure:** The `/api/auth/register` endpoint is completely unauthenticated and hardcodes the assigned role to `'reviewer'`. Because any public user can register, anyone can instantly gain authenticated access to the internal dashboard and view candidate PII (names, emails, skills).
- **Risk:** Critical. This effectively bypasses the entire access control model for the internal system.
- **Affected Code:** `POST /api/auth/register` in `backend/app/routers/auth.py`.
- **Remediation:** Restrict the registration endpoint. It should either require an Admin token to create new accounts, or it should be disabled entirely in favor of an invite-only flow or an enterprise SSO integration.

## 7. HTTP Security Headers
- **Exposure:** Essential HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) are missing from all API responses.
- **Risk:** Medium. The application is more susceptible to client-side attacks such as Clickjacking, Cross-Site Scripting (XSS), and MIME-type sniffing.
- **Affected Code:** Global FastAPI application (`backend/app/main.py`).
- **Remediation:** Add a middleware to inject security headers. For example, use the `secure` package or manually add headers like `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff` in a custom FastAPI middleware.

## 8. Environment Variables and Secrets in Client Bundles
- **Exposure:** Environment variables and secrets are **properly excluded** from the client bundle. The frontend leverages Vite, which safely only bundles environment variables prefixed with `VITE_` (like `VITE_API_URL`). Backend secrets such as `JWT_SECRET_KEY` and `DATABASE_URL` are not exposed.
- **Risk:** None (Currently Secure).
- **Affected Code:** `frontend/src/api/client.js` and `frontend/vite.config.js`.
- **Remediation:** Maintain the current Vite environment variable naming convention to ensure backend secrets remain isolated.
