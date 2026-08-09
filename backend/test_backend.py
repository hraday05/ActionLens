import os
import sys
import json

# Add backend directory to system path
sys.path.append(os.path.dirname(__file__))

from database import (
    init_db,
    get_or_create_user,
    save_document,
    get_user_documents,
    get_document_details,
    toggle_task_completion,
    save_chat_message,
    get_chat_history
)
from analyzer import analyze_document_text, answer_chat_question, validate_and_clean_analysis

def run_tests():
    print("🚀 Starting ActionLens Integration Tests...")
    
    # 1. Initialize DB
    print("⚙️ Initializing SQLite Database...")
    init_db()
    print("✅ Database initialized successfully.")

    # 2. Test User Login
    print("\n👤 Testing User Creation/Login...")
    user = get_or_create_user("test_verifier")
    assert user is not None, "Failed to create user."
    assert user["username"] == "test_verifier", f"Expected 'test_verifier', got '{user['username']}'"
    print(f"✅ User Login OK: id={user['id']}, username={user['username']}")

    # 3. Test LLM Analysis Validation
    print("\n🔍 Testing LLM Analysis Schema Validation...")
    mock_llm_json = {
        "title": "Apartment Lease Agreement",
        "summary": "Lease for unit 4B at 123 Main St.",
        "dates": [
            {"label": "Move-In Date", "date": "2026-09-01", "explanation": "Start of lease lease terms"},
            {"label": "Monthly Rent Due", "date": "2026-09-05", "explanation": "Must be paid by the 5th"}
        ],
        "eligibility": ["Must have 3x rent income"],
        "required_documents": ["Paystubs", "ID"],
        "steps": ["Sign lease", "Pay security deposit"],
        "action_items": [
            {"task": "Pay security deposit", "priority": "High", "days_to_complete": 3, "dependencies": []},
            {"task": "Submit renter insurance", "priority": "Medium", "days_to_complete": 10, "dependencies": ["Pay security deposit"]}
        ],
        "warnings": ["Late fee of $50 if paid after the 5th"],
        "confidence_level": "High",
        "confidence_explanation": "Extracted cleanly from text."
    }
    
    cleaned = validate_and_clean_analysis(mock_llm_json)
    assert cleaned["title"] == "Apartment Lease Agreement"
    assert len(cleaned["dates"]) == 2
    assert len(cleaned["action_items"]) == 2
    assert cleaned["action_items"][1]["dependencies"] == ["Pay security deposit"]
    print("✅ Schema Validation OK.")

    # 4. Test Document & Task Insertion
    print("\n💾 Testing Database Insert & Retrieval...")
    doc_id = "test-doc-uuid"
    
    # Clean up if test doc exists
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    
    raw_text = "Lease Agreement for Unit 4B at 123 Main St. Start date is 2026-09-01. Rent is due by the 5th of each month. Renter must submit paystubs."
    
    save_document(
        user_id=user["id"],
        doc_id=doc_id,
        title=cleaned["title"],
        summary=cleaned["summary"],
        extracted_json=cleaned,
        raw_text=raw_text,
        confidence_level=cleaned["confidence_level"],
        confidence_explanation=cleaned["confidence_explanation"]
    )
    
    docs = get_user_documents(user["id"])
    found_doc = next((d for d in docs if d["id"] == doc_id), None)
    assert found_doc is not None, "Document was not saved/retrieved."
    assert found_doc["title"] == "Apartment Lease Agreement", f"Expected title 'Apartment Lease Agreement', got '{found_doc['title']}'"
    print("✅ Document Insert & History Listing OK.")
    
    # Check details and tasks
    details = get_document_details(doc_id, user["id"])
    assert details is not None, "Failed to load document details."
    assert len(details["tasks"]) == 2, f"Expected 2 tasks, got {len(details['tasks'])}"
    print("✅ Document Detailed Retrieval OK.")

    # 5. Test Checklist Task Toggle
    print("\n☑️ Testing Checklist Task Toggling...")
    task_to_toggle = details["tasks"][0]
    task_id = task_to_toggle["id"]
    initial_state = task_to_toggle["completed"]
    
    # Toggle to true
    success = toggle_task_completion(task_id, not initial_state, user["id"])
    assert success, "Failed to toggle task completion."
    
    updated_details = get_document_details(doc_id, user["id"])
    updated_task = next((t for t in updated_details["tasks"] if t["id"] == task_id), None)
    assert updated_task["completed"] == (not initial_state), "Task completed state did not update in DB."
    print("✅ Checklist Completion Toggling OK.")

    # 6. Test Chat Q&A Answering
    print("\n💬 Testing strict Chat Q&A logic...")
    history = []
    
    # Test valid question
    answer, evidence = answer_chat_question(raw_text, history, "When does the lease start?")
    print(f"Question: When does the lease start?")
    print(f"Answer: {answer}")
    print(f"Evidence: {evidence}")
    assert "2026-09-01" in answer or "september 1" in answer.lower(), "QA answer failed to extract start date."
    assert "2026-09-01" in evidence, "QA evidence is missing supporting quote."
    
    # Test out of context question
    answer_ooc, evidence_ooc = answer_chat_question(raw_text, history, "What is the capital of France?")
    print(f"Question: What is the capital of France?")
    print(f"Answer: {answer_ooc}")
    assert "French" not in answer_ooc and "Paris" not in answer_ooc, "QA failed to block external knowledge."
    assert "I'm sorry" in answer_ooc, "QA failed to return fallback answer for out-of-context question."
    print("✅ Strict Chat Q&A & Evidence Citations OK.")

    print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY! Backend pipeline is fully functional.")

if __name__ == "__main__":
    run_tests()
