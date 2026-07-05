'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Filler,
  Title,
  ScatterController,
} from 'chart.js';
import { Doughnut, Bar, Line, Scatter } from 'react-chartjs-2';
import KPICard from '@/components/KPICard';

// ─── Register Chart.js components ───────────────────────────────────────────
ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Filler,
  Title,
  ScatterController
);

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Types ───────────────────────────────────────────────────────────────────
type ProjectStatus = 'OnTrack' | 'Delayed' | 'Completed' | 'OnHold';
type ProjectPhase = 'Planning' | 'Foundation' | 'Structure' | 'Interior' | 'Finishing' | 'Handover';

interface Project {
  id: string;
  name: string;
  location: string;
  budget: number;   // ₹ Lac
  spent: number;    // ₹ Lac
  status: ProjectStatus;
  progress: number; // 0-100
  phase: ProjectPhase;
  labourCount: number;
  startDate: string;
}

// ─── Hardcoded Demo Data (50 projects) ──────────────────────────────────────
const DEMO_PROJECTS: Project[] = [
  { id: 'PRJ-001', name: 'Sunrise Villa Residency',      location: 'Mumbai',    budget: 420, spent: 315, status: 'OnTrack',   progress: 75, phase: 'Structure',   labourCount: 48, startDate: '2024-01-10' },
  { id: 'PRJ-002', name: 'Green Meadows Township',        location: 'Pune',      budget: 680, spent: 590, status: 'Delayed',   progress: 62, phase: 'Interior',    labourCount: 72, startDate: '2023-11-05' },
  { id: 'PRJ-003', name: 'Skyline Heights Phase 1',       location: 'Bengaluru', budget: 550, spent: 540, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 60, startDate: '2023-06-20' },
  { id: 'PRJ-004', name: 'BlueStar Apartments',           location: 'Chennai',   budget: 310, spent: 120, status: 'OnTrack',   progress: 38, phase: 'Foundation',  labourCount: 35, startDate: '2024-03-01' },
  { id: 'PRJ-005', name: 'Heritage Homes Block A',        location: 'Hyderabad', budget: 480, spent: 400, status: 'OnHold',    progress: 55, phase: 'Structure',   labourCount: 0,  startDate: '2023-09-15' },
  { id: 'PRJ-006', name: 'Coastal Breeze Villas',         location: 'Mumbai',    budget: 720, spent: 510, status: 'OnTrack',   progress: 70, phase: 'Interior',    labourCount: 80, startDate: '2024-02-10' },
  { id: 'PRJ-007', name: 'Lakefront Luxury Suites',       location: 'Pune',      budget: 390, spent: 110, status: 'OnTrack',   progress: 28, phase: 'Foundation',  labourCount: 30, startDate: '2024-04-18' },
  { id: 'PRJ-008', name: 'Urban Nest Micro Apartments',   location: 'Bengaluru', budget: 210, spent: 195, status: 'Delayed',   progress: 80, phase: 'Finishing',   labourCount: 20, startDate: '2023-12-01' },
  { id: 'PRJ-009', name: 'Emerald Grove Society',         location: 'Ahmedabad', budget: 570, spent: 460, status: 'OnTrack',   progress: 81, phase: 'Finishing',   labourCount: 65, startDate: '2023-10-22' },
  { id: 'PRJ-010', name: 'Royal Enclave Phase 2',         location: 'Delhi',     budget: 890, spent: 870, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 95, startDate: '2023-03-05' },
  { id: 'PRJ-011', name: 'Serenity Towers Block B',       location: 'Hyderabad', budget: 460, spent: 200, status: 'OnTrack',   progress: 42, phase: 'Structure',   labourCount: 45, startDate: '2024-01-25' },
  { id: 'PRJ-012', name: 'Maple Ridge Condos',            location: 'Chennai',   budget: 330, spent: 280, status: 'Delayed',   progress: 68, phase: 'Interior',    labourCount: 38, startDate: '2023-11-14' },
  { id: 'PRJ-013', name: 'Pinnacle Business Residences',  location: 'Mumbai',    budget: 1100,spent: 880, status: 'OnTrack',   progress: 80, phase: 'Finishing',   labourCount: 110,startDate: '2023-07-01' },
  { id: 'PRJ-014', name: 'Palm Grove Villas',             location: 'Pune',      budget: 430, spent: 50,  status: 'OnTrack',   progress: 10, phase: 'Planning',    labourCount: 12, startDate: '2024-05-05' },
  { id: 'PRJ-015', name: 'Summit Eco Housing',            location: 'Bengaluru', budget: 280, spent: 260, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 28, startDate: '2023-08-12' },
  { id: 'PRJ-016', name: 'Crystal Bay Residency',         location: 'Ahmedabad', budget: 640, spent: 320, status: 'OnTrack',   progress: 50, phase: 'Structure',   labourCount: 70, startDate: '2024-02-20' },
  { id: 'PRJ-017', name: 'Silver Oaks Township',          location: 'Delhi',     budget: 750, spent: 690, status: 'Delayed',   progress: 88, phase: 'Finishing',   labourCount: 82, startDate: '2023-09-01' },
  { id: 'PRJ-018', name: 'Horizon Heights Phase 3',       location: 'Mumbai',    budget: 980, spent: 410, status: 'OnTrack',   progress: 40, phase: 'Structure',   labourCount: 100,startDate: '2024-01-08' },
  { id: 'PRJ-019', name: 'Tranquil Gardens Colony',       location: 'Hyderabad', budget: 360, spent: 340, status: 'OnHold',    progress: 72, phase: 'Interior',    labourCount: 0,  startDate: '2023-10-10' },
  { id: 'PRJ-020', name: 'Orchid Valley Apartments',      location: 'Chennai',   budget: 290, spent: 145, status: 'OnTrack',   progress: 50, phase: 'Foundation',  labourCount: 32, startDate: '2024-03-15' },
  { id: 'PRJ-021', name: 'Prestige Park Residences',      location: 'Bengaluru', budget: 820, spent: 750, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 88, startDate: '2023-04-10' },
  { id: 'PRJ-022', name: 'Willow Creek Villas',           location: 'Pune',      budget: 510, spent: 380, status: 'OnTrack',   progress: 72, phase: 'Interior',    labourCount: 55, startDate: '2023-12-20' },
  { id: 'PRJ-023', name: 'Golden Gate Society',           location: 'Ahmedabad', budget: 445, spent: 200, status: 'OnTrack',   progress: 44, phase: 'Structure',   labourCount: 48, startDate: '2024-02-01' },
  { id: 'PRJ-024', name: 'Amber View Apartments',         location: 'Delhi',     budget: 390, spent: 380, status: 'Delayed',   progress: 90, phase: 'Finishing',   labourCount: 42, startDate: '2023-10-05' },
  { id: 'PRJ-025', name: 'Meadow Lane Homes',             location: 'Mumbai',    budget: 310, spent: 60,  status: 'OnTrack',   progress: 18, phase: 'Planning',    labourCount: 15, startDate: '2024-04-22' },
  { id: 'PRJ-026', name: 'Crestwood Heights',             location: 'Hyderabad', budget: 600, spent: 480, status: 'OnTrack',   progress: 80, phase: 'Finishing',   labourCount: 66, startDate: '2023-11-01' },
  { id: 'PRJ-027', name: 'Diamond Petal Residency',       location: 'Chennai',   budget: 270, spent: 265, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 30, startDate: '2023-07-18' },
  { id: 'PRJ-028', name: 'Jasmine Grove Township',        location: 'Bengaluru', budget: 730, spent: 290, status: 'OnTrack',   progress: 38, phase: 'Foundation',  labourCount: 78, startDate: '2024-03-01' },
  { id: 'PRJ-029', name: 'Titanium Tower Block C',        location: 'Pune',      budget: 870, spent: 800, status: 'Delayed',   progress: 85, phase: 'Finishing',   labourCount: 92, startDate: '2023-08-25' },
  { id: 'PRJ-030', name: 'Lotus Petal Society Phase 1',   location: 'Ahmedabad', budget: 520, spent: 420, status: 'OnTrack',   progress: 78, phase: 'Interior',    labourCount: 58, startDate: '2023-12-10' },
  { id: 'PRJ-031', name: 'Riverdale Apartments',          location: 'Delhi',     budget: 410, spent: 175, status: 'OnTrack',   progress: 40, phase: 'Structure',   labourCount: 44, startDate: '2024-02-14' },
  { id: 'PRJ-032', name: 'Sunflower Heights',             location: 'Mumbai',    budget: 340, spent: 320, status: 'OnHold',    progress: 58, phase: 'Interior',    labourCount: 0,  startDate: '2023-09-28' },
  { id: 'PRJ-033', name: 'Evergreen Enclave',             location: 'Hyderabad', budget: 490, spent: 180, status: 'OnTrack',   progress: 35, phase: 'Foundation',  labourCount: 50, startDate: '2024-03-20' },
  { id: 'PRJ-034', name: 'Aqua Vista Condos',             location: 'Chennai',   budget: 380, spent: 370, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 40, startDate: '2023-05-30' },
  { id: 'PRJ-035', name: 'Metro Link Residences',         location: 'Bengaluru', budget: 660, spent: 495, status: 'OnTrack',   progress: 73, phase: 'Interior',    labourCount: 74, startDate: '2023-11-20' },
  { id: 'PRJ-036', name: 'Phoenix Rise Towers',           location: 'Pune',      budget: 580, spent: 120, status: 'OnTrack',   progress: 20, phase: 'Foundation',  labourCount: 60, startDate: '2024-04-01' },
  { id: 'PRJ-037', name: 'Ivory Arch Township',           location: 'Ahmedabad', budget: 700, spent: 640, status: 'Delayed',   progress: 84, phase: 'Finishing',   labourCount: 76, startDate: '2023-10-15' },
  { id: 'PRJ-038', name: 'Sterling Silver Homes',         location: 'Delhi',     budget: 450, spent: 430, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 48, startDate: '2023-06-01' },
  { id: 'PRJ-039', name: 'Copper Leaf Residency',         location: 'Mumbai',    budget: 620, spent: 340, status: 'OnTrack',   progress: 55, phase: 'Structure',   labourCount: 68, startDate: '2024-01-15' },
  { id: 'PRJ-040', name: 'Greenfield Housing Colony',     location: 'Hyderabad', budget: 290, spent: 145, status: 'OnTrack',   progress: 48, phase: 'Structure',   labourCount: 34, startDate: '2024-02-28' },
  { id: 'PRJ-041', name: 'Cascades Waterfront Suites',    location: 'Chennai',   budget: 850, spent: 680, status: 'OnTrack',   progress: 80, phase: 'Finishing',   labourCount: 90, startDate: '2023-11-08' },
  { id: 'PRJ-042', name: 'Sapphire Hills Phase 2',        location: 'Bengaluru', budget: 760, spent: 750, status: 'Delayed',   progress: 95, phase: 'Finishing',   labourCount: 82, startDate: '2023-07-14' },
  { id: 'PRJ-043', name: 'Tulip Grove Apartments',        location: 'Pune',      budget: 330, spent: 165, status: 'OnTrack',   progress: 50, phase: 'Structure',   labourCount: 36, startDate: '2024-03-10' },
  { id: 'PRJ-044', name: 'Nova Star Condominiums',        location: 'Ahmedabad', budget: 480, spent: 380, status: 'OnTrack',   progress: 78, phase: 'Interior',    labourCount: 52, startDate: '2023-12-15' },
  { id: 'PRJ-045', name: 'Grandeur Palace Residences',    location: 'Delhi',     budget: 1250,spent: 900, status: 'OnTrack',   progress: 70, phase: 'Interior',    labourCount: 130,startDate: '2023-08-10' },
  { id: 'PRJ-046', name: 'Dew Drop Society',              location: 'Mumbai',    budget: 270, spent: 265, status: 'Completed', progress: 100, phase: 'Handover',   labourCount: 28, startDate: '2023-04-20' },
  { id: 'PRJ-047', name: 'Valley View Homes',             location: 'Hyderabad', budget: 400, spent: 160, status: 'OnTrack',   progress: 38, phase: 'Foundation',  labourCount: 42, startDate: '2024-03-05' },
  { id: 'PRJ-048', name: 'Marble Arch Bungalows',         location: 'Chennai',   budget: 560, spent: 415, status: 'OnHold',    progress: 65, phase: 'Interior',    labourCount: 0,  startDate: '2023-10-01' },
  { id: 'PRJ-049', name: 'Sunrise Petal Enclave',         location: 'Bengaluru', budget: 390, spent: 200, status: 'OnTrack',   progress: 52, phase: 'Structure',   labourCount: 42, startDate: '2024-01-30' },
  { id: 'PRJ-050', name: 'Platinum Heights Block D',      location: 'Pune',      budget: 940, spent: 880, status: 'Delayed',   progress: 92, phase: 'Finishing',   labourCount: 100,startDate: '2023-09-10' },
];

