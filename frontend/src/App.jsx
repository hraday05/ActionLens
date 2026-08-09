import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  FileText, Upload, Calendar, AlertTriangle, Trash2, Send, Plus,
  Search, LogOut, Loader2, Sparkles, MessageSquare, BookOpen,
  Clock, ShieldAlert, Check, User, ArrowRight, CheckSquare,
  Mail, KeyRound, RefreshCw, ChevronRight, BarChart3, ListTodo
} from 'lucide-react';
import confetti from 'canvas-confetti';

const API_BASE = "http://localhost:8000/api";
const TODAY = new Date();

// ─── Utility helpers ──────────────────────────────────────────

function getDeadlineBadge(dateStr) {
  if (!dateStr) return null;
  try {
    const target = new Date(dateStr);
    const today = new Date(TODAY.getFullYear(), TODAY.getMonth(), TODAY.getDate());
    const tgt   = new Date(target.getFullYear(), target.getMonth(), target.getDate());
    const diff  = Math.ceil((tgt - today) / 86400000);
    if (diff < 0)  return { text: `Overdue ${Math.abs(diff)}d`, cls: 'bg-red-500/20 text-red-400 border-red-500/30', urgency: 0 };
    if (diff === 0) return { text: 'Due Today!',  cls: 'bg-amber-500/20 text-amber-300 border-amber-400/40 animate-pulse-subtle', urgency: 1 };
    if (diff === 1) return { text: 'Tomorrow',    cls: 'bg-amber-400/15 text-amber-400 border-amber-400/25', urgency: 2 };
    if (diff <= 7)  return { text: `${diff}d left`, cls: 'bg-blue-500/20 text-blue-300 border-blue-500/25', urgency: 3 };
    return { text: `${diff}d left`, cls: 'bg-slate-700/60 text-slate-300 border-slate-600', urgency: 4 };
  } catch { return null; }
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return iso; }
}

function formatDateTime(date, time) {
  const d = formatDate(date);
  if (!time) return d;
  // Convert 24h to 12h
  try {
    const [h, m] = time.split(':').map(Number);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    return `${d} at ${h12}:${String(m).padStart(2,'0')} ${ampm}`;
  } catch { return d; }
}

const PRIORITY_META = {
  High:   { cls: 'bg-red-500/15 border-red-500/25 text-red-400',   dot: 'bg-red-400' },
  Medium: { cls: 'bg-blue-500/15 border-blue-500/25 text-blue-400', dot: 'bg-blue-400' },
  Low:    { cls: 'bg-slate-700/60 border-slate-600 text-slate-400', dot: 'bg-slate-500' },
};

// ─── Sub-components ───────────────────────────────────────────

function ProgressBar({ value, max }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800/40">
        <div className="bg-emerald-500 h-full rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[9px] font-bold text-emerald-400 tabular-nums">{pct}%</span>
    </div>
  );
}

