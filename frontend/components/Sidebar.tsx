'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

const navLinks = [
  {
    href: '/',
    label: 'Dashboard',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    href: '/chat',
    label: 'AI Chat',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        <path d="M8 10h8" />
        <path d="M8 14h5" />
      </svg>
    ),
  },
  {
    href: '/analytics',
    label: 'Analytics',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    href: '/docgen',
    label: 'Doc Generator',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    href: '/agents',
    label: 'Multi-Agent',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="5" r="3" />
        <circle cx="4" cy="19" r="3" />
        <circle cx="20" cy="19" r="3" />
        <path d="M12 8v4" />
        <path d="M7 17l-2.5-3.5" />
        <path d="M17 17l2.5-3.5" />
        <path d="M9.5 12.5L7 17" />
        <path d="M14.5 12.5L17 17" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [activeWorkspace, setActiveWorkspace] = useState('default');
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);

  useEffect(() => {
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    setActiveWorkspace(active);

    const fetchWorkspaces = async () => {
      const saved = localStorage.getItem('buildflow_chat_sessions');
      if (saved) {
        try {
          const sessions = JSON.parse(saved);
          const list = [];
          for (const s of Array.isArray(sessions) ? sessions : []) {
            try {
              const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/workspace/${s.id}`);
              if (res.ok) {
                const data = await res.json();
                if (data.has_workspace) {
                  list.push({ id: s.id, name: s.title.length > 18 ? s.title.slice(0, 15) + '...' : s.title });
                }
              }
            } catch (e) {
              console.error(e);
            }
          }
          setWorkspaces(list);
        } catch (e) {
          console.error(e);
        }
      }
    };
    fetchWorkspaces();
  }, []);

  const handleWorkspaceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setActiveWorkspace(val);
    localStorage.setItem('buildflow_active_workspace', val);
    window.location.reload();
  };

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div style={{
        padding: '28px 20px 24px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Building Icon SVG */}
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'var(--gradient-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: 'var(--shadow-glow-blue)',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="9" width="18" height="13" rx="1" />
              <path d="M3 9l9-7 9 7" />
              <path d="M9 22V12h6v10" />
            </svg>
          </div>

          <div>
            <div style={{
              fontSize: '1.1rem',
              fontWeight: '800',
              letterSpacing: '-0.02em',
              lineHeight: 1.2,
            }}>
              <span style={{
                background: 'var(--gradient-primary)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                BuildFlow
              </span>
              <span style={{ color: 'var(--text-primary)', marginLeft: '3px' }}>AI</span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: '500', marginTop: '1px' }}>
              Construction Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Nav Label */}
      <div style={{
        padding: '20px 20px 8px',
      }}>
        <span style={{
          fontSize: '0.65rem',
          fontWeight: '700',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
        }}>
          Navigation
        </span>
      </div>

      {/* Nav Links */}
      <nav style={{ padding: '0 12px', flex: 1, overflowY: 'auto' }}>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navLinks.map((link) => {
            const active = isActive(link.href);
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-md)',
                    color: active ? 'white' : 'var(--text-secondary)',
                    fontWeight: active ? '600' : '500',
                    fontSize: '0.9rem',
                    background: active
                      ? 'linear-gradient(135deg, rgba(59,130,246,0.25) 0%, rgba(6,182,212,0.15) 100%)'
                      : 'transparent',
                    border: active ? '1px solid rgba(59,130,246,0.3)' : '1px solid transparent',
                    transition: 'all var(--transition-fast)',
                    position: 'relative',
                    textDecoration: 'none',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.background = 'var(--bg-hover)';
                      (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-primary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.background = 'transparent';
                      (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-secondary)';
                    }
                  }}
                >
                  {/* Icon wrapper */}
                  <span style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: active ? 'rgba(59,130,246,0.2)' : 'rgba(255,255,255,0.04)',
                    color: active ? 'var(--accent-blue-light)' : 'inherit',
                    flexShrink: 0,
                    transition: 'all var(--transition-fast)',
                  }}>
                    {link.icon}
                  </span>

                  <span>{link.label}</span>

                  {/* Active indicator */}
                  {active && (
                    <span style={{
                      marginLeft: 'auto',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: 'var(--accent-cyan)',
                      boxShadow: '0 0 6px var(--accent-cyan)',
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
      <div style={{ height: '1px', background: 'var(--border)', margin: '0 12px' }} />

      {/* Bottom Section */}
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        
        {/* Workspace Selector */}
        <div>
          <div style={{
            fontSize: '0.65rem',
            fontWeight: '700',
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            marginBottom: '8px',
          }}>
            Active Workspace
          </div>
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'border-color var(--transition-fast)',
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--border-light)'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
          >
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>📂</span>
            <select
              value={activeWorkspace}
              onChange={handleWorkspaceChange}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                fontWeight: '600',
                outline: 'none',
                cursor: 'pointer',
                flex: 1,
                width: '100%',
              }}
            >
              <option value="default" style={{ background: '#0f172a', color: '#f1f5f9' }}>Default Database</option>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id} style={{ background: '#0f172a', color: '#f1f5f9' }}>
                  {w.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Version */}
        <div style={{
          textAlign: 'center',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
        }}>
          BuildFlow AI &copy; 2026 · v1.0.0
        </div>
      </div>
    </aside>
  );
}
