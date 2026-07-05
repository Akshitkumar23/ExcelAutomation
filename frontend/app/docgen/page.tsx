'use client';

import { useState, useEffect } from 'react';

type DocType = 'CONTRACT' | 'INVOICE' | 'WORK_ORDER' | 'SITE_REPORT';

interface GeneratedDoc {
  doc_id: string;
  doc_type: string;
  preview_text: string;
  download_url: string;
  generated_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const DOC_TYPES = [
  { value: 'CONTRACT', label: 'Construction Contract', icon: '📋', desc: 'Legal agreement between contractor and client' },
  { value: 'INVOICE', label: 'Tax Invoice', icon: '🧾', desc: 'Billing document with GST calculation' },
  { value: 'WORK_ORDER', label: 'Work Order', icon: '🔧', desc: 'Task assignment with materials list' },
  { value: 'SITE_REPORT', label: 'Site Report', icon: '📊', desc: 'Daily progress and issue tracking' },
];

const DEFAULT_FORMS: Record<DocType, Record<string, string | number | string[]>> = {
  CONTRACT: {
    project_name: 'Sector 62 Commercial Complex',
    client_name: 'Metro Infrastructure Ltd.',
    budget: 250,
    start_date: '2025-07-01',
    end_date: '2026-06-30',
    scope_of_work: 'Construction of 12-storey commercial complex including foundation, structural work, interior finishing, and MEP installations as per approved drawings.',
  },
  INVOICE: {
    invoice_number: 'INV-2025-001',
    client_name: 'ABC Corp',
    project_id: 'P1003',
    amount: 85,
    services: ['Structural Foundation Work', 'Concrete Pouring & Curing', 'Site Supervision'],
    due_date: '2025-08-15',
  },
  WORK_ORDER: {
    project_id: 'P1005',
    task_description: 'Complete RCC work for floors 3-5 including formwork, steel reinforcement binding, and concrete pouring as per structural drawings.',
    assigned_to: 'Rajesh Kumar — Senior Site Engineer',
    deadline: '2025-07-20',
    materials_required: ['Concrete M-30 Grade: 120 cu.m', 'TMT Steel Bars Fe-500: 8 MT', 'Shuttering Plates: 200 nos.'],
  },
  SITE_REPORT: {
    project_id: 'P1001',
    date: new Date().toISOString().split('T')[0],
    progress_percent: 65,
    issues: ['Delayed concrete delivery from supplier', 'Worker absenteeism ~15%'],
    completed_tasks: ['3rd floor slab casting completed', 'Staircase block formwork done', 'Safety audit passed'],
  },
};

function getFormFields(docType: DocType) {
  switch (docType) {
    case 'CONTRACT':
      return [
        { key: 'project_name', label: 'Project Name', type: 'text', required: true },
        { key: 'client_name', label: 'Client Name', type: 'text', required: true },
        { key: 'budget', label: 'Budget (₹ Lac)', type: 'number', required: true },
        { key: 'start_date', label: 'Start Date', type: 'date', required: true },
        { key: 'end_date', label: 'End Date', type: 'date', required: true },
        { key: 'scope_of_work', label: 'Scope of Work', type: 'textarea', required: true },
      ];
    case 'INVOICE':
      return [
        { key: 'invoice_number', label: 'Invoice Number', type: 'text', required: true },
        { key: 'client_name', label: 'Client Name', type: 'text', required: true },
        { key: 'project_id', label: 'Project ID', type: 'text', required: true },
        { key: 'amount', label: 'Amount (₹ Lac)', type: 'number', required: true },
        { key: 'services', label: 'Services (one per line)', type: 'textarea', required: false },
        { key: 'due_date', label: 'Due Date', type: 'date', required: true },
      ];
    case 'WORK_ORDER':
      return [
        { key: 'project_id', label: 'Project ID', type: 'text', required: true },
        { key: 'task_description', label: 'Task Description', type: 'textarea', required: true },
        { key: 'assigned_to', label: 'Assigned To', type: 'text', required: true },
        { key: 'deadline', label: 'Deadline', type: 'date', required: true },
        { key: 'materials_required', label: 'Materials Required (one per line)', type: 'textarea', required: false },
      ];
    case 'SITE_REPORT':
      return [
        { key: 'project_id', label: 'Project ID', type: 'text', required: true },
        { key: 'date', label: 'Report Date', type: 'date', required: true },
        { key: 'progress_percent', label: 'Progress (%)', type: 'number', required: true },
        { key: 'completed_tasks', label: 'Completed Tasks (one per line)', type: 'textarea', required: false },
        { key: 'issues', label: 'Issues / Observations (one per line)', type: 'textarea', required: false },
      ];
  }
}

export default function DocGenPage() {
  const [docType, setDocType] = useState<DocType>('CONTRACT');
  const [formData, setFormData] = useState<Record<string, unknown>>(DEFAULT_FORMS.CONTRACT as Record<string, unknown>);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState<GeneratedDoc | null>(null);
  const [recentDocs, setRecentDocs] = useState<GeneratedDoc[]>([]);
  const [error, setError] = useState('');

  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('default');

  useEffect(() => {
    const active = localStorage.getItem('buildflow_active_workspace') || 'default';
    setSelectedWorkspace(active);
  }, []);

  const handleDocTypeChange = (type: DocType) => {
    setDocType(type);
    setFormData(DEFAULT_FORMS[type] as Record<string, unknown>);
    setGeneratedDoc(null);
    setError('');
  };

  const handleFieldChange = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const prepareData = () => {
    const data: Record<string, unknown> = { ...formData };
    // Convert textarea newline-separated strings to arrays for array fields
    if (docType === 'INVOICE' && typeof data.services === 'string') {
      data.services = (data.services as string).split('\n').filter(Boolean);
    }
    if (docType === 'WORK_ORDER' && typeof data.materials_required === 'string') {
      data.materials_required = (data.materials_required as string).split('\n').filter(Boolean);
    }
    if (docType === 'SITE_REPORT') {
      if (typeof data.completed_tasks === 'string') {
        data.completed_tasks = (data.completed_tasks as string).split('\n').filter(Boolean);
      }
      if (typeof data.issues === 'string') {
        data.issues = (data.issues as string).split('\n').filter(Boolean);
      }
      if (data.progress_percent !== undefined) {
        data.progress_percent = parseFloat(data.progress_percent as string);
      }
    }
    if (data.budget !== undefined) data.budget = parseFloat(data.budget as string);
    if (data.amount !== undefined) data.amount = parseFloat(data.amount as string);
    return data;
  };

  const generateDocument = async () => {
    setIsGenerating(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/docgen/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          doc_type: docType, 
          data: prepareData(),
          session_id: selectedWorkspace !== 'default' ? selectedWorkspace : null
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const doc = await res.json() as GeneratedDoc;
      setGeneratedDoc(doc);
      setRecentDocs((prev) => [doc, ...prev.slice(0, 9)]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setError(`Generation failed: ${msg}. Make sure the backend is running.`);
      // Demo fallback
      const demoDoc: GeneratedDoc = {
        doc_id: 'demo-' + Date.now(),
        doc_type: docType,
        preview_text: `${docType} | Demo Mode | Backend not connected`,
        download_url: '#',
        generated_at: new Date().toISOString(),
      };
      setGeneratedDoc(demoDoc);
      setRecentDocs((prev) => [demoDoc, ...prev.slice(0, 9)]);
    } finally {
      setIsGenerating(false);
    }
  };

  const getFieldDisplayValue = (key: string, value: unknown): string => {
    if (Array.isArray(value)) return value.join('\n');
    return String(value ?? '');
  };

  const fields = getFormFields(docType);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">📄 Document Generator</h1>
          <p className="page-subtitle">AI-powered construction document generation with professional PDF output</p>
        </div>
      </div>

      {/* Doc Type Selector */}
      <div className="doc-type-grid">
        {DOC_TYPES.map((dt) => (
          <button
            key={dt.value}
            className={`doc-type-card ${docType === dt.value ? 'active' : ''}`}
            onClick={() => handleDocTypeChange(dt.value as DocType)}
            id={`doctype-${dt.value.toLowerCase()}`}
          >
            <span className="doc-type-icon">{dt.icon}</span>
            <span className="doc-type-label">{dt.label}</span>
            <span className="doc-type-desc">{dt.desc}</span>
          </button>
        ))}
      </div>

      <div className="docgen-layout">
        {/* Form */}
        <div className="docgen-form-panel glass">
          <div className="panel-header">
            <h3>Document Details</h3>
            <span className="badge badge-info">{DOC_TYPES.find(d => d.value === docType)?.label}</span>
          </div>
          <div className="form-fields-grid">
            {fields.map((field) => (
              <div className={`form-group ${field.type === 'textarea' ? 'full-width' : ''}`} key={field.key}>
                <label className="form-label">
                  {field.label}
                  {field.required && <span style={{ color: 'var(--accent-red)' }}> *</span>}
                </label>
                {field.type === 'textarea' ? (
                  <textarea
                    className="form-textarea"
                    id={`field-${field.key}`}
                    value={getFieldDisplayValue(field.key, formData[field.key])}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    rows={3}
                  />
                ) : (
                  <input
                    type={field.type}
                    className="form-input"
                    id={`field-${field.key}`}
                    value={getFieldDisplayValue(field.key, formData[field.key])}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                  />
                )}
              </div>
            ))}
          </div>
          <button
            className="btn-generate"
            onClick={generateDocument}
            disabled={isGenerating}
            id="generate-btn"
          >
            {isGenerating ? (
              <>
                <div className="btn-spinner" />
                Generating PDF...
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
                Generate Document
              </>
            )}
          </button>
        </div>

        {/* Preview */}
        <div className="docgen-preview-panel">
          <div className="glass preview-card">
            <div className="panel-header">
              <h3>Document Preview</h3>
              {generatedDoc && (
                <span className="badge badge-success">✓ Generated</span>
              )}
            </div>

            {error && (
              <div className="error-banner">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {error}
              </div>
            )}

            {generatedDoc ? (
              <div className="doc-preview">
                <div className="doc-preview-header">
                  <div className="doc-preview-icon">📄</div>
                  <div>
                    <div className="doc-preview-type">{generatedDoc.doc_type.replace('_', ' ')}</div>
                    <div className="doc-preview-id">ID: {generatedDoc.doc_id.slice(0, 12)}...</div>
                  </div>
                </div>
                <div className="doc-preview-content">
                  {generatedDoc.preview_text}
                </div>
                <div className="doc-preview-meta">
                  <span>Generated: {new Date(generatedDoc.generated_at).toLocaleString()}</span>
                </div>
                <a
                  href={`${API_URL}${generatedDoc.download_url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-download"
                  id="download-btn"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  Download PDF
                </a>
              </div>
            ) : (
              <div className="preview-empty">
                <div className="preview-empty-icon">📄</div>
                <p>Fill in the form and click <strong>Generate Document</strong> to create a professional PDF.</p>
                <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                  Powered by ReportLab • Supports Contract, Invoice, Work Order & Site Report
                </p>
              </div>
            )}
          </div>

          {/* Recent Docs */}
          {recentDocs.length > 0 && (
            <div className="glass recent-docs">
              <div className="panel-header">
                <h3>Recent Documents</h3>
                <span className="badge">{recentDocs.length}</span>
              </div>
              <div className="recent-docs-list">
                {recentDocs.map((doc) => (
                  <div key={doc.doc_id} className="recent-doc-item" id={`recent-${doc.doc_id.slice(0, 8)}`}>
                    <div className="recent-doc-info">
                      <span className="recent-doc-type">{doc.doc_type.replace('_', ' ')}</span>
                      <span className="recent-doc-time">{new Date(doc.generated_at).toLocaleTimeString()}</span>
                    </div>
                    <a href={`${API_URL}${doc.download_url}`} target="_blank" rel="noopener noreferrer" className="recent-doc-download">
                      ↓
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .page-header { margin-bottom: 2rem; }
        .page-title { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.5rem; }
        .page-subtitle { color: var(--text-secondary); margin: 0; }

        .doc-type-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 1rem;
          margin-bottom: 2rem;
        }
        .doc-type-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 1.25rem;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .doc-type-card:hover { background: rgba(255,255,255,0.07); transform: translateY(-2px); }
        .doc-type-card.active { border-color: var(--accent-blue); background: rgba(59,130,246,0.1); }
        .doc-type-icon { font-size: 1.5rem; }
        .doc-type-label { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
        .doc-type-desc { font-size: 0.72rem; color: var(--text-secondary); line-height: 1.4; }

        .docgen-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
        .docgen-form-panel { padding: 1.5rem; border-radius: 16px; }
        .docgen-preview-panel { display: flex; flex-direction: column; gap: 1rem; }
        .preview-card { padding: 1.5rem; border-radius: 16px; }
        .panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; }
        .panel-header h3 { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); margin: 0; }

        .form-fields { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-label { font-size: 0.8rem; font-weight: 500; color: var(--text-secondary); }
        .form-input, .form-textarea {
          background: rgba(255,255,255,0.05);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 10px 12px;
          color: var(--text-primary);
          font-size: 0.85rem;
          font-family: inherit;
          transition: border-color 0.2s;
          width: 100%;
          box-sizing: border-box;
        }
        .form-input:focus, .form-textarea:focus { outline: none; border-color: var(--accent-blue); }
        .form-textarea { resize: vertical; min-height: 80px; }
        input[type="date"] { color-scheme: dark; }

        .btn-generate {
          width: 100%;
          background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
          border: none;
          border-radius: 10px;
          color: white;
          padding: 12px 24px;
          font-size: 0.9rem;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: all 0.2s;
        }
        .btn-generate:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 15px rgba(59,130,246,0.4); }
        .btn-generate:disabled { opacity: 0.6; cursor: not-allowed; }
        .btn-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .error-banner {
          background: rgba(239,68,68,0.1);
          border: 1px solid rgba(239,68,68,0.3);
          color: #fca5a5;
          padding: 10px 14px;
          border-radius: 8px;
          font-size: 0.82rem;
          margin-bottom: 1rem;
          display: flex;
          align-items: flex-start;
          gap: 8px;
        }

        .doc-preview { display: flex; flex-direction: column; gap: 1rem; }
        .doc-preview-header { display: flex; align-items: center; gap: 1rem; }
        .doc-preview-icon { font-size: 2rem; }
        .doc-preview-type { font-size: 1rem; font-weight: 700; color: var(--text-primary); }
        .doc-preview-id { font-size: 0.75rem; color: var(--text-secondary); font-family: monospace; }
        .doc-preview-content {
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 1rem;
          font-size: 0.82rem;
          color: var(--text-secondary);
          line-height: 1.6;
        }
        .doc-preview-meta { font-size: 0.72rem; color: var(--text-secondary); }
        .btn-download {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: var(--accent-green);
          color: white;
          border-radius: 8px;
          padding: 10px 20px;
          font-size: 0.85rem;
          font-weight: 600;
          text-decoration: none;
          transition: all 0.2s;
          align-self: flex-start;
        }
        .btn-download:hover { opacity: 0.9; transform: translateY(-1px); }

        .preview-empty { text-align: center; padding: 3rem 1rem; color: var(--text-secondary); }
        .preview-empty-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.4; }
        .preview-empty p { margin: 0; font-size: 0.9rem; line-height: 1.6; }

        .recent-docs { padding: 1.25rem; border-radius: 16px; }
        .recent-docs-list { display: flex; flex-direction: column; gap: 0.5rem; }
        .recent-doc-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border);
          border-radius: 8px;
        }
        .recent-doc-info { display: flex; flex-direction: column; gap: 2px; }
        .recent-doc-type { font-size: 0.8rem; font-weight: 500; color: var(--text-primary); }
        .recent-doc-time { font-size: 0.7rem; color: var(--text-secondary); }
        .recent-doc-download {
          background: rgba(59,130,246,0.15);
          border: 1px solid rgba(59,130,246,0.3);
          color: var(--accent-blue);
          width: 28px; height: 28px;
          border-radius: 6px;
          display: flex; align-items: center; justify-content: center;
          text-decoration: none;
          font-size: 0.9rem;
          transition: all 0.2s;
        }
        .recent-doc-download:hover { background: var(--accent-blue); color: white; }
      `}</style>
    </div>
  );
}
