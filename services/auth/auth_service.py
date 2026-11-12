import hashlib
import hmac
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import HTTPException
from database import get_db
from schemas import RegisterRequest, LoginRequest, UserResponse

# تخزين الجلسات (Tokens)
SESSIONS = {}

BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (random salt + adaptive cost)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")


def _is_legacy_sha256(stored_hash: str) -> bool:
    return len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash)


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a bcrypt hash, or a legacy unsalted SHA-256 hash."""
    if stored_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError:
            return False
    if _is_legacy_sha256(stored_hash):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, stored_hash)
    return False


def _upgrade_legacy_hash(user_id: str, password: str) -> None:
    """Re-hash a legacy SHA-256 password with bcrypt after a successful login."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), user_id),
        )
        conn.commit()
    finally:
        conn.close()

def _is_valid_email(email: str) -> bool:
    local, sep, domain = email.partition("@")
    return bool(sep and local and "." in domain and " " not in email)


def register_user(req: RegisterRequest) -> UserResponse:
    if not req.name.strip() or not req.email.strip() or not req.password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    if not _is_valid_email(req.email.strip()):
        raise HTTPException(status_code=400, detail="Invalid email format.")

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email.lower().strip(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Email already registered.")
    
    if len(req.password.encode("utf-8")) > 72:
        conn.close()
        raise HTTPException(status_code=400, detail="Password must be at most 72 bytes.")

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)
    created_at = datetime.now(timezone.utc).isoformat()
    clean_name = req.name.strip()
    clean_email = req.email.lower().strip()
    
    cursor.execute(
        "INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, clean_name, clean_email, pw_hash, "CUSTOMER", created_at)
    )
    conn.commit()
    conn.close()
    
    return UserResponse(
        id=user_id,
        name=clean_name,
        email=clean_email,
        role="CUSTOMER"
    )

def authenticate_user(req: LoginRequest):
    if not req.email.strip() or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (req.email.lower().strip(),))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if _is_legacy_sha256(user["password_hash"]):
        _upgrade_legacy_hash(user["id"], req.password)

    token = f"token-{uuid.uuid4()}"
    user_data = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    }
    SESSIONS[token] = user_data
    
    return user_data, token

def get_user_by_token(raw_authorization: str = None, token_param: str = None) -> dict:
    actual_token = None
    if raw_authorization:
        clean_auth = raw_authorization.strip().strip('"').strip("'")
        if clean_auth.startswith("Bearer "):
            actual_token = clean_auth.split(" ", 1)[1].strip()
        else:
            actual_token = clean_auth
    elif token_param:
        actual_token = token_param.strip().strip('"').strip("'")
    
    if not actual_token:
        raise HTTPException(status_code=401, detail="Missing or invalid token.")
    
    if actual_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")
    
    return SESSIONS[actual_token]

def logout_user(raw_authorization: str = None, token_param: str = None):
    actual_token = None
    if raw_authorization:
        clean_auth = raw_authorization.strip().strip('"').strip("'")
        if clean_auth.startswith("Bearer "):
            actual_token = clean_auth.split(" ", 1)[1].strip()
        else:
            actual_token = clean_auth
    elif token_param:
        actual_token = token_param.strip().strip('"').strip("'")
        
    if actual_token:
        SESSIONS.pop(actual_token, None)
    return {"success": True}
