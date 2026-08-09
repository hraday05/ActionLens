import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables or .env file.")
    return Groq(api_key=api_key)

def analyze_document_text(text: str) -> dict:
    """
    Sends extracted document text to Groq LLM to extract structured
    action dashboard data including dates WITH times.
    """
    client = get_groq_client()

    system_prompt = """You are a document action analyzer. Extract structured dashboard metadata from the provided text.
Return ONLY a raw JSON object with this exact schema — no markdown, no explanation:

{
  "title": "Short descriptive document title",
  "summary": "2-3 sentence summary of what the document covers and what is required",
  "dates": [
    {
      "label": "Descriptive name of deadline or event (e.g. 'Security Deposit Due', 'Interview Slot')",
      "date": "YYYY-MM-DD (if year is missing assume 2026; omit this entry if no date mentioned)",
      "time": "HH:MM in 24-hour format (e.g. '14:30' for 2:30 PM). Use null if no time is specified.",
      "explanation": "Context or consequence for this date"
    }
  ],
  "eligibility": ["Criterion 1", "Criterion 2"],
  "required_documents": ["Document name 1", "Document name 2"],
  "steps": ["Step 1", "Step 2"],
  "action_items": [
    {
      "task": "Clear specific action the user must take",
      "priority": "High|Medium|Low",
      "days_to_complete": 5,
      "dependencies": ["Exact task text this depends on (empty list if none)"]
    }
  ],
  "warnings": ["Critical risk, fine, penalty, or important warning. Empty list if none."],
  "confidence_level": "High|Medium|Low",
  "confidence_explanation": "Why this confidence level was chosen"
}

Priority assignment rules:
- High: Deadlines within 7 days, financial penalties, legal requirements, blocking tasks
- Medium: Deadlines within 30 days, prerequisite steps, important but not urgent
- Low: Background tasks, optional steps, far-future items

Time extraction rules:
- "by 5 PM" → "17:00"
- "at 9:30 AM" → "09:30"
- "before noon" → "12:00"
- "end of day" → "23:59"
- If no time mentioned → null
"""

    user_content = f"Analyze this document:\n\n{text}"

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4000,
        )
        raw_response = completion.choices[0].message.content
        parsed = json.loads(raw_response)
        return validate_and_clean_analysis(parsed)
    except Exception as e:
        print(f"Groq API or parsing error: {e}")
        return {
            "title": "Analysis Failed",
            "summary": f"Failed to analyze the document. Error: {str(e)}",
            "dates": [],
            "eligibility": [],
            "required_documents": [],
            "steps": [],
            "action_items": [],
            "warnings": ["An error occurred while calling the AI model. Check your internet connection and GROQ_API_KEY."],
            "confidence_level": "Low",
            "confidence_explanation": str(e)
        }

def validate_and_clean_analysis(data: dict) -> dict:
    """Validates and normalises the JSON output from the LLM."""
    cleaned = {}

    cleaned["title"] = str(data.get("title", "Untitled Document")).strip() or "Untitled Document"
    cleaned["summary"] = str(data.get("summary", "No summary provided.")).strip() or "No summary provided."

    # Dates — now includes optional time field
    cleaned["dates"] = []
    for d in data.get("dates", []):
        if isinstance(d, dict) and "label" in d and "date" in d:
            time_val = d.get("time")
            # Validate time format
            if time_val and isinstance(time_val, str):
                time_val = time_val.strip()
                # Ensure HH:MM format
                parts = time_val.split(":")
                if len(parts) != 2:
                    time_val = None
            else:
                time_val = None

            cleaned["dates"].append({
                "label": str(d.get("label", "")).strip(),
                "date": str(d.get("date", "")).strip(),
                "time": time_val,
                "explanation": str(d.get("explanation", "")).strip()
            })

    cleaned["eligibility"] = [str(x).strip() for x in data.get("eligibility", []) if str(x).strip()]
    cleaned["required_documents"] = [str(x).strip() for x in data.get("required_documents", []) if str(x).strip()]
    cleaned["steps"] = [str(x).strip() for x in data.get("steps", []) if str(x).strip()]
    cleaned["warnings"] = [str(x).strip() for x in data.get("warnings", []) if str(x).strip()]

    cleaned["action_items"] = []
    for item in data.get("action_items", []):
        if not isinstance(item, dict) or not item.get("task"):
            continue
        task_text = str(item["task"]).strip()
        if not task_text:
            continue

        priority = str(item.get("priority", "Medium")).capitalize()
        if priority not in ["High", "Medium", "Low"]:
            priority = "Medium"

        try:
            days = int(item.get("days_to_complete", 7))
        except (ValueError, TypeError):
            days = 7

        deps = item.get("dependencies", [])
        if not isinstance(deps, list):
            deps = []
        deps = [str(d).strip() for d in deps if str(d).strip()]

        cleaned["action_items"].append({
            "task": task_text,
            "priority": priority,
            "days_to_complete": days,
            "dependencies": deps
        })

    level = str(data.get("confidence_level", "Medium")).capitalize()
    if level not in ["High", "Medium", "Low"]:
        level = "Medium"
    cleaned["confidence_level"] = level
    cleaned["confidence_explanation"] = str(data.get("confidence_explanation", "")).strip() or "No explanation provided."

    return cleaned

def answer_chat_question(document_text: str, chat_history: list, question: str) -> tuple:
    """
    Answers a question strictly from document text.
    Returns: (answer_text, evidence_text)
    """
    client = get_groq_client()

    history_str = ""
    for msg in chat_history[-6:]:  # Last 6 messages for context
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_str += f"{role}: {msg.get('content', '')}\n"

    system_prompt = """You are a strict document Q&A assistant.
Answer ONLY from the provided document text. Do NOT use external knowledge.
If the answer is not in the document, reply exactly: "I'm sorry, but that information is not available in the uploaded document."

Return a raw JSON object (no markdown):
{
  "answer": "Your direct, concise answer. Use the fallback phrase above if not found.",
  "evidence": "The exact quote(s) from the document supporting your answer. Empty string if not found."
}"""

    user_content = f"""Document:
{document_text[:8000]}

Chat History:
{history_str}
Question: {question}"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1000,
        )
        parsed = json.loads(completion.choices[0].message.content)
        return parsed.get("answer", ""), parsed.get("evidence", "")
    except Exception as e:
        print(f"Chat QA error: {e}")
        return f"Error occurred during Q&A: {str(e)}", ""