function ConfidenceBadge({ level }) {
  const map = { High: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25', Medium: 'bg-amber-500/15 text-amber-400 border-amber-500/25', Low: 'bg-red-500/15 text-red-400 border-red-500/25' };
  return <span className={`text-[9px] font-bold px-2 py-0.5 rounded border ${map[level] || map.Medium}`}>{level} Confidence</span>;
}

// ─── Main App ─────────────────────────────────────────────────

export default function App() {
  // Auth state
  const [authStep, setAuthStep] = useState('login');   // 'login' | 'otp'
  const [pendingUser, setPendingUser] = useState(null); // {user_id, username, email}
  const [user, setUser] = useState(null);
  const [usernameInput, setUsernameInput] = useState('');
  const [emailInput, setEmailInput] = useState('');
  const [otpInput, setOtpInput] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  // App state
  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboard, setDashboard] = useState({ deadlines: [], pending_tasks: [] });

  // Upload state
  const [stagedFiles, setStagedFiles] = useState([]);
  const [pastedText, setPastedText] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');
  const [dragActive, setDragActive] = useState(false);

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const chatBottom = useRef(null);

  // Search
  const [search, setSearch] = useState('');

  // ── Persistence ──
  useEffect(() => {
    const saved = localStorage.getItem('actionlens_user');
    if (saved) { try { setUser(JSON.parse(saved)); } catch { localStorage.removeItem('actionlens_user'); } }
  }, []);

  useEffect(() => {
    if (user) { fetchDocuments(); fetchDashboard(); }
    else { setDocuments([]); setActiveDoc(null); setDashboard({ deadlines: [], pending_tasks: [] }); }
  }, [user]);

  useEffect(() => { chatBottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages, chatLoading]);

  // ── Cooldown timer for OTP resend ──
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setTimeout(() => setResendCooldown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  // ── Data fetchers ──
  const fetchDocuments = async () => {
    if (!user) return;
    try {
      const res = await fetch(`${API_BASE}/documents?user_id=${user.id}`);
      if (res.ok) setDocuments(await res.json());
    } catch {}
  };

  const fetchDashboard = async () => {
    if (!user) return;
    try {
      const res = await fetch(`${API_BASE}/dashboard/${user.id}`);
      if (res.ok) setDashboard(await res.json());
    } catch {}
  };

  const selectDocument = async (docId) => {
    if (!user) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}?user_id=${user.id}`);
      if (res.ok) {
        const data = await res.json();
        setActiveDoc(data);
        setActiveTab('overview');
        setChatMessages([]);
        fetchChatHistory(docId);
      }
    } catch {}
  };

  const fetchChatHistory = async (docId) => {
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}/chat?user_id=${user.id}`);
      if (res.ok) setChatMessages(await res.json());
    } catch {}
  };

  // ── Auth handlers ──
  const handleLogin = async (e) => {
    e.preventDefault();
    if (!usernameInput.trim() || !emailInput.trim()) return;
    setAuthLoading(true); setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usernameInput.trim(), email: emailInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setPendingUser(data);
        setAuthStep('otp');
        setResendCooldown(60);
      } else {
        setAuthError(data.detail || 'Login failed. Please try again.');
      }
    } catch {
      setAuthError('Cannot connect to backend. Make sure the FastAPI server is running on port 8000.');
    } finally { setAuthLoading(false); }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    if (!otpInput.trim() || !pendingUser) return;
    setAuthLoading(true); setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/verify-otp`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: pendingUser.user_id, otp: otpInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('actionlens_user', JSON.stringify(data));
        setUser(data);
        setAuthStep('login'); setOtpInput(''); setPendingUser(null);
      } else {
        setAuthError(data.detail || 'Invalid OTP. Please try again.');
      }
    } catch {
      setAuthError('Cannot connect to backend.');
    } finally { setAuthLoading(false); }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0 || !pendingUser) return;
    setAuthLoading(true); setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usernameInput.trim(), email: emailInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) { setPendingUser(data); setResendCooldown(60); setAuthError(''); }
      else setAuthError(data.detail || 'Resend failed.');
    } catch { setAuthError('Cannot connect to backend.'); }
    finally { setAuthLoading(false); }
  };

  const handleLogout = () => {
    localStorage.removeItem('actionlens_user');
    setUser(null); setActiveDoc(null); setStagedFiles([]); setPastedText('');
    setAuthStep('login'); setOtpInput(''); setPendingUser(null);
  };

  // ── Upload handlers ──
  const handleDrag = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(e.type !== 'dragleave'); };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation(); setDragActive(false);
    const valid = Array.from(e.dataTransfer.files).filter(f => /\.(pdf|png|jpg|jpeg|webp)$/i.test(f.name));
    setStagedFiles(p => [...p, ...valid]);
  };
  const handleFileSelect = (e) => { setStagedFiles(p => [...p, ...Array.from(e.target.files)]); };

  const handleAnalyze = async () => {
    if (!user || (stagedFiles.length === 0 && !pastedText.trim())) {
      setAnalyzeError('Stage at least one file or paste text.'); return;
    }
    setIsAnalyzing(true); setAnalyzeError('');
    const fd = new FormData();
    stagedFiles.forEach(f => fd.append('files', f));
    if (pastedText.trim()) fd.append('pasted_text', pastedText.trim());

    try {
      const res = await fetch(`${API_BASE}/analyze?user_id=${user.id}`, { method: 'POST', body: fd });
      if (res.ok) {
        const doc = await res.json();
        setStagedFiles([]); setPastedText(''); setShowPaste(false);
        await fetchDocuments(); await fetchDashboard();
        setActiveDoc(doc); setActiveTab('overview');
        triggerConfetti();
      } else {
        const err = await res.json();
        setAnalyzeError(err.detail || 'Analysis failed.');
      }
    } catch { setAnalyzeError('Network error. Check backend connection.'); }
    finally { setIsAnalyzing(false); }
  };

  // ── Task handlers ──
  const handleToggleTask = async (taskId, current) => {
    const next = !current;
    const updated = activeDoc.tasks.map(t => t.id === taskId ? { ...t, completed: next } : t);
    const allDone = updated.every(t => t.completed);
    setActiveDoc(p => ({ ...p, tasks: updated }));

    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/toggle?user_id=${user.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: next }),
      });
      if (res.ok) {
        fetchDocuments(); fetchDashboard();
        if (allDone && activeDoc.tasks.some(t => !t.completed)) triggerConfetti();
      } else {
        setActiveDoc(p => ({ ...p, tasks: p.tasks.map(t => t.id === taskId ? { ...t, completed: current } : t) }));
      }
    } catch {
      setActiveDoc(p => ({ ...p, tasks: p.tasks.map(t => t.id === taskId ? { ...t, completed: current } : t) }));
    }
  };

  // ── Delete document ──
  const handleDelete = async (e, docId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this document and all its tasks?')) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}?user_id=${user.id}`, { method: 'DELETE' });
      if (res.ok) { if (activeDoc?.id === docId) setActiveDoc(null); fetchDocuments(); fetchDashboard(); }
    } catch {}
  };

  // ── Chat ──
  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeDoc || chatLoading) return;
    const q = chatInput.trim(); setChatInput(''); setChatLoading(true);
    const temp = { id: `t-${Date.now()}`, role: 'user', content: q };
    setChatMessages(p => [...p, temp]);
    try {
      const res = await fetch(`${API_BASE}/chat?user_id=${user.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: activeDoc.id, question: q }),
      });
      if (res.ok) {
        const bot = await res.json();
        setChatMessages(p => [...p.filter(m => m.id !== temp.id), temp, bot]);
      } else {
        setChatMessages(p => [...p, { id: `e-${Date.now()}`, role: 'assistant', content: 'Error from backend. Check server logs.', evidence: '' }]);
      }
    } catch {
      setChatMessages(p => [...p, { id: `e-${Date.now()}`, role: 'assistant', content: 'Network error.', evidence: '' }]);
    } finally { setChatLoading(false); }
  };

  const triggerConfetti = () => confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 }, colors: ['#38bdf8','#34d399','#6366f1','#fbbf24'] });

  const filteredDocs = documents.filter(d => d.title.toLowerCase().includes(search.toLowerCase()) || d.summary.toLowerCase().includes(search.toLowerCase()));

  // ─────────────────────────────────────────────────────────────
  // LOGIN SCREEN
  // ─────────────────────────────────────────────────────────────
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4 relative overflow-hidden">
        <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-blue-600/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/3 right-1/4 w-96 h-96 bg-indigo-600/8 rounded-full blur-3xl pointer-events-none" />

        <div className="w-full max-w-md glass-panel rounded-2xl p-8 shadow-2xl animate-slide-up relative z-10">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex p-3 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white mb-4 shadow-lg shadow-blue-600/20">
              <Sparkles className="w-7 h-7" />
            </div>
            <h1 className="text-3xl font-black tracking-tight gradient-heading">ActionLens</h1>
            <p className="text-slate-400 text-xs mt-2 max-w-xs mx-auto leading-relaxed">
              "Doesn't just tell you what a document says — tells you what to do next."
            </p>
          </div>

          {/* ── Step 1: Login form ── */}
          {authStep === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">Username</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="text" placeholder="e.g. hraday"
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                    value={usernameInput} onChange={e => setUsernameInput(e.target.value)} disabled={authLoading}
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="email" placeholder="you@example.com"
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                    value={emailInput} onChange={e => setEmailInput(e.target.value)} disabled={authLoading}
                  />
                </div>
              </div>

              {authError && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 text-red-400 text-xs py-2.5 px-3 rounded-lg animate-fade-in">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /> <span>{authError}</span>
                </div>
              )}

              <button type="submit" disabled={authLoading || !usernameInput.trim() || !emailInput.trim()}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold py-3 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-600/15 group text-sm"
              >
                {authLoading ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Sending OTP...</span></> :
                  <><span>Continue with OTP</span><ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" /></>}
              </button>
            </form>
          )}

          {/* ── Step 2: OTP verification ── */}
          {authStep === 'otp' && pendingUser && (
            <div className="space-y-5 animate-fade-in">
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 text-center">
                <Mail className="w-6 h-6 text-blue-400 mx-auto mb-2" />
                <p className="text-xs text-slate-300 leading-relaxed">
                  A 6-digit OTP has been sent to <strong className="text-white">{pendingUser.email}</strong>
                </p>
                <p className="text-[10px] text-slate-500 mt-1">Check your inbox (or the server terminal if running locally)</p>
              </div>

              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">Enter OTP</label>
                  <div className="relative">
                    <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="text" placeholder="6-digit code" maxLength={6}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-xl py-3 pl-10 pr-4 text-xl text-center font-mono tracking-[0.4em] text-blue-300 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                      value={otpInput} onChange={e => setOtpInput(e.target.value.replace(/\D/g, ''))} disabled={authLoading}
                    />
                  </div>
                </div>

                {authError && (
                  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 text-red-400 text-xs py-2.5 px-3 rounded-lg animate-fade-in">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /> <span>{authError}</span>
                  </div>
                )}

                <button type="submit" disabled={authLoading || otpInput.length < 6}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold py-3 rounded-xl transition-all disabled:opacity-50 text-sm shadow-lg shadow-emerald-600/15"
                >
                  {authLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  <span>{authLoading ? 'Verifying...' : 'Verify & Sign In'}</span>
                </button>
              </form>

              <div className="flex items-center justify-between text-xs pt-1">
                <button onClick={() => { setAuthStep('login'); setAuthError(''); setOtpInput(''); }}
                  className="text-slate-500 hover:text-slate-300 transition-colors">← Back</button>
                <button onClick={handleResendOtp} disabled={resendCooldown > 0 || authLoading}
                  className="flex items-center gap-1 text-blue-400 hover:text-blue-300 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors">
                  <RefreshCw className="w-3 h-3" />
                  <span>{resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend OTP'}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // MAIN WORKSPACE
  // ─────────────────────────────────────────────────────────────
  const totalTasks = documents.reduce((s, d) => s + (d.total_tasks || 0), 0);
  const doneTasks  = documents.reduce((s, d) => s + (d.completed_tasks || 0), 0);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-950 text-slate-100">

      {/* ─────── SIDEBAR ─────── */}
      <aside className="w-full md:w-80 shrink-0 bg-slate-900/50 border-b md:border-b-0 md:border-r border-slate-800/80 flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setActiveDoc(null)}>
            <div className="p-2 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white shadow-md">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">ActionLens</h1>
              <p className="text-[9px] text-slate-500 font-medium">Document Action Planner</p>
            </div>
          </div>
          <button onClick={handleLogout} title="Sign out" className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Upload zone */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Upload Materials</span>

            <div
              onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}
              onClick={() => document.getElementById('fu').click()}
              className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all ${dragActive ? 'border-blue-500 bg-blue-500/5' : 'border-slate-800 hover:border-slate-700 hover:bg-slate-900/40'}`}
            >
              <input id="fu" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp" className="hidden" onChange={handleFileSelect} />
              <Upload className="w-7 h-7 text-slate-500 mx-auto mb-1.5" />
              <p className="text-xs font-medium text-slate-300">Drop files or browse</p>
              <p className="text-[10px] text-slate-600 mt-0.5">PDF · PNG · JPG · WEBP</p>
            </div>

            {!showPaste ? (
              <button onClick={() => setShowPaste(true)}
                className="w-full flex items-center justify-center gap-1.5 py-2 border border-slate-800 bg-slate-900/20 hover:bg-slate-900/60 text-xs font-medium rounded-xl text-slate-400 hover:text-white transition-all">
                <Plus className="w-3.5 h-3.5" /> Paste Text / Email / Chat
              </button>
            ) : (
              <div className="space-y-1.5 animate-fade-in">
                <textarea placeholder="Paste WhatsApp messages, emails, notifications..."
                  className="w-full h-24 bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                  value={pastedText} onChange={e => setPastedText(e.target.value)} />
                <button onClick={() => { setShowPaste(false); setPastedText(''); }} className="text-[10px] text-slate-500 hover:text-white">Cancel</button>
              </div>
            )}

            {stagedFiles.length > 0 && (
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-2.5 space-y-1.5 animate-fade-in">
                <div className="flex justify-between text-[9px] text-slate-500 font-bold uppercase tracking-wider px-0.5">
                  <span>Staged ({stagedFiles.length})</span>
                  <button onClick={() => setStagedFiles([])} className="hover:text-red-400">Clear</button>
                </div>
                <div className="max-h-20 overflow-y-auto space-y-1">
                  {stagedFiles.map((f, i) => (
                    <div key={i} className="flex justify-between items-center bg-slate-950 rounded-lg p-1.5 border border-slate-800/40">
                      <span className="text-[10px] text-slate-300 truncate max-w-[155px]">{f.name}</span>
                      <button onClick={() => setStagedFiles(p => p.filter((_, j) => j !== i))} className="text-slate-600 hover:text-red-400 p-0.5">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(stagedFiles.length > 0 || pastedText.trim()) && (
              <button onClick={handleAnalyze} disabled={isAnalyzing}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold py-2.5 rounded-xl text-xs shadow-md transition-all disabled:opacity-50">
                {isAnalyzing ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /><span>Analyzing...</span></> :
                  <><Sparkles className="w-3.5 h-3.5" /><span>Analyze Combined Source</span></>}
              </button>
            )}

            {analyzeError && (
              <div className="flex gap-1.5 items-start bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] py-2 px-2.5 rounded-lg">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" /><span>{analyzeError}</span>
              </div>
            )}
          </div>

          <div className="border-t border-slate-800/60" />

          {/* Document history */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">History</span>
              <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded-full">{documents.length}</span>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600 pointer-events-none" />
              <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>

            <div className="space-y-1.5 max-h-72 overflow-y-auto pr-0.5">
              {filteredDocs.length === 0 ? (
                <p className="text-center py-6 text-slate-600 text-xs italic">No documents yet.</p>
              ) : filteredDocs.map(doc => {
                const isActive = activeDoc?.id === doc.id;
                return (
                  <div key={doc.id} onClick={() => selectDocument(doc.id)}
                    className={`group w-full text-left rounded-xl p-3 border cursor-pointer transition-all flex flex-col gap-1.5 ${isActive ? 'bg-slate-800/70 border-blue-500/70 shadow-md' : 'bg-slate-900/30 border-slate-800/70 hover:bg-slate-900/60 hover:border-slate-700'}`}>
                    <div className="flex justify-between items-start gap-1">
                      <span className="font-semibold text-xs text-slate-200 group-hover:text-white flex-1 truncate">{doc.title}</span>
                      <button onClick={e => handleDelete(e, doc.id)} className="text-slate-600 hover:text-red-400 p-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <span className="text-[9px] text-slate-600">{formatDate(doc.created_at)}</span>
                    <ProgressBar value={doc.completed_tasks || 0} max={doc.total_tasks || 0} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* User footer */}
        <div className="p-4 border-t border-slate-800/80 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-sm text-blue-400">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="text-xs font-semibold text-slate-200 truncate">{user.username}</p>
            <p className="text-[9px] text-slate-600 truncate">{user.email}</p>
          </div>
        </div>
      </aside>

      {/* ─────── MAIN PANEL ─────── */}
      <main className="flex-1 overflow-y-auto p-6 max-h-screen">

        {/* ════════ HOME DASHBOARD (no doc selected) ════════ */}
        {!activeDoc && (
          <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
            <div>
              <h2 className="text-2xl font-black tracking-tight">
                Welcome, <span className="gradient-heading">{user.username}</span>
              </h2>
              <p className="text-slate-500 text-sm mt-1">Your unified action dashboard — all deadlines and tasks in one place.</p>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {[
                { icon: <FileText className="w-5 h-5" />, label: 'Documents', value: documents.length, color: 'text-blue-400 bg-blue-500/10' },
                { icon: <Check className="w-5 h-5" />, label: 'Tasks Done', value: `${doneTasks}/${totalTasks}`, color: 'text-emerald-400 bg-emerald-500/10' },
                { icon: <AlertTriangle className="w-5 h-5" />, label: 'Pending High-Priority', value: dashboard.pending_tasks.filter(t => t.priority === 'High').length, color: 'text-red-400 bg-red-500/10' },
              ].map(({ icon, label, value, color }) => (
                <div key={label} className="glass-panel p-5 rounded-2xl border border-slate-800/60 flex items-center gap-4 shadow-lg">
                  <div className={`p-3 rounded-xl ${color}`}>{icon}</div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
                    <p className="text-2xl font-black text-slate-100">{value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Deadlines + Priority Tasks */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* ── ALL DEADLINES across all documents ── */}
              <div className="glass-panel rounded-2xl border border-slate-800/80 p-5 shadow-xl flex flex-col">
                <div className="flex items-center gap-2 border-b border-slate-800/60 pb-3 mb-4">
                  <Calendar className="w-4 h-4 text-blue-400" />
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">All Deadlines</h3>
                  <span className="ml-auto text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded-full">{dashboard.deadlines.length}</span>
                </div>

                <div className="flex-1 space-y-2.5 overflow-y-auto max-h-80 pr-0.5">
                  {dashboard.deadlines.length === 0 ? (
                    <div className="py-10 text-center text-slate-600 text-xs italic">
                      Analyze a document to see deadlines here.
                    </div>
                  ) : dashboard.deadlines.map((dl, i) => {
                    const badge = getDeadlineBadge(dl.date);
                    return (
                      <div key={i} onClick={() => selectDocument(dl.doc_id)}
                        className="bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-slate-700 rounded-xl p-3 cursor-pointer transition-all flex justify-between items-start gap-2">
                        <div className="space-y-0.5 min-w-0">
                          <p className="text-xs font-semibold text-slate-200 truncate">{dl.label}</p>
                          <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                            <span className="truncate max-w-[110px]">{dl.doc_title}</span>
                            <span>·</span>
                            <span className="font-medium text-slate-400">{formatDateTime(dl.date, dl.time)}</span>
                          </div>
                          {dl.explanation && <p className="text-[9px] text-slate-600 leading-relaxed line-clamp-1">{dl.explanation}</p>}
                        </div>
                        {badge && (
                          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${badge.cls}`}>{badge.text}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* ── ALL PRIORITY TASKS across all documents ── */}
              <div className="glass-panel rounded-2xl border border-slate-800/80 p-5 shadow-xl flex flex-col">
                <div className="flex items-center gap-2 border-b border-slate-800/60 pb-3 mb-4">
                  <ListTodo className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">Priority Task Queue</h3>
                  <span className="ml-auto text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded-full">{dashboard.pending_tasks.length}</span>
                </div>

                <div className="flex-1 space-y-2 overflow-y-auto max-h-80 pr-0.5">
                  {dashboard.pending_tasks.length === 0 ? (
                    <div className="py-10 text-center text-slate-600 text-xs italic">
                      No pending tasks. Upload a document to get started!
                    </div>
                  ) : dashboard.pending_tasks.map((task, i) => {
                    const pm = PRIORITY_META[task.priority] || PRIORITY_META.Low;
                    return (
                      <div key={task.id || i} onClick={() => selectDocument(task.doc_id)}
                        className="bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-slate-700 rounded-xl p-3 cursor-pointer transition-all flex items-start gap-3">
                        <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${pm.dot}`} />
                        <div className="min-w-0 flex-1 space-y-1">
                          <p className="text-xs font-semibold text-slate-200 leading-relaxed line-clamp-2">{task.task_text}</p>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${pm.cls}`}>{task.priority}</span>
                            <span className="text-[9px] text-slate-600 truncate max-w-[120px]">{task.doc_title}</span>
                            {task.days_to_complete > 0 && (
                              <span className="text-[9px] text-slate-600 flex items-center gap-0.5">
                                <Clock className="w-3 h-3" />{task.days_to_complete}d
                              </span>
                            )}
                          </div>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-slate-700 shrink-0 mt-0.5" />
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          </div>
        )}

        {/* ════════ DOCUMENT WORKSPACE ════════ */}
        {activeDoc && (
          <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">

            {/* Workspace header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/80 pb-5">
              <div>
                <button onClick={() => setActiveDoc(null)} className="text-xs text-slate-500 hover:text-white mb-2 transition-colors">← Dashboard</button>
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-xl font-black text-slate-100">{activeDoc.title}</h2>
                  <ConfidenceBadge level={activeDoc.confidence_level} />
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5">Analyzed {formatDate(activeDoc.created_at)}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-slate-500">Progress</span>
                <div className="w-28">
                  <ProgressBar
                    value={activeDoc.tasks?.filter(t => t.completed).length || 0}
                    max={activeDoc.tasks?.length || 0}
                  />
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-0.5 border-b border-slate-800/80 pb-px">
              {[
                { id: 'overview',   icon: <BookOpen className="w-3.5 h-3.5" />,   label: 'Overview' },
                { id: 'checklist',  icon: <CheckSquare className="w-3.5 h-3.5" />, label: 'Action Plan' },
                { id: 'chat',       icon: <MessageSquare className="w-3.5 h-3.5" />, label: 'Ask AI' },
              ].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 pb-3 px-4 text-xs font-bold border-b-2 -mb-px transition-all ${activeTab === tab.id ? 'text-blue-400 border-blue-500' : 'text-slate-500 border-transparent hover:text-slate-300'}`}>
                  {tab.icon}<span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* ── OVERVIEW TAB ── */}
            {activeTab === 'overview' && (
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6 animate-fade-in">
                <div className="md:col-span-8 space-y-5">
                  {/* Summary */}
                  <div className="glass-panel p-5 rounded-2xl shadow-md space-y-2">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Summary</h3>
                    <p className="text-sm text-slate-300 leading-relaxed">{activeDoc.summary}</p>
                  </div>

                  {/* Warnings */}
                  {activeDoc.extracted_json?.warnings?.length > 0 && (
                    <div className="bg-red-500/8 border border-red-500/20 p-5 rounded-2xl space-y-3">
                      <div className="flex items-center gap-2 text-red-400">
                        <ShieldAlert className="w-4 h-4" />
                        <h3 className="text-[10px] font-bold uppercase tracking-widest">Warnings & Risks</h3>
                      </div>
                      <ul className="list-disc list-inside text-xs text-red-300/80 space-y-1.5 leading-relaxed">
                        {activeDoc.extracted_json.warnings.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  )}

                  {/* Eligibility + Required docs grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    {[
                      { title: 'Eligibility Criteria', items: activeDoc.extracted_json?.eligibility, icon: '•', iconCls: 'text-blue-400' },
                      { title: 'Required Documents', items: activeDoc.extracted_json?.required_documents, icon: <Check className="w-3 h-3" />, iconCls: 'text-emerald-400' },
                    ].map(({ title, items, icon, iconCls }) => (
                      <div key={title} className="glass-panel p-5 rounded-2xl shadow-md space-y-3">
                        <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{title}</h3>
                        {items?.length > 0 ? (
                          <ul className="space-y-2 text-xs text-slate-300">
                            {items.map((x, i) => (
                              <li key={i} className={`flex items-start gap-2 leading-relaxed ${iconCls}`}>
                                <span className="mt-0.5 shrink-0">{icon}</span><span className="text-slate-300">{x}</span>
                              </li>
                            ))}
                          </ul>
                        ) : <p className="text-xs text-slate-600 italic">None listed.</p>}
                      </div>
                    ))}
                  </div>

                  {/* Steps */}
                  {activeDoc.extracted_json?.steps?.length > 0 && (
                    <div className="glass-panel p-5 rounded-2xl shadow-md space-y-3">
                      <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Workflow Steps</h3>
                      <div className="space-y-3">
                        {activeDoc.extracted_json.steps.map((s, i) => (
                          <div key={i} className="flex gap-3 items-start">
                            <div className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 text-blue-400 font-bold text-[10px] flex items-center justify-center shrink-0">{i + 1}</div>
                            <p className="text-xs text-slate-300 leading-relaxed pt-0.5">{s}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Right: Deadlines column */}
                <div className="md:col-span-4 space-y-5">
                  <div className="glass-panel p-5 rounded-2xl shadow-md space-y-4">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Key Deadlines</h3>
                    {activeDoc.extracted_json?.dates?.length > 0 ? (
                      <div className="space-y-3">
                        {activeDoc.extracted_json.dates.map((d, i) => {
                          const badge = getDeadlineBadge(d.date);
                          return (
                            <div key={i} className="bg-slate-950/60 rounded-xl p-3 border border-slate-800/80 space-y-1.5">
                              <div className="flex justify-between items-start gap-2">
                                <span className="text-xs font-semibold text-slate-200">{d.label}</span>
                                {badge && <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${badge.cls}`}>{badge.text}</span>}
                              </div>
                              <p className="text-[10px] font-medium text-slate-400">{formatDateTime(d.date, d.time)}</p>
                              {d.explanation && <p className="text-[10px] text-slate-600 leading-relaxed">{d.explanation}</p>}
                            </div>
                          );
                        })}
                      </div>
                    ) : <p className="text-xs text-slate-600 italic">No deadlines found.</p>}
                  </div>

                  <div className="glass-panel p-4 rounded-xl text-xs space-y-1.5">
                    <div className="flex justify-between text-slate-500 font-medium">
                      <span>Analysis Confidence</span>
                      <span className={activeDoc.confidence_level === 'High' ? 'text-emerald-400' : 'text-amber-400'}>{activeDoc.confidence_level}</span>
                    </div>
                    <p className="text-[10px] text-slate-600 leading-relaxed">{activeDoc.confidence_explanation}</p>
                  </div>
                </div>
              </div>
            )}

            {/* ── CHECKLIST TAB ── */}
            {activeTab === 'checklist' && (
              <div className="glass-panel rounded-2xl border border-slate-800/80 p-5 space-y-4 shadow-xl animate-fade-in">
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-3">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">Action Plan Checklist</h3>
                    <p className="text-[10px] text-slate-600 mt-0.5">Click a task to toggle completion. Sorted High → Medium → Low.</p>
                  </div>
                  <button onClick={triggerConfetti} title="Celebrate!" className="p-1.5 text-slate-600 hover:text-yellow-400 bg-slate-900 border border-slate-800 rounded-xl transition-all">
                    <Sparkles className="w-3.5 h-3.5" />
                  </button>
                </div>

                {activeDoc.tasks?.length === 0 ? (
                  <p className="text-center py-12 text-slate-600 text-xs italic">No tasks extracted.</p>
                ) : (
                  <div className="space-y-2.5">
                    {[...activeDoc.tasks]
                      .sort((a, b) => ({ High: 3, Medium: 2, Low: 1 }[b.priority] - { High: 3, Medium: 2, Low: 1 }[a.priority]))
                      .map(task => {
                        const pm = PRIORITY_META[task.priority] || PRIORITY_META.Low;
                        return (
                          <div key={task.id} onClick={() => handleToggleTask(task.id, task.completed)}
                            className={`flex items-start gap-3.5 p-3.5 rounded-xl border cursor-pointer transition-all ${task.completed ? 'bg-emerald-950/10 border-emerald-900/30 hover:bg-emerald-950/15' : 'bg-slate-950/40 border-slate-800/70 hover:bg-slate-900/40 hover:border-slate-700'}`}>
                            <div className="pt-0.5 shrink-0">
                              {task.completed
                                ? <div className="w-5 h-5 rounded-md bg-emerald-500 flex items-center justify-center"><Check className="w-3.5 h-3.5 text-slate-950 stroke-[3]" /></div>
                                : <div className="w-5 h-5 rounded-md border-2 border-slate-700 hover:border-blue-500 transition-colors" />}
                            </div>
                            <div className="flex-1 space-y-1.5 min-w-0">
                              <p className={`text-xs font-semibold leading-relaxed ${task.completed ? 'line-through text-slate-600' : 'text-slate-200'}`}>{task.task_text}</p>
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${pm.cls}`}>{task.priority}</span>
                                {task.days_to_complete > 0 && (
                                  <span className="text-[9px] text-slate-600 flex items-center gap-1"><Clock className="w-3 h-3" />{task.days_to_complete}d</span>
                                )}
                                {task.dependencies?.length > 0 && (
                                  <span className="text-[9px] text-slate-600">Needs: {task.dependencies.map((d, i) => (
                                    <span key={i} className="bg-slate-900 border border-slate-800 rounded px-1 py-0.5 ml-1 text-slate-500">{d.slice(0, 25)}{d.length > 25 ? '…' : ''}</span>
                                  ))}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            )}

            {/* ── CHAT TAB ── */}
            {activeTab === 'chat' && (
              <div className="glass-panel rounded-2xl border border-slate-800/80 p-5 flex flex-col shadow-xl animate-fade-in" style={{ height: '550px' }}>
                <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 mb-4 flex items-start gap-2 shrink-0">
                  <ShieldAlert className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <p className="text-[10px] text-slate-400 leading-relaxed">
                    <strong className="text-slate-300">Strict Mode:</strong> Answers come only from the uploaded document. Every response includes a collapsible source quote.
                  </p>
                </div>

                {/* Chat thread */}
                <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                  {chatMessages.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-center gap-2 text-slate-600 py-10">
                      <MessageSquare className="w-8 h-8 opacity-30 text-blue-400" />
                      <p className="text-xs font-medium">Ask anything about this document</p>
                      <p className="text-[10px]">"What are the deadlines?" or "What documents do I need?"</p>
                    </div>
                  )}

                  {chatMessages.map(msg => {
                    const isUser = msg.role === 'user';
                    return (
                      <div key={msg.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} gap-1.5`}>
                        <div className={`flex gap-2 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border shrink-0 ${isUser ? 'bg-slate-800 border-slate-700 text-blue-400' : 'bg-gradient-to-tr from-blue-600 to-indigo-500 border-indigo-600/25 text-white'}`}>
                            {isUser ? user.username.charAt(0).toUpperCase() : 'AI'}
                          </div>
                          <div className={`rounded-2xl px-4 py-2.5 text-xs leading-relaxed border ${isUser ? 'bg-slate-900 border-slate-800 text-slate-200 rounded-tr-none' : 'bg-slate-950/80 border-slate-800/80 text-slate-200 rounded-tl-none shadow-md'}`}>
                            {msg.content}
                          </div>
                        </div>
                        {!isUser && msg.evidence && (
                          <div className="ml-9 animate-fade-in">
                            <button onClick={() => setExpandedEvidence(p => ({ ...p, [msg.id]: !p[msg.id] }))}
                              className="text-[9px] font-bold text-slate-600 hover:text-blue-400 flex items-center gap-1 transition-colors">
                              <span>{expandedEvidence[msg.id] ? 'Hide' : 'Show'} Source Evidence</span>
                              <Plus className={`w-2.5 h-2.5 transition-transform ${expandedEvidence[msg.id] ? 'rotate-45' : ''}`} />
                            </button>
                            {expandedEvidence[msg.id] && (
                              <div className="mt-1.5 bg-slate-900/60 border border-slate-800/80 rounded-lg p-2.5 text-[10px] text-slate-400 italic leading-relaxed max-w-md">
                                "{msg.evidence}"
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {chatLoading && (
                    <div className="flex items-center gap-2 text-xs text-slate-600 ml-2">
                      <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                      <span>Reading document…</span>
                    </div>
                  )}
                  <div ref={chatBottom} />
                </div>

                {/* Input */}
                <form onSubmit={handleSendChat} className="flex gap-2 pt-3 border-t border-slate-800/80 shrink-0">
                  <input type="text" placeholder="Ask about this document…"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-transparent"
                    value={chatInput} onChange={e => setChatInput(e.target.value)} disabled={chatLoading} />
                  <button type="submit" disabled={chatLoading || !chatInput.trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white p-2.5 rounded-xl disabled:opacity-50 transition-colors">
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            )}

          </div>
        )}
      </main>
    </div>
  );
}