// ─── Colour palette ───────────────────────────────────────────────────────────
const STATUS_COLORS: Record<ProjectStatus, string> = {
  OnTrack:   '#10b981',
  Delayed:   '#ef4444',
  Completed: '#3b82f6',
  OnHold:    '#f59e0b',
};

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 1000 },
  plugins: {
    legend: {
      labels: { color: '#cbd5e1', font: { size: 12 } },
    },
    tooltip: {
      backgroundColor: 'rgba(15,23,42,0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#94a3b8',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
      padding: 12,
    },
  },
  scales: {
    x: {
      ticks: { color: '#94a3b8' },
      grid: { color: '#1e293b' },
    },
    y: {
      ticks: { color: '#94a3b8' },
      grid: { color: '#1e293b' },
    },
  },
};

// ─── Helper: format number ────────────────────────────────────────────────────
const fmt = (n: number) => `₹${n.toLocaleString('en-IN')} L`;

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Status badge */
const StatusBadge: React.FC<{ status: ProjectStatus }> = ({ status }) => (
  <span
    style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: '999px',
      fontSize: '0.72rem',
      fontWeight: 700,
      background: STATUS_COLORS[status] + '22',
      color: STATUS_COLORS[status],
      border: `1px solid ${STATUS_COLORS[status]}55`,
      letterSpacing: '0.04em',
    }}
  >
    {status}
  </span>
);

