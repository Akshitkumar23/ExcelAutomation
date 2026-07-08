'use client';

import { useState, useRef, useEffect } from 'react';
import ChatMessage from '@/components/ChatMessage';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ id: string; type?: string }>;
}

interface Session {
  id: string;
  title: string;
  createdAt: string;
}

interface MappingRow {
  original: string;
  mapped_to: string;
  note: string;
}

interface SmartUploadResult {
  session_id: string;
  filename: string;
  row_count: number;
  column_count: number;
  rag_entries: number;
  auto_id_generated: boolean;
  auto_id_message: string;
  mapping_summary: MappingRow[];
  unmapped_columns: string[];
  preview: Record<string, any>[];
  message: string;
}

const QUICK_QUESTIONS = [
  'Show project status overview',
  'Which projects are delayed?',
  'Give me a budget summary',
  'Projects in Noida',
  'Tell me about P1001',
  'Show completed projects',
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function generateId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([
    { id: 'default-session-id', title: 'New Conversation', createdAt: 'Just now' },
  ]);
  const [activeSession, setActiveSession] = useState<string>('default-session-id');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [workspaceFile, setWorkspaceFile] = useState<{ fileName: string; projectCount: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [smartUploadResult, setSmartUploadResult] = useState<SmartUploadResult | null>(null);
  const [showMappingModal, setShowMappingModal] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch workspace status when active session changes
  useEffect(() => {
    const fetchWorkspaceStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/chat/workspace/${activeSession}`);
        if (res.ok) {
          const data = await res.json();
          if (data.has_workspace) {
            setWorkspaceFile({
              fileName: data.file_name,
              projectCount: data.project_count,
            });
          } else {
            setWorkspaceFile(null);
          }
        }
      } catch (err) {
        console.error('Failed to fetch workspace status:', err);
      }
    };
    fetchWorkspaceStatus();
  }, [activeSession]);

  // Load sessions from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('buildflow_chat_sessions');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) {
          setSessions(parsed);
          setActiveSession(parsed[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    }
  }, []);

  // Save sessions to localStorage when they change
  useEffect(() => {
    localStorage.setItem('buildflow_chat_sessions', JSON.stringify(sessions));
  }, [sessions]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file) {
      await uploadWorkspaceFile(file);
    }
  };

  const uploadWorkspaceFile = async (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv', '.xlsx', '.xls'].includes(ext)) {
      alert('Sirf .csv, .xlsx ya .xls files allowed hain.');
      return;
    }

    setIsLoading(true);
    setUploadProgress('📤 File upload ho rahi hai...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', activeSession);

    try {
      setUploadProgress('🤖 Gemini columns detect kar raha hai...');
      const res = await fetch(`${API_URL}/api/smart-upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data: SmartUploadResult = await res.json();
      setSmartUploadResult(data);
      setShowMappingModal(true);

      // Update session to use the returned session_id
      if (data.session_id && data.session_id !== activeSession) {
        setActiveSession(data.session_id);
        setSessions(prev => prev.map(s =>
          s.id === activeSession ? { ...s, id: data.session_id } : s
        ));
      }

      setWorkspaceFile({
        fileName: file.name,
        projectCount: data.row_count,
      });

      // Add assistant message
      const autoIdNote = data.auto_id_generated
        ? `\n\n> ⚠️ **ID column nahi mila** — Auto-generated IDs (ROW_001, ROW_002...) assign kiye gaye hain.`
        : '';

      const unmappedNote = data.unmapped_columns.length > 0
        ? `\n\n> ℹ️ **${data.unmapped_columns.length} column(s) recognize nahi hue** (${data.unmapped_columns.join(', ')}) — lekin ye bhi AI search mein available hain.`
        : '';

      const systemMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: `📁 **Smart File Upload Complete!**\n\n✅ File **${file.name}** successfully load ho gayi.\n- **${data.row_count} rows** detected\n- **${data.rag_entries} entries** AI memory mein indexed${autoIdNote}${unmappedNote}\n\nAb aap is file ke baare mein kuch bhi pooch sakte hain!`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, systemMsg]);

    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsLoading(false);
      setUploadProgress('');
    }
  };

  const deleteWorkspace = async () => {
    if (!confirm('Are you sure you want to delete this custom workspace file?')) return;
    
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chat/workspace/${activeSession}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setWorkspaceFile(null);
        const systemMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: `🗑️ **Workspace Deactivated**\n\nRemoved custom projects file. Switched back to the default database.`,
          timestamp: new Date().toLocaleTimeString(),
        };
        setMessages((prev) => [...prev, systemMsg]);
      } else {
        throw new Error('Failed to delete workspace.');
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSpeechRecognition = () => {
    if (typeof window === 'undefined') return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice speech recognition is not supported in this browser. Please use Google Chrome.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-IN'; // Optimized for Indian English accent

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput((prev) => prev + (prev ? " " : "") + transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch (e) {
      console.error(e);
      setIsListening(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // Update session title
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSession && s.title === 'New Conversation'
          ? { ...s, title: text.slice(0, 30) + (text.length > 30 ? '…' : '') }
          : s
      )
    );

    try {
      const res = await fetch(`${API_URL}/api/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: activeSession }),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();

      const aiMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: data.response || 'No response received.',
        timestamp: new Date().toLocaleTimeString(),
        sources: data.sources,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content:
          '⚠️ **Connection Error**\n\nCould not reach the BuildFlow AI backend. Make sure the server is running at `http://localhost:8000`.\n\n**To start the backend:**\n```\ncd backend\npip install -r requirements.txt\nuvicorn main:app --reload\n```',
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const newSession = () => {
    const id = generateId();
    setSessions((prev) => [
      { id, title: 'New Conversation', createdAt: new Date().toLocaleTimeString() },
      ...prev,
    ]);
    setActiveSession(id);
    setMessages([]);
  };

  return (
    <div 
      className="chat-page" 
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{ position: 'relative' }}
    >
      {isDragging && (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(10, 14, 26, 0.92)',
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          border: '3px dashed var(--accent-blue)',
          margin: '10px',
          borderRadius: '16px',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
        }}>
          <div style={{ fontSize: '3.5rem', marginBottom: '12px', animation: 'bounce 1s infinite' }}>📥</div>
          <h3 style={{ color: 'var(--text-primary)', fontSize: '1.3rem', fontWeight: 700 }}>File Yahan Drop Karo!</h3>
          <p style={{ color: 'var(--accent-blue)', fontSize: '0.9rem', marginTop: '6px' }}>CSV · Excel (.xlsx) · XLS</p>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginTop: '4px' }}>AI automatically columns detect karega 🤖</p>
        </div>
      )}

      {/* Smart Upload Mapping Modal */}
      {showMappingModal && smartUploadResult && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          zIndex: 200,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem',
          backdropFilter: 'blur(6px)',
        }} onClick={() => setShowMappingModal(false)}>
          <div style={{
            background: 'linear-gradient(145deg, #0f172a, #1e293b)',
            border: '1px solid rgba(59,130,246,0.4)',
            borderRadius: '20px',
            padding: '2rem',
            maxWidth: '640px',
            width: '100%',
            maxHeight: '85vh',
            overflowY: 'auto',
            boxShadow: '0 25px 60px rgba(0,0,0,0.5), 0 0 40px rgba(59,130,246,0.1)',
          }} onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
              <div>
                <h2 style={{ color: '#f1f5f9', fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>🧠 AI Column Detection</h2>
                <p style={{ color: '#64748b', fontSize: '0.8rem', margin: '4px 0 0' }}>
                  {smartUploadResult.filename} · {smartUploadResult.row_count} rows · {smartUploadResult.column_count} columns
                </p>
              </div>
              <button onClick={() => setShowMappingModal(false)} style={{
                background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px', color: '#94a3b8', cursor: 'pointer', padding: '6px 12px', fontSize: '0.8rem',
              }}>✕ Close</button>
            </div>

            {/* Auto ID Warning */}
            {smartUploadResult.auto_id_generated && (
              <div style={{
                background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245,158,11,0.35)',
                borderRadius: '10px', padding: '12px 16px', marginBottom: '1rem',
                display: 'flex', alignItems: 'flex-start', gap: '10px',
              }}>
                <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                <div>
                  <div style={{ color: '#fbbf24', fontWeight: 600, fontSize: '0.85rem' }}>ID Column Nahi Mila</div>
                  <div style={{ color: '#d97706', fontSize: '0.78rem', marginTop: '2px' }}>
                    File mein koi unique ID column detect nahi hua. Auto-generated IDs assign kar diye: ROW_001, ROW_002...
                  </div>
                </div>
              </div>
            )}

            {/* Mapping Table */}
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>
                Column Mapping (Original → Standard)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {smartUploadResult.mapping_summary.map((row, i) => (
                  <div key={i} style={{
                    display: 'grid', gridTemplateColumns: '1fr auto 1fr',
                    alignItems: 'center', gap: '12px',
                    background: row.mapped_to.includes('⚠️') ? 'rgba(239,68,68,0.06)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${row.mapped_to.includes('⚠️') ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.07)'}`,
                    borderRadius: '8px', padding: '8px 12px',
                  }}>
                    <span style={{ color: '#e2e8f0', fontSize: '0.82rem', fontFamily: 'monospace' }}>{row.original}</span>
                    <span style={{ color: '#3b82f6', fontSize: '0.75rem' }}>→</span>
                    <span style={{
                      color: row.mapped_to.includes('⚠️') ? '#f87171' : '#34d399',
                      fontSize: '0.82rem', fontFamily: 'monospace'
                    }}>{row.mapped_to}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Preview */}
            {smartUploadResult.preview && smartUploadResult.preview.length > 0 && (
              <div>
                <div style={{ color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>
                  Data Preview (First 3 Rows)
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                    <thead>
                      <tr>
                        {Object.keys(smartUploadResult.preview[0]).slice(0, 5).map(col => (
                          <th key={col} style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', borderBottom: '1px solid rgba(255,255,255,0.1)', whiteSpace: 'nowrap' }}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {smartUploadResult.preview.map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).slice(0, 5).map((val: any, j) => (
                            <td key={j} style={{ padding: '6px 8px', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.05)', whiteSpace: 'nowrap', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {String(val ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Footer */}
            <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowMappingModal(false)} style={{
                background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
                border: 'none', borderRadius: '10px', color: 'white',
                padding: '10px 24px', cursor: 'pointer', fontWeight: 600, fontSize: '0.88rem',
              }}>✅ Theek Hai, Chat Shuru Karo!</button>
            </div>
          </div>
        </div>
      )}

      {/* Sessions Sidebar */}
      <aside className="chat-sessions">
        <div className="chat-sessions-header">
          <h3>Conversations</h3>
          <button className="btn-new-chat" onClick={newSession} id="new-chat-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Chat
          </button>
        </div>



        <div className="sessions-list">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`session-item ${activeSession === session.id ? 'active' : ''}`}
              onClick={() => setActiveSession(session.id)}
              id={`session-${session.id}`}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <div className="session-info">
                <span className="session-title">{session.title}</span>
                <span className="session-time">{session.createdAt}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="chat-main">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-info">
            <div className="chat-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="10" rx="2" />
                <circle cx="12" cy="5" r="2" />
                <path d="M12 7v4" />
                <line x1="8" y1="16" x2="8" y2="16" />
                <line x1="16" y1="16" x2="16" y2="16" />
              </svg>
            </div>
            <div>
              <h2>BuildFlow AI Assistant</h2>
              <p className="chat-status">
                <span className="status-dot online" />
                Online — RAG Powered
              </p>
            </div>
          </div>
          <div className="chat-header-actions">
            <span className="model-badge">Gemini + RAG</span>
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages" id="chat-messages" style={{ justifyContent: messages.length === 0 ? 'center' : 'flex-start' }}>
          {messages.length === 0 ? (
            <div style={{
              textAlign: 'center',
              maxWidth: '520px',
              margin: '0 auto',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '14px',
              animation: 'fadeIn 0.4s ease',
            }}>
              {/* Clean AI Logo Icon */}
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '18px',
                background: 'var(--gradient-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--shadow-glow-blue)',
                marginBottom: '8px',
              }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="10" rx="2" />
                  <circle cx="12" cy="5" r="2" />
                  <path d="M12 7v4" />
                </svg>
              </div>
              <h2 style={{ fontSize: '1.45rem', fontWeight: '800', color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
                BuildFlow AI Assistant
              </h2>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.6' }}>
                Ask me about project status, budgets, delays, site engineer info, or locations. How can I help you today?
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <ChatMessage key={msg.id} role={msg.role} content={msg.content} timestamp={msg.timestamp} />
            ))
          )}
          {isLoading && (
            <div className="typing-indicator">
              <div className="chat-avatar-sm">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="10" rx="2" />
                  <circle cx="12" cy="5" r="2" />
                </svg>
              </div>
              <div className="typing-dots">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {workspaceFile && (
          <div style={{
            margin: '0 1.5rem 10px',
            padding: '10px 16px',
            background: 'linear-gradient(135deg, rgba(59,130,246,0.12), rgba(6,182,212,0.08))',
            border: '1px solid rgba(59,130,246,0.35)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: '1.3rem', flexShrink: 0 }}>🧠</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f1f5f9' }}>
                  Smart Workspace Active
                  {smartUploadResult?.auto_id_generated && (
                    <span style={{ marginLeft: '6px', background: 'rgba(245,158,11,0.2)', color: '#fbbf24', fontSize: '0.68rem', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>AUTO-ID</span>
                  )}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {workspaceFile.fileName} · {workspaceFile.projectCount} rows
                  {smartUploadResult && smartUploadResult.unmapped_columns.length > 0 && (
                    <span style={{ marginLeft: '6px', color: '#f87171' }}>· {smartUploadResult.unmapped_columns.length} unrecognized col(s)</span>
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
              {smartUploadResult && (
                <button onClick={() => setShowMappingModal(true)} style={{
                  background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
                  color: '#60a5fa', padding: '4px 10px', borderRadius: '6px',
                  fontSize: '0.72rem', cursor: 'pointer', fontWeight: 600,
                }}>🗺️ Mapping</button>
              )}
              <button onClick={deleteWorkspace} style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                color: '#f87171', padding: '4px 10px', borderRadius: '6px',
                fontSize: '0.72rem', cursor: 'pointer',
              }}>🗑️</button>
            </div>
          </div>
        )}

        {/* Upload progress indicator */}
        {uploadProgress && (
          <div style={{
            margin: '0 1.5rem 6px',
            padding: '8px 14px',
            background: 'rgba(6,182,212,0.1)',
            border: '1px solid rgba(6,182,212,0.25)',
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: '#06b6d4',
            animation: 'pulse 1.2s infinite',
          }}>{uploadProgress}</div>
        )}



        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <button
              className="upload-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Upload CSV or Excel projects file to this session"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '4px',
                marginRight: '4px',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".csv,.xlsx,.xls"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadWorkspaceFile(file);
              }}
            />
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder={workspaceFile ? `'${workspaceFile.fileName}' ke baare mein poochho...` : 'Ask about project status, budgets, delays, or drop a file to upload...'}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              id="chat-input"
            />
            <button
              className={`mic-btn ${isListening ? 'listening' : ''}`}
              onClick={toggleSpeechRecognition}
              title="Voice Input (Speech-to-Text)"
              style={{
                background: isListening ? '#ef4444' : 'rgba(255,255,255,0.05)',
                border: 'none',
                borderRadius: '10px',
                width: '38px',
                height: '38px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                cursor: 'pointer',
                transition: 'all 0.2s',
                marginRight: '4px',
                boxShadow: isListening ? '0 0 10px #ef4444' : 'none',
              }}
              id="mic-btn"
            >
              {isListening ? (
                <div
                  className="mic-pulse-dot"
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    background: 'white',
                    animation: 'pulse 1s infinite alternate',
                  }}
                />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="19" x2="16" y2="19" />
                </svg>
              )}
            </button>
            <button
              className="send-btn"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading}
              id="send-btn"
            >
              {isLoading ? (
                <div className="spinner-sm" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .chat-page {
          display: flex;
          height: calc(100vh - 0px);
          overflow: hidden;
        }
        .chat-sessions {
          width: 280px;
          min-width: 280px;
          background: rgba(10, 14, 26, 0.45);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .chat-sessions-header {
          padding: 1.5rem;
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .chat-sessions-header h3 {
          color: var(--text-primary);
          font-size: 0.95rem;
          font-weight: 600;
        }
        .btn-new-chat {
          display: flex;
          align-items: center;
          gap: 6px;
          background: var(--accent-blue);
          color: white;
          border: none;
          border-radius: 8px;
          padding: 6px 12px;
          font-size: 0.78rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .btn-new-chat:hover { background: #2563eb; transform: translateY(-1px); }
        .data-sources {
          padding: 1rem 1.5rem;
          border-bottom: 1px solid var(--border);
        }
        .sources-label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--text-secondary);
          margin-bottom: 0.5rem;
        }
        .source-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.8rem;
          color: var(--text-secondary);
          padding: 3px 0;
        }
        .source-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: var(--accent-green);
          box-shadow: 0 0 6px var(--accent-green);
        }
        .sessions-list {
          flex: 1;
          overflow-y: auto;
          padding: 0.75rem;
        }
        .session-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 10px 12px;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.15s;
          margin-bottom: 4px;
          color: var(--text-secondary);
        }
        .session-item:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }
        .session-item.active { background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); color: var(--text-primary); }
        .session-info { flex: 1; min-width: 0; }
        .session-title { display: block; font-size: 0.82rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .session-time { display: block; font-size: 0.7rem; color: var(--text-secondary); margin-top: 2px; }
        .chat-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-width: 0;
          background: var(--bg-deep-navy);
        }
        .chat-header {
          padding: 1.25rem 1.5rem;
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(17, 24, 39, 0.5);
          backdrop-filter: blur(10px);
        }
        .chat-header-info { display: flex; align-items: center; gap: 1rem; }
        .chat-avatar {
          width: 42px; height: 42px;
          background: linear-gradient(135deg, #3b82f6, #06b6d4);
          border-radius: 12px;
          display: flex; align-items: center; justify-content: center;
          color: white;
        }
        .chat-header-info h2 { font-size: 1rem; font-weight: 600; margin: 0; color: var(--text-primary); }
        .chat-status { font-size: 0.75rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; margin: 0; }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; }
        .status-dot.online { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
        .model-badge {
          background: rgba(59,130,246,0.15);
          border: 1px solid rgba(59,130,246,0.3);
          color: var(--accent-blue);
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 0.75rem;
          font-weight: 600;
        }
        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 0;
        }
        .typing-indicator {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 0.75rem 0;
        }
        .chat-avatar-sm {
          width: 30px; height: 30px;
          background: linear-gradient(135deg, #3b82f6, #06b6d4);
          border-radius: 8px;
          display: flex; align-items: center; justify-content: center;
          color: white;
          flex-shrink: 0;
        }
        .typing-dots {
          display: flex;
          gap: 4px;
          background: rgba(255,255,255,0.05);
          border: 1px solid var(--border);
          padding: 10px 14px;
          border-radius: 12px;
        }
        .typing-dots span {
          width: 7px; height: 7px;
          background: var(--text-secondary);
          border-radius: 50%;
          animation: bounce 1.2s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        .chat-input-area {
          padding: 1.25rem 1.5rem;
          border-top: 1px solid var(--border);
          background: rgba(17,24,39,0.35);
        }
        .chat-input-wrapper {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          background: rgba(255,255,255,0.04);
          border: 1px solid var(--border);
          border-radius: 24px;
          padding: 0.5rem 0.6rem 0.5rem 1.25rem;
          transition: all 0.2s;
        }
        .chat-input-wrapper:focus-within {
          border-color: var(--accent-blue);
          background: rgba(255,255,255,0.06);
          box-shadow: 0 0 15px rgba(59, 130, 246, 0.15);
        }
        .chat-textarea {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: var(--text-primary);
          font-size: 0.9rem;
          font-family: inherit;
          resize: none;
          max-height: 120px;
          line-height: 1.5;
        }
        .chat-textarea::placeholder { color: var(--text-secondary); }
        .send-btn {
          width: 36px; height: 36px;
          background: var(--accent-blue);
          border: none;
          border-radius: 50%;
          color: white;
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.2s;
          flex-shrink: 0;
        }
        .send-btn:hover:not(:disabled) { background: #2563eb; transform: scale(1.05); }
        .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .spinner-sm {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
