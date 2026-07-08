'use client';

import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Project {
  id: string;
  name: string;
  location: string;
  budget: number;
  spent: number;
  status: string;
  progress: number;
  phase: string;
  labourCount: number;
  startDate: string;
}

interface OverviewData {
  total_projects: number;
  total_budget: number;
  total_spent: number;
  on_track_count: number;
  delayed_count: number;
  avg_progress: number;
  projects?: Project[];
}

function useCountUp(target: number, duration = 1200) {
  const [val, setVal] = useState(0);
  const raf = useRef<number>(0);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setVal(Math.round(target * ease));
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);
  return val;
}

function StatCard({ label, value, desc, accent, icon, delay = 0 }: {
  label: string; value: string | number; desc: string;
  accent: string; icon: React.ReactNode; delay?: number;
}) {
  const numVal = typeof value === 'number' ? value : parseInt(String(value).replace(/\D/g, '')) || 0;
  const animated = useCountUp(numVal);
  const display = typeof value === 'string' && value.includes('%')
    ? `${animated}%` : animated;

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: '16px',
      padding: '22px',
      position: 'relative',
      overflow: 'hidden',
      animation: `fadeUp 0.5s ${delay}ms both ease`,
      transition: 'transform 200ms ease, border-color 200ms ease, box-shadow 200ms ease',
      cursor: 'default',
    }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-4px)';
        (e.currentTarget as HTMLDivElement).style.borderColor = `${accent}44`;
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 16px 40px -12px rgba(0,0,0,0.7), 0 0 20px ${accent}22`;
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
        (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
      }}
    >
      {/* Top accent line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
        background: `linear-gradient(90deg, ${accent}, transparent)`,
      }} />

      {/* Subtle bg glow */}
      <div style={{
        position: 'absolute', top: '-40px', right: '-20px',
        width: '120px', height: '120px', borderRadius: '50%',
        background: `radial-gradient(circle, ${accent}18 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--t-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {label}
        </div>
        <div style={{
          width: '34px', height: '34px', borderRadius: '8px',
          background: `${accent}18`, color: accent,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: `1px solid ${accent}28`,
          flexShrink: 0,
        }}>
          {icon}
        </div>
      </div>

      <div style={{
        fontSize: '2.2rem', fontWeight: '900', color: 'var(--t-1)',
        letterSpacing: '-0.04em', lineHeight: 1, marginBottom: '6px',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {display}
      </div>
      <div style={{ fontSize: '0.73rem', color: 'var(--t-3)', fontWeight: '400' }}>{desc}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) await uploadFile(e.dataTransfer.files[0]);
  };

  const uploadFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext || '')) {
      setUploadStatus({ type: 'error', message: 'Unsupported format. Upload .xlsx, .xls, or .csv.' });
      return;
    }
    setUploading(true);
    setUploadStatus(null);
    const formData = new FormData();
    formData.append('file', file);
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    try {
      const res = await fetch(`${API_URL}/api/analytics/upload?session_id=${active}`, { method: 'POST', body: formData });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Upload failed');
      setUploadStatus({ type: 'success', message: result.message || 'Database loaded!' });
      const overviewRes = await fetch(`${API_URL}/api/analytics/overview?session_id=${active}`);
      if (overviewRes.ok) setData(await overviewRes.json());
    } catch (err: any) {
      setUploadStatus({ type: 'error', message: err.message || 'Backend connection failed.' });
    } finally { setUploading(false); }
  };

  useEffect(() => {
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    fetch(`${API_URL}/api/analytics/overview?session_id=${active}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const total     = data?.total_projects  ?? 50;
  const delayed   = data?.delayed_count   ?? 8;
  const onTrack   = data?.on_track_count  ?? 34;
  const progress  = data?.avg_progress    ?? 72;
  const budget    = data?.total_budget    ?? 0;
  const spent     = data?.total_spent     ?? 0;
  const projects  = data?.projects?.slice(0, 6) ?? [];

  const stats = [
    { label: 'Total Projects', value: total, desc: 'Active in database', accent: '#3b82f6', delay: 0,
      icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg> },
    { label: 'On Schedule', value: onTrack, desc: 'Projects on track', accent: '#10b981', delay: 80,
      icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-5"/></svg> },
    { label: 'Delayed', value: delayed, desc: 'Need attention', accent: '#ef4444', delay: 160,
      icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> },
    { label: 'Avg Progress', value: `${Math.round(progress)}%`, desc: 'Overall completion', accent: '#8b5cf6', delay: 240,
      icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> },
  ];

  const workspaceCards = [
    {
      href: '/chat', color: 'cyan', label: 'RAG Assistant',
      desc: 'Natural language Q&A over all project records. Query status, budgets, and risks instantly.',
      icon: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 10h8M8 14h5"/></svg>,
    },
    {
      href: '/docgen', color: 'purple', label: 'Document Generator',
      desc: 'Generate professional PDF contracts, work orders, site reports, and tax invoices.',
      icon: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
    },
    {
      href: '/agents', color: 'blue', label: 'Multi-Agent Pipeline',
      desc: 'Trigger sequential AI agents for planning, cost analysis, risk scoring, and notifications.',
      icon: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="5" r="3"/><circle cx="4" cy="19" r="3"/><circle cx="20" cy="19" r="3"/><path d="M12 8v4M7 17l-2.5-3.5M17 17l2.5-3.5"/></svg>,
    },
  ];

  return (
    <div className="page-container">

      {/* ── Hero ── */}
      <section style={{
        padding: '2.75rem 2.5rem',
        borderRadius: '20px',
        marginBottom: '1.75rem',
        background: 'linear-gradient(145deg, #0d1117 0%, #0a0d15 100%)',
        border: '1px solid rgba(255,255,255,0.07)',
        display: 'grid',
        gridTemplateColumns: '1.1fr 0.9fr',
        gap: '2.5rem',
        alignItems: 'center',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Background radial glows */}
        <div style={{
          position: 'absolute', top: '-60px', left: '20%',
          width: '400px', height: '300px',
          background: 'radial-gradient(ellipse, rgba(59,130,246,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: '-40px', right: '10%',
          width: '300px', height: '200px',
          background: 'radial-gradient(ellipse, rgba(6,182,212,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Content */}
        <div style={{ position: 'relative', animation: 'fadeUp 0.5s ease both' }}>
          {/* Badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '7px',
            padding: '4px 12px',
            background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.22)',
            borderRadius: '999px', fontSize: '0.72rem', color: '#60a5fa', fontWeight: '600',
            marginBottom: '1.1rem', letterSpacing: '0.03em',
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3b82f6', boxShadow: '0 0 6px #3b82f6', animation: 'dotPulse 2s infinite' }} />
            BuildFlow AI · Construction Intelligence Platform
          </div>

          <h1 style={{
            fontSize: 'clamp(2rem, 4vw, 2.8rem)', fontWeight: '900',
            letterSpacing: '-0.045em', color: '#f8fafc', lineHeight: '1.08',
            margin: '0 0 0.85rem',
          }}>
            Intelligent{' '}
            <span style={{
              background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>
              Construction
            </span>
            <br />
            Management
          </h1>

          <p style={{ fontSize: '0.9rem', color: '#64748b', lineHeight: '1.7', marginBottom: '1.5rem', maxWidth: '440px' }}>
            AI-powered platform for real-time project oversight — query data, generate documents, predict delays, and orchestrate multi-agent workflows.
          </p>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <Link href="/chat" className="btn-primary" style={{ padding: '10px 22px' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              Launch AI Chat
            </Link>
            <Link href="/analytics" className="btn-secondary" style={{ padding: '10px 22px' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              Analytics
            </Link>
          </div>
        </div>

        {/* Smart Upload Dropzone */}
        <div
          style={{
            position: 'relative', zIndex: 1,
            border: `2px dashed ${dragActive ? '#3b82f6' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: '16px',
            padding: '2rem 1.5rem',
            textAlign: 'center',
            background: dragActive ? 'rgba(59,130,246,0.08)' : 'rgba(255,255,255,0.02)',
            cursor: 'pointer',
            transition: 'all 200ms ease',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px',
            boxShadow: dragActive ? '0 0 24px rgba(59,130,246,0.25)' : 'none',
          }}
          onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}
          onClick={() => document.getElementById('excel-file-input')?.click()}
        >
          <input type="file" id="excel-file-input" style={{ display: 'none' }} accept=".xlsx,.xls,.csv" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])} />

          {uploading ? (
            <>
              <div style={{
                width: '44px', height: '44px', borderRadius: '50%',
                border: '3px solid rgba(59,130,246,0.2)', borderTopColor: '#3b82f6',
                animation: 'spin 0.9s linear infinite',
              }} />
              <span style={{ fontSize: '0.85rem', color: '#60a5fa', fontWeight: 600 }}>Parsing file…</span>
            </>
          ) : (
            <>
              <div style={{
                width: '52px', height: '52px', borderRadius: '14px',
                background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: dragActive ? 'bounce 0.7s infinite' : 'float 3s ease-in-out infinite',
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2.2" strokeLinecap="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <div style={{ fontSize: '0.875rem', fontWeight: '700', color: '#f1f5f9' }}>
                {dragActive ? 'Release to upload' : 'Drop Excel or CSV here'}
              </div>
              <div style={{ fontSize: '0.72rem', color: '#475569' }}>
                .xlsx · .xls · .csv · Any column structure
              </div>
              <div style={{
                fontSize: '0.68rem', color: '#3b82f6',
                background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)',
                borderRadius: '6px', padding: '3px 10px', fontWeight: 600,
              }}>
                🤖 AI auto-detects columns
              </div>
            </>
          )}

          {uploadStatus && (
            <div style={{
              width: '100%', padding: '8px 12px', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 500,
              display: 'flex', alignItems: 'flex-start', gap: '7px', textAlign: 'left',
              background: uploadStatus.type === 'success' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
              border: `1px solid ${uploadStatus.type === 'success' ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`,
              color: uploadStatus.type === 'success' ? '#34d399' : '#f87171',
            }} onClick={e => e.stopPropagation()}>
              {uploadStatus.type === 'success' ? '✅' : '❌'} {uploadStatus.message}
            </div>
          )}
        </div>
      </section>

      {/* ── Stats ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '1.75rem' }}>
        {stats.map((s, i) => <StatCard key={i} {...s} />)}
      </div>

      {/* ── Budget summary strip ── */}
      {budget > 0 && (
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: '14px',
          padding: '18px 24px',
          marginBottom: '1.75rem',
          display: 'flex',
          alignItems: 'center',
          gap: '32px',
          flexWrap: 'wrap',
          animation: 'fadeUp 0.5s 300ms both ease',
        }}>
          <div>
            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--t-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Total Budget</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.03em' }}>₹ {budget.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Lac</div>
          </div>
          <div style={{ height: '40px', width: '1px', background: 'var(--border)' }} />
          <div>
            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--t-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Total Spent</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#34d399', letterSpacing: '-0.03em' }}>₹ {spent.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Lac</div>
          </div>
          <div style={{ height: '40px', width: '1px', background: 'var(--border)' }} />
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '7px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--t-3)', fontWeight: 600 }}>Budget Utilisation</span>
              <span style={{ fontSize: '0.7rem', color: '#60a5fa', fontWeight: 700 }}>{budget > 0 ? ((spent / budget) * 100).toFixed(1) : 0}%</span>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '999px', overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: '999px',
                background: 'linear-gradient(90deg, #3b82f6, #06b6d4)',
                width: `${Math.min(budget > 0 ? (spent / budget) * 100 : 0, 100)}%`,
                transition: 'width 1s ease',
              }} />
            </div>
          </div>
        </div>
      )}

      {/* ── Workspaces ── */}
      <section style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--t-1)', letterSpacing: '-0.02em', margin: 0 }}>Operations Workspaces</h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--t-3)', margin: '3px 0 0' }}>Jump into any module to manage your projects</p>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          {workspaceCards.map(card => (
            <Link key={card.href} href={card.href} className="nav-card" style={{ animation: 'fadeUp 0.5s 400ms both ease' }}>
              <div className={`nav-card-icon-wrapper ${card.color}`}>{card.icon}</div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--t-1)', margin: '4px 0 2px', letterSpacing: '-0.02em' }}>{card.label}</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--t-3)', lineHeight: '1.65', margin: 0, flex: 1 }}>{card.desc}</p>
              <span className="nav-card-link">Open workspace →</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Projects Table ── */}
      {projects.length > 0 && (
        <section style={{ animation: 'fadeUp 0.5s 500ms both ease' }}>
          <div className="card">
            <div className="card-header">
              <div>
                <h2 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--t-1)', margin: 0 }}>Active Projects Overview</h2>
                <p style={{ fontSize: '0.73rem', color: 'var(--t-3)', margin: '2px 0 0' }}>Latest {projects.length} records</p>
              </div>
              <Link href="/analytics" className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.78rem' }}>
                Full Dataset →
              </Link>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Project Name</th>
                    <th>Location</th>
                    <th>Phase</th>
                    <th>Budget</th>
                    <th>Progress</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map(p => (
                    <tr key={p.id}>
                      <td>
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem', color: '#60a5fa', fontWeight: 600 }}>
                          {p.id}
                        </span>
                      </td>
                      <td style={{ color: 'var(--t-1)', fontWeight: 500 }}>{p.name}</td>
                      <td style={{ fontSize: '0.83rem' }}>{p.location}</td>
                      <td style={{ fontSize: '0.83rem' }}>{p.phase}</td>
                      <td style={{ fontWeight: 600, color: 'var(--t-1)', whiteSpace: 'nowrap' }}>₹{p.budget} Lac</td>
                      <td style={{ width: '160px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.06)', borderRadius: '999px', overflow: 'hidden' }}>
                            <div style={{
                              height: '100%', borderRadius: '999px',
                              width: `${p.progress}%`,
                              background: p.status === 'OnTrack' ? '#10b981'
                                : p.status === 'Delayed' ? '#ef4444' : '#f59e0b',
                              transition: 'width 1s ease',
                            }} />
                          </div>
                          <span style={{ fontSize: '0.72rem', color: 'var(--t-3)', minWidth: '28px', fontWeight: 600 }}>
                            {p.progress.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${p.status === 'OnTrack' ? 'badge-success' : p.status === 'Delayed' ? 'badge-danger' : 'badge-warning'}`}>
                          {p.status === 'OnTrack' ? '● On Track' : p.status === 'Delayed' ? '● Delayed' : `● ${p.status}`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* Loading state */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '16px', marginBottom: '1.75rem', marginTop: '-1.75rem' }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: '110px', borderRadius: '16px' }} />
          ))}
        </div>
      )}

    </div>
  );
}
