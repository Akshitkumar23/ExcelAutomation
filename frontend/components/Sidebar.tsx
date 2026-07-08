'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

const navLinks = [
  {
    href: '/',
    label: 'Dashboard',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
    color: '#3b82f6',
  },
  {
    href: '/chat',
    label: 'AI Chat',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    color: '#06b6d4',
  },
  {
    href: '/analytics',
    label: 'Analytics',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    color: '#10b981',
  },
  {
    href: '/docgen',
    label: 'Doc Generator',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
    color: '#8b5cf6',
  },
  {
    href: '/agents',
    label: 'Multi-Agent',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="5" r="3" />
        <circle cx="4" cy="19" r="3" />
        <circle cx="20" cy="19" r="3" />
        <path d="M12 8v4M7 17l-2.5-3.5M17 17l2.5-3.5" />
      </svg>
    ),
    color: '#f59e0b',
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [activeWorkspace, setActiveWorkspace] = useState('default');
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);
  const [backendOnline, setBackendOnline] = useState(false);

  useEffect(() => {
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    setActiveWorkspace(active);

    // Check backend status
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/health`)
      .then(r => r.ok && setBackendOnline(true))
      .catch(() => setBackendOnline(false));

    const fetchWorkspaces = async () => {
      const saved = localStorage.getItem('buildflow_chat_sessions');
      if (!saved) return;
      try {
        const sessions = JSON.parse(saved);
        const list = [];
        for (const s of Array.isArray(sessions) ? sessions : []) {
          try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/workspace/${s.id}`);
            if (res.ok) {
              const data = await res.json();
              if (data.has_workspace) {
                list.push({ id: s.id, name: s.title.length > 18 ? s.title.slice(0, 15) + '…' : s.title });
              }
            }
          } catch { /* noop */ }
        }
        setWorkspaces(list);
      } catch { /* noop */ }
    };
    fetchWorkspaces();
  }, []);

  const handleWorkspaceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setActiveWorkspace(val);
    localStorage.setItem('buildflow_active_workspace', val);
    window.location.reload();
  };

  const isActive = (href: string) => href === '/' ? pathname === '/' : pathname.startsWith(href);

  return (
    <aside style={{
      width: '264px',
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #0b0d16 0%, #08090f 100%)',
      borderRight: '1px solid rgba(255,255,255,0.06)',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      left: 0, top: 0, bottom: 0,
      zIndex: 100,
    }}>

      {/* Logo */}
      <div style={{ padding: '24px 20px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px', height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 0 20px rgba(59,130,246,0.4)',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="9" width="18" height="13" rx="1.5" />
              <path d="M3 9l9-7 9 7" />
              <path d="M9 22V13h6v9" />
            </svg>
          </div>

          <div>
            <div style={{ fontSize: '1.05rem', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: 1.2 }}>
              <span style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>BuildFlow</span>
              <span style={{ color: '#f8fafc', marginLeft: '3px' }}>AI</span>
            </div>
            <div style={{ fontSize: '0.65rem', color: '#475569', fontWeight: '500', marginTop: '1px', letterSpacing: '0.04em' }}>
              Construction Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Status */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '7px',
          fontSize: '0.72rem', color: backendOnline ? '#10b981' : '#64748b',
          fontWeight: 500,
        }}>
          <span style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: backendOnline ? '#10b981' : '#475569',
            boxShadow: backendOnline ? '0 0 6px #10b981' : 'none',
            animation: backendOnline ? 'dotPulse 2s infinite' : 'none',
            flexShrink: 0,
          }} />
          {backendOnline ? 'Backend online' : 'Backend offline'}
        </div>
      </div>

      {/* Nav Label */}
      <div style={{ padding: '18px 20px 8px' }}>
        <span style={{ fontSize: '0.62rem', fontWeight: '700', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          Navigation
        </span>
      </div>

      {/* Nav Links */}
      <nav style={{ padding: '0 10px', flex: 1, overflowY: 'auto' }}>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {navLinks.map((link) => {
            const active = isActive(link.href);
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '11px',
                    padding: '9px 12px',
                    borderRadius: '10px',
                    color: active ? '#f8fafc' : '#64748b',
                    fontWeight: active ? '600' : '450',
                    fontSize: '0.875rem',
                    background: active ? `rgba(59,130,246,0.12)` : 'transparent',
                    border: active ? `1px solid rgba(59,130,246,0.25)` : '1px solid transparent',
                    transition: 'all 150ms ease',
                    textDecoration: 'none',
                    letterSpacing: '-0.01em',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.background = 'rgba(255,255,255,0.05)';
                      (e.currentTarget as HTMLAnchorElement).style.color = '#cbd5e1';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.background = 'transparent';
                      (e.currentTarget as HTMLAnchorElement).style.color = '#64748b';
                    }
                  }}
                >
                  <span style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: '30px', height: '30px',
                    borderRadius: '8px',
                    background: active ? `${link.color}1a` : 'rgba(255,255,255,0.04)',
                    color: active ? link.color : 'inherit',
                    flexShrink: 0,
                    transition: 'all 150ms ease',
                  }}>
                    {link.icon}
                  </span>

                  <span style={{ flex: 1 }}>{link.label}</span>

                  {active && (
                    <span style={{
                      width: '5px', height: '5px',
                      borderRadius: '50%',
                      background: link.color,
                      boxShadow: `0 0 8px ${link.color}`,
                      flexShrink: 0,
                    }} />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Divider */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)', margin: '0 10px' }} />

      {/* Workspace + Footer */}
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>

        {/* Workspace selector */}
        <div>
          <div style={{ fontSize: '0.62rem', fontWeight: '700', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '7px' }}>
            Active Workspace
          </div>
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '9px',
            padding: '8px 11px',
            display: 'flex', alignItems: 'center', gap: '8px',
            transition: 'border-color 150ms ease',
          }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)')}
          >
            <span style={{ fontSize: '0.9rem', flexShrink: 0 }}>📂</span>
            <select
              value={activeWorkspace}
              onChange={handleWorkspaceChange}
              style={{
                background: 'transparent', border: 'none',
                color: '#cbd5e1', fontSize: '0.78rem', fontWeight: '500',
                outline: 'none', cursor: 'pointer', flex: 1, width: '100%',
              }}
            >
              <option value="default" style={{ background: '#0d1117', color: '#f1f5f9' }}>Default Database</option>
              {workspaces.map(w => (
                <option key={w.id} value={w.id} style={{ background: '#0d1117', color: '#f1f5f9' }}>{w.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: '6px', padding: '6px 0',
        }}>
          <div style={{
            width: '4px', height: '4px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
          }} />
          <span style={{ fontSize: '0.65rem', color: '#334155', fontWeight: '500', letterSpacing: '0.04em' }}>
            BuildFlow AI · v1.0.0 · 2026
          </span>
        </div>
      </div>
    </aside>
  );
}