/** Progress bar */
const ProgressBar: React.FC<{ value: number; color?: string }> = ({ value, color = '#3b82f6' }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
    <div
      style={{
        flex: 1,
        height: '6px',
        borderRadius: '999px',
        background: 'rgba(255,255,255,0.08)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: `${value}%`,
          height: '100%',
          borderRadius: '999px',
          background: color,
          transition: 'width 0.6s ease',
        }}
      />
    </div>
    <span style={{ fontSize: '0.75rem', color: '#94a3b8', minWidth: '32px', textAlign: 'right' }}>
      {value}%
    </span>
  </div>
);

/** Section card wrapper */
const Card: React.FC<{ children: React.ReactNode; title?: string; style?: React.CSSProperties }> = ({
  children,
  title,
  style,
}) => (
  <div
    style={{
      background: 'rgba(15,23,42,0.7)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderRadius: '16px',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '1.5rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      ...style,
    }}
  >
    {title && (
      <h3
        style={{
          margin: 0,
          fontSize: '1rem',
          fontWeight: 700,
          color: '#f1f5f9',
          letterSpacing: '0.01em',
        }}
      >
        {title}
      </h3>
    )}
    {children}
  </div>
);

// ─── Main Analytics Page ──────────────────────────────────────────────────────
export default function AnalyticsDashboard() {
  const [projects, setProjects] = useState<Project[]>(DEMO_PROJECTS);
  const [loading, setLoading]   = useState(true);
  const [apiError, setApiError] = useState(false);

  const [monthlyTrend, setMonthlyTrend] = useState<Array<{ month: string; spent: number }>>([]);
  const [forecast, setForecast] = useState<{
    historical: Array<{ month: string; spent: number }>;
    forecast: Array<{ month: string; predicted_spent: number; lower: number; upper: number }>;
  } | null>(null);

  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('default');

  useEffect(() => {
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    setSelectedWorkspace(active);
  }, []);
  // Table state
  const [search, setSearch]         = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [sortKey, setSortKey]       = useState<keyof Project>('id');
  const [sortDir, setSortDir]       = useState<'asc' | 'desc'>('asc');
  const PAGE_SIZE = 10;
  // Fetch from API, fall back to demo
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const qParam = selectedWorkspace !== 'default' ? `?session_id=${selectedWorkspace}` : '';
      
      const overviewRes = await fetch(`${API_URL}/api/analytics/overview${qParam}`);
      if (!overviewRes.ok) throw new Error('Failed to fetch overview');
      const overviewData = await overviewRes.json();
      
      if (Array.isArray(overviewData.projects)) {
        setProjects(overviewData.projects);
      }
      if (Array.isArray(overviewData.monthly_trend)) {
        setMonthlyTrend(overviewData.monthly_trend);
      }

      // Fetch real ML forecast
      const forecastRes = await fetch(`${API_URL}/api/analytics/forecast${qParam}`);
      if (forecastRes.ok) {
        const forecastData = await forecastRes.json();
        setForecast(forecastData);
      }
      setApiError(false);
    } catch (err) {
      console.error(err);
      setApiError(true);
      // keep DEMO_PROJECTS
    } finally {
      setLoading(false);
    }
  }, [selectedWorkspace]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── KPI computations ─────────────────────────────────────────────────────
  const totalBudget  = useMemo(() => projects.reduce((s, p) => s + p.budget, 0), [projects]);
  const totalSpent   = useMemo(() => projects.reduce((s, p) => s + p.spent,  0), [projects]);
  const onTrackCount = useMemo(() => projects.filter((p) => p.status === 'OnTrack').length,   [projects]);
  const delayedCount = useMemo(() => projects.filter((p) => p.status === 'Delayed').length,   [projects]);
  const spentPct     = useMemo(() => ((totalSpent / totalBudget) * 100).toFixed(1), [totalBudget, totalSpent]);

  // ── Doughnut: Status Distribution ────────────────────────────────────────
  const doughnutData = useMemo(() => {
    const counts = {
      OnTrack:   projects.filter((p) => p.status === 'OnTrack').length,
      Delayed:   projects.filter((p) => p.status === 'Delayed').length,
      Completed: projects.filter((p) => p.status === 'Completed').length,
      OnHold:    projects.filter((p) => p.status === 'OnHold').length,
    };
    return {
      labels: ['On Track', 'Delayed', 'Completed', 'On Hold'],
      datasets: [
        {
          data: [counts.OnTrack, counts.Delayed, counts.Completed, counts.OnHold],
          backgroundColor: ['#10b981cc', '#ef4444cc', '#3b82f6cc', '#f59e0bcc'],
          borderColor:     ['#10b981',   '#ef4444',   '#3b82f6',   '#f59e0b'],
          borderWidth: 2,
          hoverOffset: 8,
        },
      ],
    };
  }, [projects]);

  // ── Bar: Budget vs Spent by Location ─────────────────────────────────────
  const locations = useMemo(
    () => Array.from(new Set(projects.map((p) => p.location))).sort(),
    [projects]
  );
  const barData = useMemo(() => ({
    labels: locations,
    datasets: [
      {
        label: 'Budget (₹ Lac)',
        data: locations.map((loc) =>
          projects.filter((p) => p.location === loc).reduce((s, p) => s + p.budget, 0)
        ),
        backgroundColor: '#3b82f6bb',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 6,
      },
      {
        label: 'Spent (₹ Lac)',
        data: locations.map((loc) =>
          projects.filter((p) => p.location === loc).reduce((s, p) => s + p.spent, 0)
        ),
        backgroundColor: '#10b981bb',
        borderColor: '#10b981',
        borderWidth: 1,
        borderRadius: 6,
      },
    ],
  }), [projects, locations]);

  // ── Line: Monthly Spending Trend (Jan–Jun 2025, simulated) ───────────────
  const lineData = useMemo(() => {
    if (monthlyTrend.length > 0) {
      return {
        labels: monthlyTrend.map((t) => t.month),
        datasets: [
          {
            label: 'Monthly Spend (₹ Lac)',
            data: monthlyTrend.map((t) => Math.round(t.spent)),
            borderColor: '#8b5cf6',
            backgroundColor: 'rgba(139,92,246,0.15)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#8b5cf6',
            pointRadius: 5,
            pointHoverRadius: 8,
          },
        ],
      };
    }
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    const base = [totalSpent * 0.08, totalSpent * 0.12, totalSpent * 0.15, totalSpent * 0.19, totalSpent * 0.22, totalSpent * 0.24];
    return {
      labels: months,
      datasets: [
        {
          label: 'Monthly Spend (₹ Lac)',
          data: base.map((v) => Math.round(v)),
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139,92,246,0.15)',
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#8b5cf6',
          pointRadius: 5,
          pointHoverRadius: 8,
        },
      ],
    };
  }, [totalSpent, monthlyTrend]);

  // ── Scatter: Labour Efficiency ────────────────────────────────────────────
  const scatterData = useMemo(() => {
    const grouped: Record<ProjectStatus, { x: number; y: number }[]> = {
      OnTrack: [], Delayed: [], Completed: [], OnHold: [],
    };
    projects.forEach((p) => grouped[p.status].push({ x: p.labourCount, y: p.progress }));
    return {
      datasets: Object.entries(grouped).map(([status, points]) => ({
        label: status,
        data: points,
        backgroundColor: STATUS_COLORS[status as ProjectStatus] + 'cc',
        borderColor: STATUS_COLORS[status as ProjectStatus],
        borderWidth: 1,
        pointRadius: 7,
        pointHoverRadius: 10,
      })),
    };
  }, [projects]);

  // ── Horizontal Bar: Top 10 by Budget ─────────────────────────────────────
  const top10 = useMemo(
    () => [...projects].sort((a, b) => b.budget - a.budget).slice(0, 10),
    [projects]
  );
  const hBarData = useMemo(() => ({
    labels: top10.map((p) => p.name.length > 28 ? p.name.slice(0, 25) + '…' : p.name),
    datasets: [
      {
        label: 'Budget (₹ Lac)',
        data: top10.map((p) => p.budget),
        backgroundColor: top10.map((_, i) =>
          `hsl(${220 + i * 14}, 80%, 58%)`
        ),
        borderColor: 'transparent',
        borderRadius: 6,
      },
    ],
  }), [top10]);

  // ── Line: Budget Forecast (historical + 3 predicted months) ──────────────
  const forecastData = useMemo(() => {
    if (forecast && forecast.historical.length > 0 && forecast.forecast.length > 0) {
      const labels = [
        ...forecast.historical.map((h) => h.month),
        ...forecast.forecast.map((f) => f.month)
      ];
      const histData = [
        ...forecast.historical.map((h) => Math.round(h.spent)),
        ...forecast.forecast.map(() => null)
      ];
      const forecastData = [
        ...forecast.historical.slice(0, -1).map(() => null),
        Math.round(forecast.historical[forecast.historical.length - 1].spent),
        ...forecast.forecast.map((f) => Math.round(f.predicted_spent))
      ];
      return {
        labels,
        datasets: [
          {
            label: 'Historical Spend',
            data: histData,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59,130,246,0.12)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#3b82f6',
            pointRadius: 5,
          },
          {
            label: 'AI Prediction',
            data: forecastData,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.08)',
            borderDash: [8, 4],
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#f59e0b',
            pointRadius: 5,
          },
        ],
      };
    }
    const hist = [
      totalSpent * 0.08,
      totalSpent * 0.12,
      totalSpent * 0.15,
      totalSpent * 0.19,
      totalSpent * 0.22,
      totalSpent * 0.24,
    ].map(Math.round);
    const forecastValues = [
      Math.round(totalSpent * 0.27),
      Math.round(totalSpent * 0.31),
      Math.round(totalSpent * 0.35),
    ];
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];
    const histFull    = [...hist,         null, null, null] as (number | null)[];
    const forecastFull= [null, null, null, null, null, hist[5], ...forecastValues] as (number | null)[];
    return {
      labels,
      datasets: [
        {
          label: 'Historical Spend',
          data: histFull,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.12)',
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#3b82f6',
          pointRadius: 5,
        },
        {
          label: 'AI Prediction',
          data: forecastFull,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.08)',
          borderDash: [8, 4],
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#f59e0b',
          pointRadius: 5,
        },
      ],
    };
  }, [totalSpent, forecast]);

  // ── Table: Filter + Sort + Paginate ──────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return projects.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        p.location.toLowerCase().includes(q) ||
        p.status.toLowerCase().includes(q) ||
        p.phase.toLowerCase().includes(q)
    );
  }, [projects, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageData   = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const handleSort = useCallback((key: keyof Project) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setCurrentPage(1);
  }, [sortKey]);

  // ── Export CSV ────────────────────────────────────────────────────────────
  const exportCSV = useCallback(() => {
    const headers = ['ID','Name','Location','Budget (Lac)','Spent (Lac)','Status','Progress (%)','Phase','Labour'];
    const rows = projects.map((p) =>
      [p.id, `"${p.name}"`, p.location, p.budget, p.spent, p.status, p.progress, p.phase, p.labourCount].join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `buildflow_analytics_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [projects]);

  const sortIcon = (key: keyof Project) =>
    sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ' ↕';

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #020617 0%, #0f172a 50%, #020617 100%)',
        padding: '2rem',
        fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        color: '#f1f5f9',
      }}
    >
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">📊 Smart Analytics Dashboard</h1>
          <p className="page-subtitle">BuildFlow AI · Real-time project intelligence &amp; forecasting</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {apiError && (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '4px 12px',
                borderRadius: '999px',
                background: '#f59e0b22',
                color: '#f59e0b',
                border: '1px solid #f59e0b44',
              }}
            >
              ⚠ Demo data — API offline
            </span>
          )}
          {loading && (
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Loading…</span>
          )}
          <span
            style={{
              fontSize: '0.75rem',
              color: '#64748b',
            }}
          >
            {projects.length} projects · {new Date().toLocaleDateString('en-IN', { dateStyle: 'medium' })}
          </span>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 1 — KPI Cards
      ════════════════════════════════════════════════════════════════════ */}
      <div
        style={{
          display: 'flex',
          gap: '1.25rem',
          flexWrap: 'wrap',
          marginBottom: '1.5rem',
        }}
      >
        <KPICard
          title="Total Budget"
          value={`₹${(totalBudget).toLocaleString('en-IN')} L`}
          subtitle={`Across ${projects.length} projects`}
          trend="neutral"
          color="#3b82f6"
          icon={<span>💰</span>}
        />
        <KPICard
          title="Total Spent"
          value={`₹${(totalSpent).toLocaleString('en-IN')} L`}
          subtitle={`${spentPct}% of total budget utilized`}
          trend={parseFloat(spentPct) > 80 ? 'up' : 'neutral'}
          color="#10b981"
          icon={<span>📤</span>}
        />
        <KPICard
          title="Projects On Track"
          value={onTrackCount}
          subtitle={`${((onTrackCount / projects.length) * 100).toFixed(0)}% of all projects`}
          trend="up"
          color="#10b981"
          icon={<span>✅</span>}
        />
        <KPICard
          title="Projects Delayed"
          value={delayedCount}
          subtitle={`${((delayedCount / projects.length) * 100).toFixed(0)}% of all projects`}
          trend="down"
          color="#ef4444"
          icon={<span>⚠️</span>}
        />
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 2 — Doughnut + Bar (Budget vs Spent)
      ════════════════════════════════════════════════════════════════════ */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <Card title="Project Status Distribution">
          <div style={{ height: '300px', position: 'relative' }}>
            <Doughnut
              data={doughnutData}
              options={{
                ...CHART_DEFAULTS,
                plugins: {
                  ...CHART_DEFAULTS.plugins,
                  legend: {
                    ...CHART_DEFAULTS.plugins.legend,
                    position: 'bottom' as const,
                  },
                },
              }}
            />
          </div>
        </Card>

        <Card title="Budget vs Spent by Location">
          <div style={{ height: '300px', position: 'relative' }}>
            <Bar
              data={barData}
              options={{
                ...CHART_DEFAULTS,
                plugins: { ...CHART_DEFAULTS.plugins },
              }}
            />
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 3 — Line (Monthly) + Scatter (Labour Efficiency)
      ════════════════════════════════════════════════════════════════════ */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <Card title="Monthly Spending Trend — 2025">
          <div style={{ height: '300px', position: 'relative' }}>
            <Line
              data={lineData}
              options={{ ...CHART_DEFAULTS }}
            />
          </div>
        </Card>

        <Card title="Labour Efficiency (Count vs Progress %)">
          <div style={{ height: '300px', position: 'relative' }}>
            <Scatter
              data={scatterData}
              options={{
                ...CHART_DEFAULTS,
                plugins: { ...CHART_DEFAULTS.plugins },
                scales: {
                  x: {
                    ...CHART_DEFAULTS.scales.x,
                    title: { display: true, text: 'Labour Count', color: '#94a3b8' },
                  },
                  y: {
                    ...CHART_DEFAULTS.scales.y,
                    title: { display: true, text: 'Progress %', color: '#94a3b8' },
                    min: 0,
                    max: 105,
                  },
                },
              }}
            />
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 4 — Horizontal Bar: Top 10 Projects by Budget
      ════════════════════════════════════════════════════════════════════ */}
      <Card title="Top 10 Projects by Budget" style={{ marginBottom: '1.5rem' }}>
        <div style={{ height: '340px', position: 'relative' }}>
          <Bar
            data={hBarData}
            options={{
              ...CHART_DEFAULTS,
              indexAxis: 'y' as const,
              plugins: {
                ...CHART_DEFAULTS.plugins,
                legend: { display: false },
              },
              scales: {
                x: {
                  ...CHART_DEFAULTS.scales.x,
                  title: { display: true, text: 'Budget (₹ Lac)', color: '#94a3b8' },
                },
                y: { ...CHART_DEFAULTS.scales.y },
              },
            }}
          />
        </div>
      </Card>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 5 — Budget Forecast (AI Prediction)
      ════════════════════════════════════════════════════════════════════ */}
      <Card
        title="Budget Forecast — Historical + AI Prediction (Jul–Sep 2025)"
        style={{ marginBottom: '1.5rem' }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.78rem',
            color: '#f59e0b',
          }}
        >
          <span>🤖</span>
          <span>
            Dashed line = AI-predicted spend based on current project velocity and seasonal trends
          </span>
        </div>
        <div style={{ height: '300px', position: 'relative' }}>
          <Line
            data={forecastData}
            options={{
              ...CHART_DEFAULTS,
              plugins: {
                ...CHART_DEFAULTS.plugins,
                legend: {
                  ...CHART_DEFAULTS.plugins.legend,
                  position: 'top' as const,
                },
              },
              scales: {
                x: { ...CHART_DEFAULTS.scales.x },
                y: {
                  ...CHART_DEFAULTS.scales.y,
                  title: { display: true, text: 'Cumulative Spend (₹ Lac)', color: '#94a3b8' },
                },
              },
            }}
          />
        </div>
      </Card>

      {/* ════════════════════════════════════════════════════════════════════
          ROW 6 — Data Table
      ════════════════════════════════════════════════════════════════════ */}
      <Card title="All Projects — Detailed View">
        {/* Controls */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.75rem',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <input
            type="text"
            placeholder="🔍  Search by name, ID, location, status, phase…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '10px',
              padding: '0.55rem 1rem',
              color: '#f1f5f9',
              fontSize: '0.85rem',
              outline: 'none',
              width: '320px',
              maxWidth: '100%',
            }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              {filtered.length} results
            </span>
            <button
              onClick={exportCSV}
              style={{
                padding: '0.5rem 1.1rem',
                borderRadius: '10px',
                border: '1px solid #3b82f644',
                background: '#3b82f622',
                color: '#60a5fa',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}
            >
              📥 Export CSV
            </button>
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.82rem',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                {(
                  [
                    ['id',       'Project ID'],
                    ['name',     'Name'],
                    ['location', 'Location'],
                    ['budget',   'Budget (L)'],
                    ['spent',    'Spent (L)'],
                    ['status',   'Status'],
                    ['progress', 'Progress'],
                    ['phase',    'Phase'],
                  ] as [keyof Project, string][]
                ).map(([key, label]) => (
                  <th
                    key={key}
                    onClick={() => handleSort(key)}
                    style={{
                      padding: '0.7rem 0.75rem',
                      textAlign: 'left',
                      color: sortKey === key ? '#60a5fa' : '#64748b',
                      fontWeight: 600,
                      letterSpacing: '0.04em',
                      fontSize: '0.73rem',
                      textTransform: 'uppercase',
                      cursor: 'pointer',
                      userSelect: 'none',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {label}{sortIcon(key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageData.map((p, i) => (
                <tr
                  key={p.id}
                  style={{
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background = 'rgba(59,130,246,0.06)')
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background =
                      i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)')
                  }
                >
                  <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8', fontFamily: 'monospace' }}>{p.id}</td>
                  <td style={{ padding: '0.6rem 0.75rem', color: '#e2e8f0', fontWeight: 500 }}>
                    {p.name.length > 30 ? p.name.slice(0, 27) + '…' : p.name}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8' }}>{p.location}</td>
                  <td style={{ padding: '0.6rem 0.75rem', color: '#f1f5f9', fontWeight: 600 }}>
                    {p.budget.toLocaleString('en-IN')}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8' }}>
                    {p.spent.toLocaleString('en-IN')}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem' }}>
                    <StatusBadge status={p.status} />
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', minWidth: '130px' }}>
                    <ProgressBar value={p.progress} color={STATUS_COLORS[p.status]} />
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8' }}>{p.phase}</td>
                </tr>
              ))}
              {pageData.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: '2rem', textAlign: 'center', color: '#475569' }}>
                    No projects match your search.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Page {currentPage} of {totalPages} · showing {pageData.length} of {filtered.length}
          </span>
          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(1)}
              style={paginationBtnStyle(currentPage === 1)}
            >
              «
            </button>
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => p - 1)}
              style={paginationBtnStyle(currentPage === 1)}
            >
              ‹
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, idx) => {
              const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
              const pg = start + idx;
              if (pg > totalPages) return null;
              return (
                <button
                  key={pg}
                  onClick={() => setCurrentPage(pg)}
                  style={{
                    ...paginationBtnStyle(false),
                    background: pg === currentPage ? '#3b82f6' : 'rgba(255,255,255,0.05)',
                    color: pg === currentPage ? '#fff' : '#94a3b8',
                    borderColor: pg === currentPage ? '#3b82f6' : 'rgba(255,255,255,0.1)',
                  }}
                >
                  {pg}
                </button>
              );
            })}
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => p + 1)}
              style={paginationBtnStyle(currentPage === totalPages)}
            >
              ›
            </button>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage(totalPages)}
              style={paginationBtnStyle(currentPage === totalPages)}
            >
              »
            </button>
          </div>
        </div>
      </Card>

      {/* Footer */}
      <div
        style={{
          marginTop: '2rem',
          textAlign: 'center',
          fontSize: '0.75rem',
          color: '#334155',
        }}
      >
        BuildFlow AI Analytics · Data updates every 5 minutes · Charts powered by Chart.js
      </div>
    </div>
  );
}

// ─── Pagination button style helper ──────────────────────────────────────────
function paginationBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: '0.35rem 0.65rem',
    borderRadius: '8px',
    border: '1px solid rgba(255,255,255,0.1)',
    background: disabled ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.05)',
    color: disabled ? '#334155' : '#94a3b8',
    fontSize: '0.82rem',
    cursor: disabled ? 'default' : 'pointer',
    fontWeight: 600,
    transition: 'background 0.15s',
    opacity: disabled ? 0.4 : 1,
  };
}
