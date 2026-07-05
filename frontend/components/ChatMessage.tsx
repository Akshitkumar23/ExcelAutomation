'use client';

import React, { forwardRef } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────
export interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// ─── Robot / BuildFlow avatar SVG ─────────────────────────────────────────────
const BuildFlowAvatar = () => (
  <svg
    width="28"
    height="28"
    viewBox="0 0 28 28"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle cx="14" cy="14" r="14" fill="url(#avatarGrad)" />
    {/* Building base */}
    <rect x="8" y="14" width="12" height="9" rx="1" fill="rgba(255,255,255,0.9)" />
    {/* Windows */}
    <rect x="10" y="16" width="2.5" height="2.5" rx="0.5" fill="rgba(59,130,246,0.9)" />
    <rect x="14" y="16" width="2.5" height="2.5" rx="0.5" fill="rgba(59,130,246,0.9)" />
    <rect x="10" y="20" width="2.5" height="2" rx="0.5" fill="rgba(59,130,246,0.7)" />
    <rect x="14" y="20" width="2.5" height="2" rx="0.5" fill="rgba(59,130,246,0.7)" />
    {/* Roof / AI antenna */}
    <path d="M10 14 L14 8 L18 14Z" fill="rgba(255,255,255,0.95)" />
    <circle cx="14" cy="6.5" r="1.5" fill="#60a5fa" />
    <line x1="14" y1="8" x2="14" y2="6.5" stroke="#60a5fa" strokeWidth="1.2" />
    <defs>
      <linearGradient id="avatarGrad" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
        <stop stopColor="#1d4ed8" />
        <stop offset="1" stopColor="#7c3aed" />
      </linearGradient>
    </defs>
  </svg>
);

// ─── Simple inline markdown renderer ─────────────────────────────────────────
function renderContent(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const codeBlockRegex = /```([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    // text before code block
    if (match.index > lastIndex) {
      parts.push(renderTextSections(text.slice(lastIndex, match.index), parts.length));
    }
    // code block
    parts.push(
      <pre
        key={`code-${match.index}`}
        style={{
          background: 'rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '8px',
          padding: '10px 12px',
          overflowX: 'auto',
          fontSize: '11px',
          fontFamily: '"Fira Code", Courier, monospace',
          color: '#a5f3fc',
          margin: '10px 0',
          whiteSpace: 'pre',
          wordBreak: 'normal',
        }}
      >
        {match[1].trim()}
      </pre>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(renderTextSections(text.slice(lastIndex), parts.length));
  }

  return <>{parts}</>;
}

function renderTextSections(text: string, baseKey: number): React.ReactNode {
  const lines = text.split('\n');
  const renderedLines = lines.map((line, lineIndex) => {
    let cleanLine = line.trim();
    if (cleanLine.startsWith('## ')) {
      return (
        <h3 key={`h3-${lineIndex}`} style={{ fontSize: '0.98rem', fontWeight: '700', color: '#60a5fa', margin: '10px 0 6px 0', letterSpacing: '-0.01em' }}>
          {renderInline(cleanLine.slice(3), lineIndex)}
        </h3>
      );
    }
    if (cleanLine.startsWith('# ')) {
      return (
        <h2 key={`h2-${lineIndex}`} style={{ fontSize: '1.1rem', fontWeight: '800', color: '#22d3ee', margin: '14px 0 8px 0', letterSpacing: '-0.015em' }}>
          {renderInline(cleanLine.slice(2), lineIndex)}
        </h2>
      );
    }
    if (cleanLine.startsWith('- ') || cleanLine.startsWith('* ')) {
      return (
        <div key={`li-${lineIndex}`} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', margin: '4px 0 4px 10px', fontSize: '0.86rem' }}>
          <span style={{ color: '#06b6d4', marginTop: '1px', flexShrink: 0 }}>•</span>
          <span style={{ flex: 1, color: '#cbd5e1' }}>{renderInline(cleanLine.slice(2), lineIndex)}</span>
        </div>
      );
    }
    if (cleanLine === '') {
      return <div key={`empty-${lineIndex}`} style={{ height: '6px' }} />;
    }
    return (
      <p key={`p-${lineIndex}`} style={{ margin: '0 0 6px 0', fontSize: '0.86rem', color: '#cbd5e1', lineHeight: '1.55' }}>
        {renderInline(cleanLine, lineIndex)}
      </p>
    );
  });
  return <div key={baseKey} style={{ display: 'flex', flexDirection: 'column' }}>{renderedLines}</div>;
}

function renderInline(text: string, baseKey: number): React.ReactNode {
  // Handle **bold**
  const boldRegex = /\*\*(.*?)\*\*/g;
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = boldRegex.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(
        <span key={`${baseKey}-t-${last}`}>{text.slice(last, m.index)}</span>
      );
    }
    nodes.push(
      <strong key={`${baseKey}-b-${m.index}`} style={{ fontWeight: 700, color: '#f8fafc' }}>
        {m[1]}
      </strong>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    nodes.push(<span key={`${baseKey}-t-end`}>{text.slice(last)}</span>);
  }

  // Wrap lines in paragraph spans
  return (
    <span key={baseKey}>
      {nodes.length > 0 ? nodes : text}
    </span>
  );
}

// ─── ChatMessage Component ────────────────────────────────────────────────────
const ChatMessage = forwardRef<HTMLDivElement, ChatMessageProps>(
  ({ role, content, timestamp }, ref) => {
    const isUser = role === 'user';

    return (
      <div
        ref={ref}
        className="fade-in-up"
        style={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          alignItems: 'flex-end',
          gap: '10px',
          marginBottom: '16px',
          padding: '0 4px',
        }}
      >
        {/* Avatar – only for assistant */}
        {!isUser && (
          <div
            style={{
              flexShrink: 0,
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #1d4ed8, #7c3aed)',
              boxShadow: '0 4px 12px rgba(59,130,246,0.4)',
            }}
          >
            <BuildFlowAvatar />
          </div>
        )}

        {/* Bubble */}
        <div style={{ maxWidth: '72%', display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
          {!isUser && (
            <span style={{ fontSize: '11px', fontWeight: 600, color: '#60a5fa', marginBottom: '4px', letterSpacing: '0.05em' }}>
              BuildFlow AI
            </span>
          )}

          <div
            style={
              isUser
                ? {
                    background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
                    color: '#fff',
                    padding: '12px 16px',
                    borderRadius: '18px 18px 4px 18px',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    boxShadow: '0 4px 20px rgba(59,130,246,0.3)',
                    wordBreak: 'break-word',
                  }
                : {
                    background: 'rgba(13, 21, 37, 0.92)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    backdropFilter: 'blur(20px)',
                    color: '#e2e8f0',
                    padding: '12px 16px',
                    borderRadius: '18px 18px 18px 4px',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                    wordBreak: 'break-word',
                  }
            }
          >
            {renderContent(content)}
          </div>

          <span
            style={{
              fontSize: '10px',
              color: 'var(--text-muted)',
              marginTop: '4px',
              paddingLeft: isUser ? 0 : '4px',
              paddingRight: isUser ? '4px' : 0,
            }}
          >
            {timestamp}
          </span>
        </div>
      </div>
    );
  }
);

ChatMessage.displayName = 'ChatMessage';
export default ChatMessage;
