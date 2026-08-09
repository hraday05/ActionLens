import requests
import sqlite3
import os
import sys

API_BASE = "http://localhost:8000/api"
DB_PATH = os.path.join(os.path.dirname(__file__), "actionlens.db")

def get_otp_from_db(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, otp_code FROM users WHERE username = ?", (username.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row if row else (None, None)

def run_api_tests():
    print("🚀 Starting ActionLens HTTP API Endpoint Tests...")

    # 1. Test Login Endpoint
    print("\n👤 Testing POST /api/login...")
    payload = {
        "username": "api_test_user",
        "email": "actionlens8@gmail.com"
    }
    res = requests.post(f"{API_BASE}/login", json=payload)
    assert res.status_code == 200, f"Login failed: {res.text}"
    login_data = res.json()
    print("Response:", login_data)
    assert "user_id" in login_data
    
    user_id, otp = get_otp_from_db("api_test_user")
    assert otp is not None, "OTP not stored in database."
    print(f"✅ Login OK. User ID: {user_id}, OTP retrieved from DB: {otp}")

    # 2. Test OTP Verification Endpoint
    print("\n🔐 Testing POST /api/verify-otp...")
    verify_payload = {
        "user_id": user_id,
        "otp": otp
    }
    res = requests.post(f"{API_BASE}/verify-otp", json=verify_payload)
    assert res.status_code == 200, f"OTP verification failed: {res.text}"
    session_data = res.json()
    print("Response:", session_data)
    assert session_data["username"] == "api_test_user"
    assert session_data["email"] == "actionlens8@gmail.com"
    print("✅ OTP Verification OK. Session active.")

    # 3. Test Analyze Endpoint (Paste text)
    print("\n📄 Testing POST /api/analyze (Pasted text)...")
    doc_text = """
    APARTMENT RENTAL CONTRACT
    Premises: Unit 12B, 100 Pine St.
    Agreement between landlord John Doe and tenant api_test_user.
    Start date: October 1, 2026.
    Rent of $2000 is due by the 1st of every month at 9:00 AM.
    Security deposit of $2000 due by September 15, 2026 at 5:00 PM.
    Required documents: ID photocopy, employment letter.
    Warnings: Quiet hours start at 10:00 PM daily. Violation leads to a fine of $100.
    """
    analyze_data = {
        "pasted_text": doc_text
    }
    res = requests.post(f"{API_BASE}/analyze?user_id={user_id}", data=analyze_data)
    assert res.status_code == 200, f"Analysis failed: {res.text}"
    doc_details = res.json()
    print("Extracted Document Title:", doc_details["title"])
    print("Confidence Level:", doc_details["confidence_level"])
    doc_id = doc_details["id"]
    print(f"✅ Document Analysis & Storage OK. Doc ID: {doc_id}")

    # 4. Test Dashboard Endpoint
    print(f"\n📊 Testing GET /api/dashboard/{user_id}...")
    res = requests.get(f"{API_BASE}/dashboard/{user_id}")
    assert res.status_code == 200, f"Dashboard retrieval failed: {res.text}"
    dashboard_data = res.json()
    print(f"Found {len(dashboard_data['deadlines'])} deadlines and {len(dashboard_data['pending_tasks'])} pending tasks.")
    
    # Check if dates have times
    for dl in dashboard_data['deadlines']:
        print(f"Deadline: {dl['label']} on {dl['date']} at {dl['time']}")
        assert "time" in dl
        if "Security Deposit" in dl['label']:
            assert dl['time'] == "17:00", f"Expected time 17:00, got {dl['time']}"
            
    print("✅ Dashboard Aggregation & Time Extraction OK.")

    # 5. Test Chat Endpoint
    print("\n💬 Testing POST /api/chat...")
    chat_payload = {
        "document_id": doc_id,
        "question": "What happens if I violate quiet hours?"
    }
    res = requests.post(f"{API_BASE}/chat?user_id={user_id}", json=chat_payload)
    assert res.status_code == 200, f"Chat failed: {res.text}"
    chat_reply = res.json()
    print("AI Answer:", chat_reply["content"])
    print("Evidence Quote:", chat_reply["evidence"])
    assert "$100" in chat_reply["content"] or "fine" in chat_reply["content"].lower()
    assert "Quiet hours" in chat_reply["evidence"] or "fine of $100" in chat_reply["evidence"]
    print("✅ Chat Q&A & Evidence Citation OK.")

    # 6. Test Task Toggle
    print("\n☑️ Testing POST /api/tasks/{task_id}/toggle...")
    task_id = doc_details["tasks"][0]["id"]
    res = requests.post(f"{API_BASE}/tasks/{task_id}/toggle?user_id={user_id}", json={"completed": True})
    assert res.status_code == 200, f"Toggle task failed: {res.text}"
    
    # Reload document and verify
    res = requests.get(f"{API_BASE}/documents/{doc_id}?user_id={user_id}")
    updated_doc = res.json()
    assert updated_doc["tasks"][0]["completed"] is True
    print("✅ Task Toggle OK.")

    print("\n🎉 ALL HTTP API ROUTE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_api_tests()
