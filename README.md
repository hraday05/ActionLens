# ActionLens 🔍
### *"ActionLens doesn't just tell you what a document says — it tells you what you need to do next."*

ActionLens is an AI-powered web application that transforms unstructured documents (PDFs, images, emails, WhatsApp messages) into a structured, prioritized **Action Dashboard** — with deadline countdowns, interactive checklists, and a strict evidence-backed document chatbot.

---

## ✨ Features

- **Multi-source Upload** — Drag & drop PDFs, images/screenshots, or paste text/emails/WhatsApp messages simultaneously
- **AI Structured Extraction** — Groq LLM extracts title, summary, dates + times, eligibility, required documents, steps, warnings, and confidence level
- **Priority Action Checklist** — Ordered tasks (High → Medium → Low) with dependency tracking, days-to-complete, and interactive completion toggle
- **Deadline Countdowns** — All key dates with time shown; color-coded urgency badges (Overdue / Today / Tomorrow / N days left)
- **Unified Priority Dashboard** — See ALL deadlines and pending tasks across ALL your documents on one screen
- **Ask ActionLens Chat** — Strict Q&A powered by Groq; every answer backed by a collapsible source quote from the original document
- **Email OTP Authentication** — Username + email login with a 6-digit OTP verification
- **Multi-user Session Isolation** — Each user's documents, tasks, and chats are fully separated in SQLite

---

## 🏗️ Architecture

```
DevengersHackathon/
├── backend/               # FastAPI Python backend
│   ├── main.py            # API routes
│   ├── database.py        # SQLite models and queries
│   ├── analyzer.py        # Groq LLM structured extraction + Q&A
│   ├── parser.py          # PDF (PyMuPDF) + Image (pytesseract OCR) text extraction
│   ├── email_otp.py       # OTP email sender via Gmail SMTP
│   └── test_backend.py    # Integration test suite
├── frontend/              # React + Vite + Tailwind CSS frontend
│   ├── src/
│   │   ├── App.jsx        # Main application component
│   │   └── index.css      # Tailwind + custom glassmorphism styles
│   ├── tailwind.config.js
│   └── postcss.config.js
├── .env                   # API keys and SMTP credentials (never commit this)
└── README.md
```

---

## ⚙️ Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- **Groq API Key** — free at [console.groq.com](https://console.groq.com)
- **Gmail App Password** (for OTP emails) — optional; OTP prints to terminal if not set

---

## 🚀 Setup from Scratch

### 1. Clone / Navigate to the Project

```bash
cd /path/to/DevengersHackathon
```

### 2. Create and Activate a Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install Python Backend Dependencies

```bash
pip install fastapi uvicorn pymupdf python-multipart pytesseract pillow python-dotenv groq
```

### 4. Install Tesseract OCR (for image/screenshot support)

```bash
# macOS (Homebrew)
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows — download installer from: https://github.com/UB-Mannheim/tesseract/wiki
```

### 5. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. Configure Environment Variables

Create or edit the `.env` file in the project root:

```env
# Required — Get free at https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# Optional — For OTP email delivery
# If not set, OTP will be printed to the server terminal for local testing
SMTP_EMAIL=your_gmail_address@gmail.com
SMTP_PASSWORD=your_16_char_gmail_app_password
```

#### Getting a Gmail App Password:
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**
3. Search for **"App passwords"** → Generate one for "Mail"
4. Paste the 16-character password as `SMTP_PASSWORD`

---

## ▶️ Running the Application

You need **two terminal windows** — one for the backend, one for the frontend.

### Terminal 1 — Start the FastAPI Backend

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at: `http://127.0.0.1:8000`  
Interactive API docs: `http://127.0.0.1:8000/docs`

### Terminal 2 — Start the React Frontend

```bash
cd frontend
npm run dev
```

The app will be available at: **`http://localhost:5173`**

---

## 🧪 Running Backend Tests

```bash
source .venv/bin/activate
python backend/test_backend.py
```

---

## 🔄 How to Use ActionLens

1. **Sign In** — Enter a username and email address. An OTP is sent to your email.
2. **Verify OTP** — Enter the 6-digit code from your email (or terminal if SMTP not configured).
3. **Upload Materials** — Drag & drop PDFs and images, or click "Paste Text" to enter emails/WhatsApp chats. You can stage multiple files at once.
4. **Analyze** — Click **"Analyze Combined Source"** and wait ~5 seconds for Groq to extract structured data.
5. **Review Dashboard** — See all deadlines across all your documents sorted by urgency on the home screen.
6. **Work the Checklist** — Go to the "Action Plan Checklist" tab and tick off tasks as you complete them.
7. **Ask Questions** — Use the "Ask ActionLens Chat" tab to query the document. Every answer shows a collapsible source quote.

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS v3, Lucide React |
| Backend | FastAPI, Uvicorn |
| LLM | Groq API (`llama-3.3-70b-versatile`) |
| PDF Extraction | PyMuPDF (`fitz`) |
| Image OCR | Tesseract + pytesseract |
| Database | SQLite (local, via Python `sqlite3`) |
| Email | Python `smtplib` + Gmail SMTP |

---

## 🔐 Security Notes

- API keys are **server-side only** — never exposed to the browser
- Uploaded files are saved temporarily and **deleted immediately** after text extraction
- OTP codes expire after **10 minutes**
- Each user's data is fully isolated by `user_id` in all database queries
