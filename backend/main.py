import os
import sys
import shutil
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure local modules resolve when started from repo root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db,
    get_or_create_user,
    store_otp,
    verify_otp,
    save_document,
    get_user_documents,
    get_document_details,
    delete_document,
    toggle_task_completion,
    save_chat_message,
    get_chat_history,
    get_user_dashboard,
)
from parser import extract_content
from analyzer import analyze_document_text, answer_chat_question
from email_otp import generate_otp, get_otp_expiry, send_otp_email

init_db()

app = FastAPI(title="ActionLens API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)

# ─── Request/Response Models ──────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    email: str

class OTPVerifyRequest(BaseModel):
    user_id: int
    otp: str

class ToggleTaskRequest(BaseModel):
    completed: bool

class ChatRequest(BaseModel):
    document_id: str
    question: str

# ─── Auth Endpoints ───────────────────────────────────────────

@app.post("/api/login")
def login(request: LoginRequest):
    """
    Step 1 of auth. Accepts username + email.
    Creates user if new, validates email if existing, then sends OTP.
    Returns user info (without verified=True — frontend must call /api/verify-otp next).
    """
    if not request.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    if not request.email.strip() or "@" not in request.email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    try:
        user = get_or_create_user(request.username, request.email)
    except ValueError as e:
        if str(e) == "EMAIL_MISMATCH":
            raise HTTPException(
                status_code=403,
                detail="This username is already registered with a different email address. Please use the correct email."
            )
        raise HTTPException(status_code=500, detail=str(e))

    if not user:
        raise HTTPException(status_code=500, detail="Failed to create or retrieve user.")

    # Generate and store OTP
    otp = generate_otp()
    expires_at = get_otp_expiry()
    store_otp(user["id"], otp, expires_at)


    # Send email — returns (success, demo_otp)
    _sent, demo_otp = send_otp_email(request.email, otp, request.username)

    return {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "demo_otp": demo_otp,  # None if email was delivered; OTP string if shown in UI
        "message": "OTP sent to your email." if not demo_otp else "Email delivery unavailable — your OTP is shown below."
    }

@app.post("/api/verify-otp")
def verify_otp_endpoint(request: OTPVerifyRequest):
    """
    Step 2 of auth. Verifies the OTP for a user.
    Returns full user session on success.
    """
    if not request.otp.strip():
        raise HTTPException(status_code=400, detail="OTP cannot be empty.")

    is_valid = verify_otp(request.user_id, request.otp.strip())
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP. Please request a new one.")

    # Return session data
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (request.user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found.")

    return dict(row)

# ─── Document Endpoints ───────────────────────────────────────

@app.post("/api/analyze")
async def analyze_documents(
    files: Optional[List[UploadFile]] = File(None),
    pasted_text: Optional[str] = Form(None),
    user_id: int = Query(...),
):
    if not files and (not pasted_text or not pasted_text.strip()):
        raise HTTPException(status_code=400, detail="No content provided. Upload a file or paste text.")

    combined_text_segments = []

    if files:
        for file in files:
            if not file.filename:
                continue
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".txt"]:
                continue

            temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}{ext}")
            try:
                with open(temp_path, "wb") as buf:
                    shutil.copyfileobj(file.file, buf)
                extracted = extract_content(temp_path)
                combined_text_segments.append(extracted)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    if pasted_text and pasted_text.strip():
        combined_text_segments.append(f"--- [Source: Pasted Text/Message] ---\n{pasted_text.strip()}")

    if not combined_text_segments:
        raise HTTPException(status_code=400, detail="Could not extract content from inputs.")

    combined_raw_text = "\n\n".join(combined_text_segments)
    analysis = analyze_document_text(combined_raw_text)

    doc_id = str(uuid.uuid4())
    save_document(
        user_id=user_id,
        doc_id=doc_id,
        title=analysis["title"],
        summary=analysis["summary"],
        extracted_json=analysis,
        raw_text=combined_raw_text,
        confidence_level=analysis["confidence_level"],
        confidence_explanation=analysis["confidence_explanation"],
    )

    return get_document_details(doc_id, user_id)

@app.get("/api/documents")
def list_documents(user_id: int = Query(...)):
    return get_user_documents(user_id)

@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str, user_id: int = Query(...)):
    doc = get_document_details(doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc

@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: str, user_id: int = Query(...)):
    success = delete_document(doc_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or delete failed.")
    return {"status": "success"}

# ─── Dashboard Endpoint ───────────────────────────────────────

@app.get("/api/dashboard/{user_id}")
def get_dashboard(user_id: int):
    """Returns aggregated deadlines + pending tasks across ALL user documents."""
    return get_user_dashboard(user_id)

# ─── Task Endpoints ───────────────────────────────────────────

@app.post("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: str, request: ToggleTaskRequest, user_id: int = Query(...)):
    success = toggle_task_completion(task_id, request.completed, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or access denied.")
    return {"status": "success", "completed": request.completed}

# ─── Chat Endpoints ───────────────────────────────────────────

@app.post("/api/chat")
def chat_with_document(request: ChatRequest, user_id: int = Query(...)):
    doc = get_document_details(request.document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")

    history = get_chat_history(request.document_id, limit=10)
    answer, evidence = answer_chat_question(doc["raw_text"], history, request.question)

    save_chat_message(request.document_id, "user", request.question)
    saved_msg = save_chat_message(request.document_id, "assistant", answer, evidence)
    return saved_msg

@app.get("/api/documents/{doc_id}/chat")
def get_chats(doc_id: str, user_id: int = Query(...)):
    doc = get_document_details(doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")
    return get_chat_history(doc_id)
