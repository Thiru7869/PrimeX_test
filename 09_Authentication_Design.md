# 09 — Authentication Design Architecture
## PrimeX AI · Enterprise Authentication Documentation

> **Document Version:** 1.0.0
> **Status:** Production Reference
> **Security Model:** JWT Access Token + Refresh Token (Stateless)
> **Project Motto:** *"Build a modular, production-grade, vendor-independent AI Operating System that can scale from free-tier infrastructure to enterprise architecture without redesign."*

---

## Table of Contents

1. [Authentication Goals](#1-authentication-goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Authentication Lifecycle Overview](#3-authentication-lifecycle-overview)
4. [Registration Flow](#4-registration-flow)
5. [Login Flow](#5-login-flow)
6. [JWT Strategy](#6-jwt-strategy)
7. [JWT Payload Structure](#7-jwt-payload-structure)
8. [Token Lifecycle](#8-token-lifecycle)
9. [Refresh Token Architecture](#9-refresh-token-architecture)
10. [Frontend Token Storage](#10-frontend-token-storage)
11. [Logout Architecture](#11-logout-architecture)
12. [Password Security](#12-password-security)
13. [Authorization Model (RBAC)](#13-authorization-model-rbac)
14. [Protected Routes Strategy](#14-protected-routes-strategy)
15. [Authentication Middleware](#15-authentication-middleware)
16. [Security Measures](#16-security-measures)
17. [Failed Login Strategy](#17-failed-login-strategy)
18. [Password Reset Architecture](#18-password-reset-architecture)
19. [Account Verification Architecture](#19-account-verification-architecture)
20. [Security Best Practices](#20-security-best-practices)
21. [Sequence Diagrams](#21-sequence-diagrams)
22. [Database Tables](#22-database-tables)
23. [Final Recommendations](#23-final-recommendations)

---

## 1. Authentication Goals

PrimeX AI's authentication system is designed with four foundational principles that align with the project's architecture mandate of production-grade, vendor-independent, scalable design.

### 1.1 Secure Authentication

- All passwords hashed with **bcrypt** (cost factor 12+); plaintext never stored or logged
- Tokens are short-lived and cryptographically signed
- All token operations (issue, validate, revoke) are auditable
- Brute force and replay attacks are mitigated at the infrastructure level

### 1.2 Stateless Backend

- The FastAPI backend is **completely stateless** — no server-side session store
- Authentication state is carried entirely in the JWT access token
- Only refresh token revocation requires a database check
- Enables zero-friction horizontal scaling on Render

### 1.3 Scalability

- No shared session memory between server instances
- Refresh token table is the only auth-related database dependency at runtime
- JWT validation is CPU-bound and does not require any I/O
- Architecture supports 10 → 10,000 concurrent users without redesign

### 1.4 Minimal Database Load

- Access token validation: **0 database queries** (pure JWT cryptographic verification)
- Refresh token validation: **1 database query** (token_hash lookup)
- Login: **2 queries** (user lookup + refresh token insert)
- Logout: **1 query** (refresh token revocation)

---

## 2. Architecture Overview

```mermaid
graph TB
    subgraph Frontend["Frontend (Next.js 15)"]
        UI["UI Components"]
        ZS["Zustand Auth Store\n(Access Token in Memory)"]
        COOKIE["HttpOnly Secure Cookie\n(Refresh Token)"]
        AX["TanStack Query\n(API Calls)"]
    end

    subgraph Backend["Backend (FastAPI)"]
        MW["Auth Middleware\nJWT Validation"]
        AR["Auth Router\n/api/v1/auth"]
        AS["AuthService"]
        HASH["bcrypt\nPassword Hashing"]
        JWTLib["python-jose\nJWT Sign/Verify"]
    end

    subgraph DB["Database (Neon PostgreSQL)"]
        UT[("users\ntable")]
        RT[("refresh_tokens\ntable")]
    end

    UI --> AX
    AX --> |"Authorization: Bearer token"| MW
    MW --> |"Valid token → inject user"| AR
    AR --> AS
    AS --> HASH
    AS --> JWTLib
    AS --> UT
    AS --> RT

    JWTLib --> |"Access Token (15min)"| ZS
    AR --> |"Refresh Token (30d)\nSet-Cookie"| COOKIE

    COOKIE --> |"Automatic cookie send"| AR
    ZS --> |"In-memory only"| AX
```

---

## 3. Authentication Lifecycle Overview

```mermaid
stateDiagram-v2
    [*] --> Unauthenticated

    Unauthenticated --> Registering : POST /auth/register
    Registering --> Unauthenticated : Validation Failed
    Registering --> Authenticated : Registration Success + Login

    Unauthenticated --> Authenticating : POST /auth/login
    Authenticating --> Unauthenticated : Invalid Credentials
    Authenticating --> Authenticated : Login Success

    Authenticated --> MakingRequest : API Call with Access Token
    MakingRequest --> Authenticated : Token Valid (200 OK)
    MakingRequest --> TokenExpired : 401 Unauthorized

    TokenExpired --> Refreshing : POST /auth/refresh (via cookie)
    Refreshing --> Authenticated : New Access Token Issued
    Refreshing --> Unauthenticated : Refresh Token Expired / Revoked

    Authenticated --> LoggingOut : POST /auth/logout
    LoggingOut --> Unauthenticated : Token Revoked + Cookie Cleared
```

---

## 4. Registration Flow

### 4.1 Flow Description

1. User submits email, password, and full name from the frontend
2. Frontend validates fields client-side before submission
3. FastAPI receives the request and Pydantic validates the payload
4. `AuthService` checks if the email already exists in the `users` table
5. Password is hashed using bcrypt with cost factor 12
6. New user record is inserted into the `users` table
7. A success response (201) is returned — no tokens are issued on registration
8. The frontend redirects the user to the login screen

### 4.2 Registration Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (Next.js)
    participant API as FastAPI Backend
    participant VAL as Pydantic Validator
    participant SVC as AuthService
    participant HASH as bcrypt
    participant DB as Neon PostgreSQL

    User->>FE: Fill registration form
    FE->>FE: Client-side validation
    FE->>API: POST /api/v1/auth/register\n{email, password, full_name}

    API->>VAL: Validate request schema
    alt Validation fails
        VAL-->>API: ValidationError
        API-->>FE: 422 Unprocessable Entity
        FE-->>User: Show field errors
    end

    VAL-->>API: Schema valid

    API->>SVC: register(email, password, full_name)
    SVC->>DB: SELECT * FROM users WHERE email = ?
    alt Email already exists
        DB-->>SVC: User found
        SVC-->>API: ConflictError
        API-->>FE: 409 Conflict
        FE-->>User: "Email already registered"
    end

    DB-->>SVC: No user found

    SVC->>HASH: bcrypt.hashpw(password, rounds=12)
    HASH-->>SVC: hashed_password

    SVC->>DB: INSERT INTO users (id, email, hashed_password, full_name, role)
    DB-->>SVC: User record created

    SVC-->>API: UserResponse
    API-->>FE: 201 Created {user: {...}}
    FE-->>User: Registration successful → redirect to login
```

### 4.3 Registration FastAPI Implementation

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import RegisterRequest, UserResponse
from app.services.auth_service import AuthService
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/register",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register New User"
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> SuccessResponse[UserResponse]:
    auth_service = AuthService(db)
    user = await auth_service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name
    )
    return SuccessResponse(data=UserResponse.model_validate(user))
```

---

## 5. Login Flow

### 5.1 Flow Description

1. User submits email and password credentials
2. FastAPI validates the request via Pydantic
3. `AuthService` fetches the user by email from the database
4. bcrypt verifies the submitted password against the stored hash
5. If credentials are valid, a JWT access token is generated (15-minute lifetime)
6. A refresh token is generated (30-day lifetime), hashed, and stored in `refresh_tokens`
7. The access token is returned in the JSON response body
8. The plaintext refresh token is set as an `HttpOnly; Secure` cookie

### 5.2 Login Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (Next.js)
    participant API as FastAPI Backend
    participant SVC as AuthService
    participant HASH as bcrypt
    participant JWT as python-jose
    participant DB as Neon PostgreSQL

    User->>FE: Enter email + password
    FE->>API: POST /api/v1/auth/login\n{email, password}

    API->>SVC: login(email, password)

    SVC->>DB: SELECT * FROM users WHERE email = ?
    alt User not found
        DB-->>SVC: No record
        SVC-->>API: AuthenticationError
        API-->>FE: 401 Unauthorized\n"Invalid credentials"
        FE-->>User: Show error (no email/password hint)
    end

    DB-->>SVC: User record

    SVC->>HASH: bcrypt.checkpw(password, hashed_password)
    alt Password incorrect
        HASH-->>SVC: False
        SVC-->>API: AuthenticationError
        API-->>FE: 401 Unauthorized
        FE-->>User: Show error
    end

    HASH-->>SVC: True (valid)

    SVC->>JWT: create_access_token({sub, email, role, exp: +15min})
    JWT-->>SVC: access_token (JWT string)

    SVC->>JWT: generate_refresh_token() → UUID
    JWT-->>SVC: refresh_token (UUID string)

    SVC->>HASH: bcrypt.hashpw(refresh_token)
    HASH-->>SVC: token_hash

    SVC->>DB: INSERT INTO refresh_tokens\n(user_id, token_hash, expires_at: +30d)
    DB-->>SVC: Stored

    SVC-->>API: {access_token, refresh_token, user}

    API-->>FE: 200 OK\nJSON: {access_token, user}\nSet-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth
    FE->>FE: Store access_token in Zustand (memory)
    FE-->>User: Authenticated → redirect to dashboard
```

---

## 6. JWT Strategy

### 6.1 Access Token

| Property | Value |
|---|---|
| **Type** | JWT (JSON Web Token) |
| **Algorithm** | HS256 (HMAC-SHA256) |
| **Lifetime** | **15 minutes** |
| **Secret** | `JWT_SECRET_KEY` environment variable (min 32 chars) |
| **Storage** | Zustand in-memory store (never localStorage) |

**Design Decision:** 15 minutes is the industry standard balance between security and usability. A short-lived access token limits the blast radius if a token is intercepted — it's unusable within 15 minutes without the refresh token, which is stored in an HttpOnly cookie inaccessible to JavaScript.

### 6.2 Refresh Token

| Property | Value |
|---|---|
| **Type** | Opaque UUID (not JWT) |
| **Lifetime** | **30 days** |
| **Storage** | `refresh_tokens` database table (hashed) |
| **Transport** | HttpOnly Secure Cookie |
| **Rotation** | Issued on every refresh; old token revoked |

**Design Decision:** The refresh token is a random UUID, not a JWT, to ensure it cannot be decoded or predicted. It is stored hashed in the database so that even a database breach does not expose valid tokens. The 30-day lifetime reduces login friction for regular users while ensuring inactive accounts are automatically logged out.

### 6.3 Token Rotation

On every successful refresh:
1. The incoming refresh token is **revoked** (marked `revoked = true` in DB)
2. A brand-new refresh token is **issued** and its hash stored
3. The new token is sent in a new `Set-Cookie` response

This prevents token theft via replay — a stolen refresh token can only be used once before rotation invalidates it.

### 6.4 Implementation

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import uuid
import os

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload.update({
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "access"
    })
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return str(uuid.uuid4())

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise AuthenticationError("Token is invalid or expired")
```

---

## 7. JWT Payload Structure

### 7.1 Claims Reference

| Claim | Name | Description | Example |
|---|---|---|---|
| `sub` | Subject | User's unique ID (UUID) | `"usr_01J2K3M4N5"` |
| `email` | Email | User's email address | `"jane@example.com"` |
| `role` | Role | User's RBAC role | `"user"` or `"admin"` |
| `exp` | Expiration | Unix timestamp of expiry | `1705313400` |
| `iat` | Issued At | Unix timestamp of creation | `1705312500` |
| `jti` | JWT ID | Unique token identifier (UUID) | `"3f7b1c2e-..."` |
| `type` | Token Type | Distinguishes access from other tokens | `"access"` |

### 7.2 Example JWT Payload (Decoded)

```json
{
  "sub": "usr_01J2K3M4N5P6Q7R8",
  "email": "jane.doe@example.com",
  "role": "user",
  "full_name": "Jane Doe",
  "exp": 1705313400,
  "iat": 1705312500,
  "jti": "3f7b1c2e-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
  "type": "access"
}
```

> **Note:** The JWT is Base64-encoded, **not encrypted**. Never include sensitive data (passwords, PII beyond email, payment data) in the payload.

### 7.3 JWT Structure

```
Header.Payload.Signature

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9         ← Header (alg + typ)
.eyJzdWIiOiJ1c3JfMDFKMkszTTRONVA2UTdSOCIsImVtYWlsIjoiamFuZUBleGFtcGxlLmNvbSJ9  ← Payload
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c  ← HMAC-SHA256 Signature
```

---

## 8. Token Lifecycle

```mermaid
graph LR
    subgraph Access_Token["Access Token Lifecycle"]
        A1["Created on Login\n(15 min TTL)"] --> A2["Stored in Zustand\n(memory only)"]
        A2 --> A3["Sent in Authorization header\nBearer token"]
        A3 --> A4{"Expired?"}
        A4 --> |"No"| A3
        A4 --> |"Yes"| A5["Trigger Silent Refresh"]
        A5 --> A1
    end

    subgraph Refresh_Token["Refresh Token Lifecycle"]
        R1["Generated on Login\n(UUID, 30 day TTL)"] --> R2["Hash stored in DB\ntoken_hash column"]
        R2 --> R3["Plaintext in HttpOnly Cookie"]
        R3 --> R4["Used to refresh access token"]
        R4 --> R5{"Valid & not revoked?"}
        R5 --> |"Yes"| R6["Revoke old token\nIssue new token\n(Rotation)"]
        R6 --> R1
        R5 --> |"No"| R7["Force re-login\n401 Unauthorized"]
    end
```

### Token States

| State | Description | Action Required |
|---|---|---|
| **Active** | Token is valid and within its TTL | Use normally |
| **Expired** | Past the `exp` claim | Access: refresh silently; Refresh: re-login |
| **Revoked** | Marked `revoked=true` in DB | Re-login required |
| **Rotated** | Superseded by new token after refresh | New token is active |
| **Invalidated** | Global logout: all tokens for user revoked | Re-login required |

---

## 9. Refresh Token Architecture

### 9.1 Database Table: `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at  TIMESTAMP WITH TIME ZONE,
    device_hint VARCHAR(100)  -- Optional: "Chrome/macOS", "Mobile/iOS"
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

### 9.2 Refresh Flow Diagram

```mermaid
sequenceDiagram
    participant FE as Frontend (Next.js)
    participant API as FastAPI Backend
    participant SVC as AuthService
    participant DB as Neon PostgreSQL

    Note over FE: Access token expired → intercept 401
    FE->>API: POST /api/v1/auth/refresh\n(Cookie: refresh_token=<uuid>)

    API->>SVC: refresh(refresh_token_from_cookie)

    SVC->>SVC: bcrypt.hashpw(incoming_token)
    SVC->>DB: SELECT * FROM refresh_tokens\nWHERE token_hash = ? AND revoked = false

    alt Token not found or revoked
        DB-->>SVC: No record
        SVC-->>API: AuthenticationError
        API-->>FE: 401 Unauthorized\nClear cookie
        FE->>FE: Clear Zustand state\nRedirect to /login
    end

    DB-->>SVC: refresh_token record

    alt Token expired
        SVC->>DB: UPDATE refresh_tokens SET revoked=true WHERE id = ?
        SVC-->>API: AuthenticationError("Refresh token expired")
        API-->>FE: 401 Unauthorized
    end

    Note over SVC: Token is valid — rotate it

    SVC->>DB: UPDATE refresh_tokens SET revoked=true, revoked_at=NOW() WHERE id = ?
    
    SVC->>SVC: new_refresh_token = generate_refresh_token()
    SVC->>DB: INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
    
    SVC->>SVC: new_access_token = create_access_token({sub, email, role})

    SVC-->>API: {new_access_token, new_refresh_token}
    API-->>FE: 200 OK\nJSON: {access_token}\nSet-Cookie: refresh_token=<new>; HttpOnly; Secure
    FE->>FE: Update Zustand with new access_token
```

### 9.3 Token Revocation

```python
async def revoke_refresh_token(self, token: str, db: AsyncSession) -> None:
    """Revoke a single refresh token (single-device logout)."""
    token_hash = self._hash_token(token)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked=True, revoked_at=datetime.now(timezone.utc))
    )
    await db.execute(stmt)
    await db.commit()

async def revoke_all_user_tokens(self, user_id: str, db: AsyncSession) -> None:
    """Revoke all refresh tokens for a user (global logout)."""
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        )
        .values(revoked=True, revoked_at=datetime.now(timezone.utc))
    )
    await db.execute(stmt)
    await db.commit()
```

### 9.4 Expired Token Cleanup

A scheduled job (Render Cron or APScheduler) purges expired tokens daily:

```python
async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """Remove expired refresh tokens to keep the table lean."""
    stmt = delete(RefreshToken).where(
        RefreshToken.expires_at < datetime.now(timezone.utc)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
```

---

## 10. Frontend Token Storage

### 10.1 Access Token — Zustand In-Memory Store

```typescript
// stores/authStore.ts
import { create } from 'zustand'

interface AuthState {
  accessToken: string | null
  user: User | null
  isAuthenticated: boolean
  setTokens: (accessToken: string, user: User) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,

  setTokens: (accessToken, user) =>
    set({ accessToken, user, isAuthenticated: true }),

  clearAuth: () =>
    set({ accessToken: null, user: null, isAuthenticated: false }),
}))
```

**Why in-memory (not localStorage)?**

| Storage | XSS Risk | Survives Refresh | Notes |
|---|---|---|---|
| `localStorage` | ❌ HIGH — Any JS can read it | ✅ Yes | Never use for tokens |
| `sessionStorage` | ❌ HIGH | ❌ No | Same XSS risk |
| Zustand memory | ✅ None — Not DOM-accessible | ❌ No (by design) | Correct choice |
| HttpOnly Cookie | ✅ None — JS cannot read | ✅ Yes | Used for refresh token |

When the page refreshes and the Zustand store is empty, the app silently calls `/auth/refresh` using the HttpOnly cookie to restore the session.

### 10.2 Refresh Token — HttpOnly Cookie

Set by the server on login and refresh:

```python
from fastapi import Response

def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,          # JavaScript cannot access this cookie
        secure=True,            # Only sent over HTTPS
        samesite="strict",      # No cross-site sending (CSRF protection)
        max_age=60 * 60 * 24 * 30,  # 30 days in seconds
        path="/api/v1/auth",    # Scoped — only sent to auth endpoints
    )

def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        secure=True,
        httponly=True,
        samesite="strict"
    )
```

### 10.3 Silent Token Refresh (Axios Interceptor)

```typescript
// lib/apiClient.ts
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true,  // Required to send HttpOnly cookie
})

// Attach access token to every request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Silent refresh on 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true
      try {
        const { data } = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/refresh`,
          {},
          { withCredentials: true }
        )
        const { access_token } = data.data
        useAuthStore.getState().setTokens(access_token, useAuthStore.getState().user!)
        error.config.headers.Authorization = `Bearer ${access_token}`
        return apiClient(error.config)
      } catch {
        useAuthStore.getState().clearAuth()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient
```

---

## 11. Logout Architecture

### 11.1 Single-Device Logout

Revokes only the refresh token associated with the current session:

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Neon PostgreSQL

    User->>FE: Click "Logout"
    FE->>API: POST /api/v1/auth/logout\nAuthorization: Bearer <access_token>\nCookie: refresh_token=<uuid>

    API->>DB: UPDATE refresh_tokens SET revoked=true\nWHERE token_hash = hash(cookie_token)
    DB-->>API: Updated

    API-->>FE: 204 No Content\nSet-Cookie: refresh_token=; Expires=epoch; HttpOnly

    FE->>FE: useAuthStore.clearAuth()\nRedirect to /login
    FE-->>User: Logged out
```

### 11.2 Global Logout (All Devices)

Revokes all active refresh tokens for the user:

```python
@router.post("/auth/logout-all", status_code=204)
async def logout_all_devices(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    await auth_service.revoke_all_user_tokens(current_user.id)
    clear_refresh_cookie(response)
```

| Logout Type | Scope | Use Case |
|---|---|---|
| **Single Device** | Revokes current device's token | Normal logout button |
| **Global Logout** | Revokes ALL user tokens | "Sign out everywhere" in settings |
| **Admin Revoke** | Admin revokes specific user tokens | Account suspension, security incident |

---

## 12. Password Security

### 12.1 bcrypt Implementation

```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Work factor — adjust upward as hardware improves
)

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt. Never store the plain password."""
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a submitted password against the stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

**Why bcrypt with rounds=12?**

- bcrypt is specifically designed to be slow — resistant to GPU-based brute force attacks
- Rounds=12 means 2^12 = 4,096 iterations — each hash takes ~100ms on modern hardware
- Even with 1,000 GPU cores, cracking a 12-char random password would take centuries
- Rounds should be increased to 13-14 as hardware improves (Alembic migration required)

### 12.2 Password Requirements

| Rule | Minimum |
|---|---|
| Length | 8 characters |
| Uppercase letters | 1 required |
| Lowercase letters | 1 required |
| Numeric digits | 1 required |
| Special characters | 1 required (`!@#$%^&*...`) |
| Maximum length | 128 characters (bcrypt limit safety) |

### 12.3 Password Pydantic Validator

```python
import re
from pydantic import field_validator

@field_validator("password")
@classmethod
def validate_password_strength(cls, v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(v) > 128:
        raise ValueError("Password must not exceed 128 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};':\"\\|,.<>/?`~]", v):
        raise ValueError("Password must contain at least one special character")
    return v
```

### 12.4 Security Rules

- **Never log passwords** — not in plaintext, not partially masked
- **Never store plaintext passwords** — only the bcrypt hash
- **Never compare passwords in plaintext** — always use `pwd_context.verify()`
- **Never return password hashes** in API responses
- **Sanitize password fields** from log outputs using Sentry scrubber

---

## 13. Authorization Model (RBAC)

### 13.1 Current Roles

| Role | Description | Permissions |
|---|---|---|
| `user` | Standard registered user | Own resources only |
| `admin` | Platform administrator | All user resources + admin endpoints |

### 13.2 Future Roles

| Role | Description |
|---|---|
| `super_admin` | Infrastructure-level access; Anthropic/internal only |
| `org_admin` | Multi-tenant organization administrator |
| `read_only` | View-only access for auditors or shared accounts |

### 13.3 Role Storage

Stored in the `users.role` column as an enum:

```python
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
```

### 13.4 Role-Based Route Guards

```python
from fastapi import Depends, HTTPException, status
from app.models.user import User, UserRole

def require_role(*roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# Usage:
@router.get("/admin/users")
async def list_users(
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    ...
```

---

## 14. Protected Routes Strategy

### 14.1 Backend Route Protection

Every protected FastAPI endpoint uses the `get_current_user` dependency:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.models.user import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency — validates JWT and returns the current user.
    Raises 401 if token is missing, invalid, or expired.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token payload missing 'sub' claim")
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found"
        )
    return user
```

### 14.2 Frontend Route Guards

```typescript
// middleware.ts (Next.js 15 App Router)
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_ROUTES = ['/login', '/register', '/forgot-password']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname.startsWith(route))

  // Check for refresh token cookie (presence only — can't read HttpOnly in middleware)
  const hasRefreshToken = request.cookies.has('refresh_token')

  if (!isPublicRoute && !hasRefreshToken) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)']
}
```

```typescript
// hooks/useRequireAuth.ts
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'

export function useRequireAuth() {
  const { isAuthenticated, accessToken } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      router.push('/login')
    }
  }, [isAuthenticated, accessToken, router])

  return { isAuthenticated }
}
```

---

## 15. Authentication Middleware

### 15.1 JWT Validation Middleware

FastAPI handles auth via dependency injection, not traditional middleware, for fine-grained route control:

```python
# app/dependencies/auth.py

from functools import lru_cache
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User

# Shorthand type aliases for route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]

# Usage in routes — clean and readable
@router.get("/chats")
async def list_chats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    ...
```

### 15.2 Request Logging Middleware

```python
import time
import uuid
from fastapi import Request

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start_time) * 1000
    
    # Attach request ID to response for client correlation
    response.headers["X-Request-ID"] = request_id
    
    # Structured log (Sentry / stdout)
    import logging
    logger = logging.getLogger("primexai.http")
    logger.info(
        "HTTP Request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2)
        }
    )
    
    return response
```

---

## 16. Security Measures

### 16.1 CSRF Protection

HttpOnly cookie + `SameSite=Strict` prevents cross-site request forgery:

- `SameSite=Strict` means the refresh token cookie is only sent when navigating from the same origin
- No CSRF tokens required because we use `Authorization: Bearer` for access (not cookies)
- The only cookie (refresh token) is scoped to `/api/v1/auth` path — not sent on other requests

### 16.2 XSS Protection

- Access token stored in Zustand (JavaScript memory) — not in DOM-accessible storage
- Refresh token in `HttpOnly` cookie — JavaScript cannot read `document.cookie`
- Content Security Policy (CSP) headers prevent script injection
- All user-provided content is sanitized before rendering in the frontend

### 16.3 Brute Force Protection

```python
# Rate limiting on auth endpoints via SlowAPI
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("10/minute;50/hour")
async def login(request: Request, credentials: LoginRequest, ...):
    ...

@router.post("/auth/register")
@limiter.limit("5/minute;20/hour")
async def register(request: Request, payload: RegisterRequest, ...):
    ...
```

### 16.4 Credential Stuffing Prevention

- Consistent error messages: always `"Invalid credentials"` (never `"Email not found"` or `"Wrong password"`)
- Timing-safe comparison via `pwd_context.verify()` — prevents timing attacks
- IP-based rate limiting combined with per-user login attempt counting
- Optional: CAPTCHA on login after 5 failed attempts (future v2)

### 16.5 Replay Attacks

- JWT `jti` (JWT ID) claim is a unique UUID per token
- Short 15-minute access token TTL limits replay window
- Refresh token rotation means a replayed refresh token is immediately invalidated

### 16.6 Security Headers Summary

| Header | Value | Purpose |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Content-Security-Policy` | `default-src 'self'` | XSS mitigation |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Prevent data leakage |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter |

---

## 17. Failed Login Strategy

### 17.1 Login Attempt Tracking

```python
# Lightweight in-memory tracking (upgrade to Redis for distributed)
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

login_attempts: dict[str, list[datetime]] = defaultdict(list)
LOCKOUT_THRESHOLD = 10
LOCKOUT_WINDOW_MINUTES = 15
LOCKOUT_DURATION_MINUTES = 30

def check_login_lockout(identifier: str) -> bool:
    """Returns True if the identifier (IP or email) is currently locked out."""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    
    # Clean old attempts
    login_attempts[identifier] = [
        t for t in login_attempts[identifier] if t > window_start
    ]
    
    return len(login_attempts[identifier]) >= LOCKOUT_THRESHOLD

def record_failed_attempt(identifier: str) -> int:
    login_attempts[identifier].append(datetime.utcnow())
    return len(login_attempts[identifier])
```

### 17.2 Lockout Response

When threshold reached, return `429 Too Many Requests`:

```json
{
  "success": false,
  "error": {
    "code": "ACCOUNT_TEMPORARILY_LOCKED",
    "message": "Too many failed login attempts. Please try again in 30 minutes.",
    "details": null
  }
}
```

### 17.3 Strategy Table

| Attempt # | Action |
|---|---|
| 1–5 | Standard 401 response |
| 6–10 | 401 + add delay (exponential backoff hint) |
| 10+ | 429 + `Retry-After: 1800` header + lockout for 30 minutes |
| Admin override | Admin can manually unlock via admin API (future) |

---

## 18. Password Reset Architecture

> **Status:** Planned for v1.1 — not included in initial production release.

### 18.1 Planned Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant EMAIL as Email Service (Resend)
    participant DB as Neon PostgreSQL

    User->>FE: Enter email on /forgot-password
    FE->>API: POST /api/v1/auth/forgot-password {email}
    API->>DB: Find user by email
    alt User exists
        API->>API: Generate secure reset token (UUID, 1hr TTL)
        API->>DB: Store hashed reset token in password_reset_tokens
        API->>EMAIL: Send reset email with link
    end
    API-->>FE: 200 OK "If email exists, reset link sent"
    Note over FE: Intentionally vague — prevents email enumeration

    User->>FE: Click link → /reset-password?token=UUID
    FE->>API: POST /api/v1/auth/reset-password {token, new_password}
    API->>DB: Verify token (not expired, not used)
    API->>API: Hash new password
    API->>DB: Update users.hashed_password\nMark token as used\nRevoke all refresh tokens
    API-->>FE: 200 OK
    FE-->>User: Password changed → redirect to login
```

---

## 19. Account Verification Architecture

> **Status:** Planned for v1.1 — not included in initial production release.

### 19.1 Planned Flow

```mermaid
flowchart TD
    A[User Registers] --> B[Insert user with is_verified=false]
    B --> C[Generate email_verification_token UUID]
    C --> D[Send verification email via Resend]
    D --> E{User clicks link?}
    E -->|Yes, within 24h| F[Verify token in DB]
    F --> G[Update users.is_verified = true]
    G --> H[User can access all features]
    E -->|No| I[Partial access until verified]
    I --> J[User can resend verification email]
    J --> D
    E -->|Token expired| K[Token TTL exceeded]
    K --> J
```

---

## 20. Security Best Practices

### 20.1 Environment Variables

All secrets are stored as environment variables. Never hardcode in source:

```bash
# .env (never committed to git)
JWT_SECRET_KEY=<min-32-char-random-string>
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
SENTRY_DSN=https://...@sentry.io/...
ENVIRONMENT=production
```

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret_key: str
    database_url: str
    sentry_dsn: str
    environment: str = "production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 20.2 Secret Rotation

| Secret | Rotation Policy | Impact on Active Sessions |
|---|---|---|
| `JWT_SECRET_KEY` | Every 90 days or on breach | All active access tokens invalidated immediately |
| Database password | Every 90 days | No user impact (server-side only) |
| Refresh token hash salt | Never (bcrypt handles internally) | N/A |

On `JWT_SECRET_KEY` rotation: all active access tokens become invalid. Users with valid refresh tokens will get a new access token on the next request (transparent). Users without a valid refresh token must re-login.

### 20.3 HTTPS Only

- Render automatically provisions TLS for all deployments
- HTTP requests are redirected to HTTPS at the load balancer
- `Strict-Transport-Security` header enforces this at the browser level
- Secure cookie attribute ensures cookies are never sent over HTTP

### 20.4 Secure Cookie Configuration

```python
# Full secure cookie attributes for production
response.set_cookie(
    key="refresh_token",
    value=token,
    httponly=True,       # ✅ No JavaScript access
    secure=True,         # ✅ HTTPS only
    samesite="strict",   # ✅ No cross-origin sending
    max_age=2592000,     # ✅ 30 days
    path="/api/v1/auth", # ✅ Minimal scope — not sent on every request
    domain=None,         # Use current domain — no subdomain sharing
)
```

---

## 21. Sequence Diagrams

### 21.1 Registration

*(See Section 4.2 — Registration Sequence Diagram)*

### 21.2 Login

*(See Section 5.2 — Login Sequence Diagram)*

### 21.3 Token Refresh

*(See Section 9.2 — Refresh Flow Diagram)*

### 21.4 Logout

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (Next.js)
    participant ZS as Zustand Store
    participant API as FastAPI Backend
    participant DB as Neon PostgreSQL

    User->>FE: Click "Logout"

    FE->>API: POST /api/v1/auth/logout\nAuthorization: Bearer <access_token>\nCookie: refresh_token=<uuid>

    API->>API: Decode access_token → get user_id
    API->>API: Hash cookie refresh_token

    API->>DB: UPDATE refresh_tokens\nSET revoked=true, revoked_at=NOW()\nWHERE token_hash = ? AND user_id = ?

    DB-->>API: 1 row updated

    API-->>FE: 204 No Content\nSet-Cookie: refresh_token=; Expires=Thu, 01 Jan 1970; HttpOnly; Secure; Path=/api/v1/auth

    FE->>ZS: clearAuth() → accessToken=null, user=null
    FE->>FE: Redirect to /login
    FE-->>User: Logged out successfully
```

---

## 22. Database Tables

### 22.1 Table: `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'admin', 'super_admin')),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### Column Reference

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() | Unique user identifier |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Login identifier |
| `hashed_password` | VARCHAR(255) | NOT NULL | bcrypt hash |
| `full_name` | VARCHAR(100) | NOT NULL | Display name |
| `role` | VARCHAR(20) | NOT NULL, default 'user', CHECK | RBAC role |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Soft-disable accounts |
| `is_verified` | BOOLEAN | NOT NULL, default FALSE | Email verification status |
| `created_at` | TIMESTAMPTZ | NOT NULL, default NOW() | Account creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-updated | Last modification time |

### 22.2 Table: `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked     BOOLEAN      NOT NULL DEFAULT FALSE,
    revoked_at  TIMESTAMP WITH TIME ZONE,
    device_hint VARCHAR(100),
    ip_address  VARCHAR(45)
);

-- Indexes
CREATE INDEX idx_refresh_tokens_user_id   ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_revoked    ON refresh_tokens(revoked) WHERE revoked = FALSE;
```

#### Column Reference

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique token record identifier |
| `user_id` | UUID | FK → users.id, CASCADE DELETE | Owner of the token |
| `token_hash` | VARCHAR(255) | NOT NULL, UNIQUE | bcrypt hash of the plaintext UUID token |
| `expires_at` | TIMESTAMPTZ | NOT NULL | When this token expires (login time + 30 days) |
| `created_at` | TIMESTAMPTZ | NOT NULL, default NOW() | When this token was issued |
| `revoked` | BOOLEAN | NOT NULL, default FALSE | True if logout or rotation has occurred |
| `revoked_at` | TIMESTAMPTZ | Nullable | When revocation occurred |
| `device_hint` | VARCHAR(100) | Nullable | Browser/device info for UX (e.g., "Chrome on macOS") |
| `ip_address` | VARCHAR(45) | Nullable | IP at issuance for audit trail |

### 22.3 SQLAlchemy Models

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
```

---

## 23. Final Recommendations

### Architecture Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| **Token Strategy** | JWT (access) + Opaque UUID (refresh) | JWT for stateless validation; opaque UUID for secure revocation |
| **Access Token TTL** | 15 minutes | Limits theft blast radius; transparent refresh for UX |
| **Refresh Token TTL** | 30 days | Balances security and user convenience |
| **Access Token Storage** | Zustand memory | Immune to XSS; cleared on browser close |
| **Refresh Token Storage** | HttpOnly Secure Cookie | JS-inaccessible; scoped to auth endpoints only |
| **Password Hashing** | bcrypt rounds=12 | Designed for password hashing; GPU-resistant |
| **Rotation Policy** | Every refresh | Prevents replay of stolen refresh tokens |
| **Revocation** | DB-backed token_hash | Enables immediate global and single-device logout |

### Non-Negotiable Security Rules

1. **Never store plaintext passwords** — bcrypt only, always
2. **Never put tokens in localStorage** — Zustand memory or HttpOnly cookie only
3. **Never return hashed passwords** in any API response
4. **Never expose specific login failure reasons** — always "Invalid credentials"
5. **Never skip `Depends(get_current_user)`** on protected endpoints
6. **Never commit secrets** to the repository — `.env` must be in `.gitignore`
7. **Always validate JWT expiry** — never trust an expired token
8. **Always rotate refresh tokens** — single-use is non-negotiable

### Production Checklist

- [ ] `JWT_SECRET_KEY` set to 64+ character random string in environment
- [ ] `HTTPS` enforced at Render load balancer level
- [ ] `Secure` cookie attribute enabled (fails silently on HTTP)
- [ ] Sentry DSN configured for error monitoring
- [ ] Rate limiting tested under load
- [ ] Database indexes verified via `EXPLAIN ANALYZE`
- [ ] Refresh token cleanup cron job scheduled
- [ ] Login brute force tested and blocked at 10 attempts
- [ ] Token rotation verified — old token rejected after refresh
- [ ] Global logout tested — all devices lose access

### Future Security Enhancements (v2+)

| Feature | Priority | Notes |
|---|---|---|
| Email verification | High | Prevent spam accounts |
| Password reset flow | High | Critical for UX |
| CAPTCHA on login | Medium | After 5 failed attempts |
| OAuth (Google) | Medium | Reduce friction; keep JWT-native as primary |
| MFA / TOTP | Medium | Enterprise security requirement |
| Audit log table | Low | Track all auth events for compliance |
| Device management UI | Low | Let users see and revoke sessions per device |

---

*Document maintained by PrimeX AI Engineering. Last updated: 2025-01-15. Version 1.0.0.*
