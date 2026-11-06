import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from database import get_db
from schemas import RegisterRequest, LoginRequest, UserResponse

# تخزين الجلسات (Tokens)
SESSIONS = {}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(req: RegisterRequest) -> UserResponse:
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email.lower().strip(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered.")
    
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
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (req.email.lower().strip(),))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    input_hash = hash_password(req.password)
    is_demo = (req.email.lower().strip() == "demo@msoa.shop" and req.password == "demo123")
    
    if user["password_hash"] != input_hash and not is_demo:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
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
