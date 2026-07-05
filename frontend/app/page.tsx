'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';

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

export default function DashboardPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await uploadFile(e.target.files[0]);
    }
  };

  const uploadFile = async (file: File) => {
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    if (fileExt !== 'csv' && fileExt !== 'xlsx' && fileExt !== 'xls') {
      setUploadStatus({
        type: 'error',
        message: 'Unsupported format. Please upload a .xlsx, .xls, or .csv file.'
      });
      return;
    }

    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append('file', file);

    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    try {
      const res = await fetch(`${API_URL}/api/analytics/upload?session_id=${active}`, {
        method: 'POST',
        body: formData,
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to upload database file');
      }

      setUploadStatus({
        type: 'success',
        message: result.message || 'Database loaded successfully!'
      });

      // Reload dashboard metrics
      const overviewRes = await fetch(`${API_URL}/api/analytics/overview?session_id=${active}`);
      if (overviewRes.ok) {
        const json = await overviewRes.json();
        setData(json);
      }
    } catch (err: any) {
      console.error(err);
      setUploadStatus({
        type: 'error',
        message: err.message || 'Connection to backend failed.'
      });
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    const fetchOverview = async () => {
      const active = localStorage.getItem('buildflow_active_workspace') || 'default';
      try {
        const res = await fetch(`${API_URL}/api/analytics/overview?session_id=${active}`);
        if (!res.ok) throw new Error('API error');
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error('Failed to fetch overview data from backend:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchOverview();
  }, []);

  // fallback values if backend is offline or loading
  const totalProjects = data?.total_projects ?? 50;
  const delayedProjects = data?.delayed_count ?? 12;
  const onTrackProjects = data?.on_track_count ?? 32;
  const avgProgress = data?.avg_progress ?? 68;
  const projectList = data?.projects?.slice(0, 5) ?? [];

  const stats = [
    {
      label: 'Total Projects',
      value: totalProjects,
      desc: 'Active contracts in database',
      color: '#3b82f6',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        </svg>
      ),
    },
    {
      label: 'On Track',
      value: onTrackProjects,
      desc: 'Projects meeting deadlines',
      color: '#10b981',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M8 12l3 3 5-5" />
        </svg>
      ),
    },
    {
      label: 'Schedule Delays',
      value: delayedProjects,
      desc: 'Flagged with active delays',
      color: '#ef4444',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" fill="none" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
    },
    {
      label: 'Average Progress',
      value: `${avgProgress.toFixed(0)}%`,
      desc: 'Overall project completion rate',
      color: '#8b5cf6',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
  ];

  return (
    <div className="page-container">
      {/* Hero / Banner */}
      <section className="hero-section glass">
        <div className="hero-content">
          <div className="system-badge">
            <span className="badge-dot" />
            BuildFlow AI Construction Portal
          </div>
          <h1>
            BuildFlow <span className="gradient-text">AI</span>
          </h1>
          <p>
            Real-time operations management for construction projects. Query project data, generate contract documentation, and run budget forecasts on unified project records.
          </p>
          <div className="hero-actions">
            <Link href="/chat" className="btn-primary">
              Launch Assistant
            </Link>
            <Link href="/analytics" className="btn-secondary">
              View Analytics
            </Link>
          </div>
        </div>

        {/* Excel / CSV Dropzone Section */}
        <div 
          className={`dropzone glass ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => document.getElementById('excel-file-input')?.click()}
        >
          <input 
            type="file" 
            id="excel-file-input" 
            style={{ display: 'none' }} 
            accept=".xlsx, .xls, .csv"
            onChange={handleFileChange}
          />
          {uploading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <div className="spinner"></div>
              <span className="dropzone-title" style={{ marginTop: '8px' }}>Parsing database...</span>
            </div>
          ) : (
            <>
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue-light)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <div className="dropzone-title">Drag &amp; Drop Excel or CSV here</div>
              <div className="dropzone-desc">Supports .xlsx, .xls, and .csv formats</div>
            </>
          )}
          {uploadStatus && (
            <div className={`upload-alert ${uploadStatus.type}`} onClick={(e) => e.stopPropagation()}>
              {uploadStatus.type === 'success' ? '✅' : '❌'} {uploadStatus.message}
            </div>
          )}
        </div>
      </section>

      {/* Stats Row */}
      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        {stats.map((s, idx) => (
          <div key={idx} className="glass stat-card-simple" style={{ borderLeft: `4px solid ${s.color}` }}>
            <div className="stat-card-header">
              <span className="stat-card-label">{s.label}</span>
              <span className="stat-card-icon" style={{ color: s.color }}>{s.icon}</span>
            </div>
            <div className="stat-card-value">{s.value}</div>
            <div className="stat-card-desc">{s.desc}</div>
          </div>
        ))}
      </div>

      {/* Quick Navigation Cards */}
      <section style={{ marginBottom: '2.5rem' }}>
        <div className="section-header">
          <h2 className="section-title">Operations Workspaces</h2>
        </div>
        <div className="grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', alignItems: 'stretch' }}>
          <Link href="/chat" className="nav-card glass">
            <div className="nav-card-icon-wrapper cyan">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                <path d="M8 10h8" />
                <path d="M8 14h5" />
              </svg>
            </div>
            <h3>RAG Assistant</h3>
            <p>Query project specs, status updates, material usage, and resource requirements directly from records.</p>
            <span className="nav-card-link">Open Workspace &rarr;</span>
          </Link>
          <Link href="/docgen" className="nav-card glass">
            <div className="nav-card-icon-wrapper purple">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <h3>Document Generator</h3>
            <p>Generate professional PDF construction contracts, work orders, site reports, and tax invoices.</p>
            <span className="nav-card-link">Open Workspace &rarr;</span>
          </Link>
          <Link href="/agents" className="nav-card glass">
            <div className="nav-card-icon-wrapper blue">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="5" r="3" />
                <circle cx="4" cy="19" r="3" />
                <circle cx="20" cy="19" r="3" />
                <path d="M12 8v4" />
                <path d="M7 17l-2.5-3.5" />
                <path d="M17 17l2.5-3.5" />
              </svg>
            </div>
            <h3>Multi-Agent Orchestrator</h3>
            <p>Trigger automated operational pipelines using sequential Planning, Analytics, DocGen, and Notification agents.</p>
            <span className="nav-card-link">Open Workspace &rarr;</span>
          </Link>
        </div>
      </section>

      {/* Excel / CSV Dropzone Section */}


      {/* Projects Table */}
      {projectList.length > 0 && (
        <section style={{ marginBottom: '2rem' }}>
          <div className="card glass">
            <div className="card-header">
              <h2 className="section-title">Active Projects Overview</h2>
              <Link href="/analytics" className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                View Full Dataset
              </Link>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Project ID</th>
                    <th>Project Name</th>
                    <th>Location</th>
                    <th>Phase</th>
                    <th>Budget</th>
                    <th>Progress</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {projectList.map((p) => (
                    <tr key={p.id}>
                      <td style={{ fontWeight: '700', fontFamily: 'monospace' }}>{p.id}</td>
                      <td style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{p.name}</td>
                      <td>{p.location}</td>
                      <td>{p.phase}</td>
                      <td style={{ fontWeight: '600' }}>₹{p.budget} Lac</td>
                      <td style={{ width: '180px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div className="progress-bar" style={{ flex: 1, height: '6px' }}>
                            <div
                              className="progress-fill"
                              style={{
                                width: `${p.progress}%`,
                                background: p.status === 'OnTrack' ? 'var(--accent-green)' : p.status === 'Delayed' ? 'var(--accent-red)' : 'var(--accent-orange)',
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '0.78rem', minWidth: '30px' }}>{p.progress.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            p.status === 'OnTrack' ? 'badge-success' : p.status === 'Delayed' ? 'badge-danger' : 'badge-warning'
                          }`}
                        >
                          {p.status === 'OnTrack' ? 'On Track' : p.status === 'Delayed' ? 'Delayed' : p.status}
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

      <style jsx>{`
        .hero-section {
          padding: 3rem 2.5rem;
          border-radius: var(--radius-lg);
          margin-bottom: 2rem;
          background: linear-gradient(135deg, rgba(17,24,39,0.7) 0%, rgba(10,14,26,0.9) 100%);
          display: grid;
          grid-template-columns: 1.15fr 0.85fr;
          gap: 3rem;
          align-items: center;
        }
        @media (max-width: 900px) {
          .hero-section {
            grid-template-columns: 1fr;
            gap: 2.5rem;
            padding: 2.5rem 2rem;
          }
        }
        .hero-content h1 {
          font-size: 2.5rem;
          font-weight: 800;
          margin: 0.75rem 0;
          color: var(--text-primary);
        }
        .hero-content p {
          color: var(--text-secondary);
          max-width: 600px;
          line-height: 1.6;
          margin-bottom: 1.5rem;
        }
        .system-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 12px;
          background: rgba(59,130,246,0.1);
          border: 1px solid rgba(59,130,246,0.2);
          border-radius: var(--radius-full);
          font-size: 0.75rem;
          color: var(--accent-blue-light);
          font-weight: 600;
        }
        .badge-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent-blue);
          box-shadow: 0 0 6px var(--accent-blue);
        }
        .hero-actions {
          display: flex;
          gap: 12px;
        }
        .stat-card-simple {
          background: rgba(17,24,39,0.5);
          padding: 1.25rem;
          border-radius: 12px;
          border: 1px solid var(--border);
        }
        .stat-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.5rem;
        }
        .stat-card-label {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
        .stat-card-value {
          font-size: 1.75rem;
          font-weight: 800;
          color: var(--text-primary);
          line-height: 1.2;
        }
        .stat-card-desc {
          font-size: 0.7rem;
          color: var(--text-secondary);
          margin-top: 4px;
        }
        .nav-card {
          padding: 1.75rem;
          border-radius: 16px;
          text-decoration: none;
          color: inherit;
          display: flex;
          flex-direction: column;
          gap: 8px;
          background: rgba(30, 41, 59, 0.4);
          border: 1px solid rgba(255, 255, 255, 0.05);
          transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          height: 100%;
        }
        .nav-card:hover {
          background: rgba(30, 41, 59, 0.65);
          border-color: rgba(96, 165, 250, 0.4);
          transform: translateY(-3px);
          box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5), 0 0 20px rgba(59, 130, 246, 0.15);
        }
        .nav-card-icon-wrapper {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 6px;
          transition: all 0.2s;
        }
        .nav-card-icon-wrapper.cyan {
          background: rgba(6, 182, 212, 0.08);
          color: var(--accent-cyan-light);
          border: 1px solid rgba(6, 182, 212, 0.15);
        }
        .nav-card-icon-wrapper.purple {
          background: rgba(139, 92, 246, 0.08);
          color: var(--accent-purple-light);
          border: 1px solid rgba(139, 92, 246, 0.15);
        }
        .nav-card-icon-wrapper.blue {
          background: rgba(59, 130, 246, 0.08);
          color: var(--accent-blue-light);
          border: 1px solid rgba(59, 130, 246, 0.15);
        }
        .nav-card:hover .nav-card-icon-wrapper.cyan {
          background: rgba(6, 182, 212, 0.18);
          box-shadow: 0 0 12px rgba(6, 182, 212, 0.3);
        }
        .nav-card:hover .nav-card-icon-wrapper.purple {
          background: rgba(139, 92, 246, 0.18);
          box-shadow: 0 0 12px rgba(139, 92, 246, 0.3);
        }
        .nav-card:hover .nav-card-icon-wrapper.blue {
          background: rgba(59, 130, 246, 0.18);
          box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
        }
        .nav-card h3 {
          font-size: 1.08rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 4px 0;
          letter-spacing: -0.01em;
        }
        .nav-card p {
          font-size: 0.85rem;
          color: rgba(241, 245, 249, 0.7);
          line-height: 1.6;
          margin: 0 0 16px 0;
        }
        .nav-card-link {
          font-size: 0.82rem;
          font-weight: 600;
          color: var(--accent-blue-light);
          margin-top: auto;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: color 0.2s, transform 0.2s;
        }
        .nav-card:hover .nav-card-link {
          color: var(--accent-cyan-light);
          transform: translateX(4px);
        }
        .upload-section {
          margin-bottom: 2.5rem;
        }
        .dropzone {
          border: 2px dashed var(--border);
          border-radius: var(--radius-md);
          padding: 2rem 1.25rem;
          text-align: center;
          background: rgba(17, 24, 39, 0.45);
          cursor: pointer;
          transition: all var(--transition-base);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          outline: none;
        }
        .dropzone.active {
          border-color: var(--accent-blue);
          background: rgba(59, 130, 246, 0.1);
          box-shadow: var(--shadow-glow-blue);
        }
        .dropzone:hover {
          border-color: var(--accent-blue-light);
          background: rgba(255, 255, 255, 0.02);
        }
        .dropzone-title {
          font-size: 0.92rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .dropzone-desc {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }
        .upload-alert {
          margin-top: 1rem;
          padding: 0.75rem 1rem;
          border-radius: var(--radius-sm);
          font-size: 0.82rem;
          font-weight: 500;
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          max-width: 500px;
        }
        .upload-alert.success {
          background: rgba(16, 185, 129, 0.15);
          border: 1px solid rgba(16, 185, 129, 0.3);
          color: var(--accent-green-light);
        }
        .upload-alert.error {
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.3);
          color: var(--accent-red-light);
        }
        .spinner {
          width: 24px;
          height: 24px;
          border: 3px solid rgba(255, 255, 255, 0.1);
          border-radius: 50%;
          border-top-color: var(--accent-blue);
          animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
