'use client';

import React from 'react';

type TrendDirection = 'up' | 'down' | 'neutral';

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: TrendDirection;
  color?: string;
  icon?: React.ReactNode;
}

const TrendArrow: React.FC<{ trend: TrendDirection }> = ({ trend }) => {
  if (trend === 'up') {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          color: '#10b981',
          fontSize: '1.1rem',
          fontWeight: 700,
          marginLeft: '0.4rem',
        }}
        aria-label="Trending up"
      >
        ↑
      </span>
    );
  }
  if (trend === 'down') {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          color: '#ef4444',
          fontSize: '1.1rem',
          fontWeight: 700,
          marginLeft: '0.4rem',
        }}
        aria-label="Trending down"
      >
        ↓
      </span>
    );
  }
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        color: '#94a3b8',
        fontSize: '1.1rem',
        fontWeight: 700,
        marginLeft: '0.4rem',
      }}
      aria-label="Neutral trend"
    >
      →
    </span>
  );
};

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  subtitle,
  trend = 'neutral',
  color = '#3b82f6',
  icon,
}) => {
  const glowColor = color + '33'; // 20% opacity hex

  return (
    <div
      style={{
        position: 'relative',
        background: 'rgba(15, 23, 42, 0.7)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.08)',
        borderLeft: `4px solid ${color}`,
        padding: '1.5rem 1.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        boxShadow: `0 0 24px 0 ${glowColor}, 0 4px 24px rgba(0,0,0,0.4)`,
        overflow: 'hidden',
        animation: 'kpiGlow 3s ease-in-out infinite alternate',
        minWidth: 0,
        flex: '1 1 200px',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-3px)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 0 36px 0 ${glowColor}, 0 8px 32px rgba(0,0,0,0.5)`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 0 24px 0 ${glowColor}, 0 4px 24px rgba(0,0,0,0.4)`;
      }}
    >
      {/* Background shimmer orb */}
      <div
        style={{
          position: 'absolute',
          top: '-30px',
          right: '-30px',
          width: '100px',
          height: '100px',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
          pointerEvents: 'none',
        }}
      />

      {/* Header row: title + icon */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: '0.8rem',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#94a3b8',
          }}
        >
          {title}
        </p>
        {icon && (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: `${color}22`,
              color: color,
              fontSize: '1.1rem',
            }}
          >
            {icon}
          </span>
        )}
      </div>

      {/* Value row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '0.25rem',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: '2rem',
            fontWeight: 800,
            lineHeight: 1.1,
            color: '#f1f5f9',
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </p>
        {trend && <TrendArrow trend={trend} />}
      </div>

      {/* Subtitle */}
      {subtitle && (
        <p
          style={{
            margin: 0,
            fontSize: '0.78rem',
            color: '#64748b',
            fontWeight: 500,
          }}
        >
          {subtitle}
        </p>
      )}

      <style jsx>{`
        @keyframes kpiGlow {
          from {
            box-shadow: 0 0 18px 0 ${glowColor}, 0 4px 24px rgba(0, 0, 0, 0.4);
          }
          to {
            box-shadow: 0 0 32px 4px ${glowColor}, 0 4px 24px rgba(0, 0, 0, 0.4);
          }
        }
      `}</style>
    </div>
  );
};

export default KPICard;
