'use client';

import { useState, useRef, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type WorkflowType = 'full_project_setup' | 'daily_site_report' | 'contract_generation' | 'budget_analysis';
type AgentStatusType = 'idle' | 'running' | 'completed' | 'error';

interface AgentStatus {
  agent_name: string;
  status: AgentStatusType;
  output: string;
  timestamp: string;
}

interface RunStatus {
  run_id: string;
  workflow_type: string;
  project_id: string;
  status: string;
  agents: AgentStatus[];
  started_at: string;
  completed_at?: string;
  summary: string;
}

interface LogEntry {
  time: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
}

const WORKFLOW_OPTIONS = [
  {
    value: 'full_project_setup',
    label: 'Full Project Setup',
    desc: 'Planning → Analytics → Doc Generation → Email',
    icon: '🚀',
    agents: 4,
  },
  {
    value: 'daily_site_report',
    label: 'Daily Site Report',
    desc: 'Analytics → Report Generation → Email',
    icon: '📊',
    agents: 3,
  },
  {
    value: 'contract_generation',
    label: 'Contract Generation',
    desc: 'Planning → Doc Generation → Email',
    icon: '📋',
    agents: 3,
  },
  {
    value: 'budget_analysis',
    label: 'Budget Analysis',
    desc: 'Planning → Analytics only',
    icon: '💰',
    agents: 2,
  },
];

const AGENT_ICONS: Record<string, string> = {
  'Planning Agent': '🗺️',
  'Analytics Agent': '📈',
  'Doc Agent': '📄',
  'Email Agent': '✉️',
};

const AGENT_COLORS: Record<string, string> = {
  'Planning Agent': '#3b82f6',
  'Analytics Agent': '#06b6d4',
  'Doc Agent': '#10b981',
  'Email Agent': '#f59e0b',
};

function statusColor(status: AgentStatusType): string {
  switch (status) {
    case 'running': return '#f59e0b';
    case 'completed': return '#10b981';
    case 'error': return '#ef4444';
    default: return '#475569';
  }
}

export default function AgentsPage() {
  const [workflow, setWorkflow] = useState<WorkflowType>('full_project_setup');
  const [projectId, setProjectId] = useState('P1001');
  const [notes, setNotes] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [pastRuns, setPastRuns] = useState<RunStatus[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const lastAgentStatuses = useRef<Record<string, string>>({});
  const activeIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const activeTimeoutRefs = useRef<NodeJS.Timeout[]>([]);

  useEffect(() => {
    return () => {
      if (activeIntervalRef.current) {
        clearInterval(activeIntervalRef.current);
      }
      activeTimeoutRefs.current.forEach(clearTimeout);
    };
  }, []);

  const addLog = (message: string, level: LogEntry['level'] = 'info') => {
    setLogs((prev) => [
      ...prev,
      { time: new Date().toLocaleTimeString(), message, level },
    ]);
  };

  const pollStatus = async (runId: string) => {
    try {
      const res = await fetch(`${API_URL}/api/agents/status/${runId}`);
      if (!res.ok) return null;
      return await res.json() as RunStatus;
    } catch {
      return null;
    }
  };

  const runWorkflow = async () => {
    if (!projectId.trim()) return;
    setIsRunning(true);
    setRunStatus(null);
    setLogs([]);
    lastAgentStatuses.current = {};

    if (activeIntervalRef.current) {
      clearInterval(activeIntervalRef.current);
    }
    activeTimeoutRefs.current.forEach(clearTimeout);
    activeTimeoutRefs.current = [];

    addLog(`Starting workflow: ${workflow} for project ${projectId}`, 'info');

    try {
      const activeWorkspace = localStorage.getItem('buildflow_active_workspace') || 'default';
      const res = await fetch(`${API_URL}/api/agents/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_type: workflow,
          project_id: projectId,
          notes,
          session_id: activeWorkspace !== 'default' ? activeWorkspace : null
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const { run_id } = await res.json() as { run_id: string };
      addLog(`Workflow started! Run ID: ${run_id.slice(0, 8)}...`, 'success');

      // Poll until complete
      let attempts = 0;
      const maxAttempts = 30;
      const pollInterval = setInterval(async () => {
        attempts++;
        const status = await pollStatus(run_id);

        if (status) {
          setRunStatus(status);

          // Log agent state changes only when status changes
          status.agents.forEach((agent) => {
            const prevStatus = lastAgentStatuses.current[agent.agent_name];
            if (prevStatus !== agent.status) {
              lastAgentStatuses.current[agent.agent_name] = agent.status;
              if (agent.status === 'running') {
                addLog(`${agent.agent_name}: Processing...`, 'info');
              } else if (agent.status === 'completed') {
                addLog(`${agent.agent_name}: ✓ ${agent.output.slice(0, 80)}${agent.output.length > 80 ? '...' : ''}`, 'success');
              } else if (agent.status === 'error') {
                addLog(`${agent.agent_name}: ✗ Error occurred`, 'error');
              }
            }
          });

          if (status.status === 'completed') {
            clearInterval(pollInterval);
            setIsRunning(false);
            setPastRuns((prev) => [status, ...prev.slice(0, 9)]);
            addLog(`✅ Workflow completed: ${status.summary}`, 'success');
          }
        }

        if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setIsRunning(false);
          addLog('⚠️ Workflow polling timeout', 'warning');
        }
      }, 2000);
      activeIntervalRef.current = pollInterval;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      addLog(`❌ Error: ${msg}`, 'error');
      setIsRunning(false);

      // Demo mode: simulate the workflow
      addLog('Running in demo mode (backend offline)...', 'warning');
      const demoAgents = ['Planning Agent', 'Analytics Agent', 'Doc Agent', 'Email Agent'];
      const demoStatus: RunStatus = {
        run_id: 'demo-' + Date.now(),
        workflow_type: workflow,
        project_id: projectId,
        status: 'running',
        agents: demoAgents.map((name) => ({ agent_name: name, status: 'idle', output: 'Waiting...', timestamp: new Date().toISOString() })),
        started_at: new Date().toISOString(),
        summary: '',
      };
      setRunStatus(demoStatus);

      let i = 0;
      const interval = setInterval(() => {
        if (i >= demoAgents.length) {
          clearInterval(interval);
          setRunStatus((prev) => prev ? { ...prev, status: 'completed', summary: 'Demo workflow completed successfully!' } : prev);
          addLog('Demo workflow completed!', 'success');
          return;
        }
        const name = demoAgents[i];
        addLog(`${name}: Processing...`, 'info');
        const timeout = setTimeout(() => {
          setRunStatus((prev) => {
            if (!prev) return prev;
            const agents = [...prev.agents];
            agents[i] = { ...agents[i], status: 'completed', output: `${name} completed successfully for ${projectId}.`, timestamp: new Date().toISOString() };
            return { ...prev, agents };
          });
          addLog(`${name}: ✓ Completed`, 'success');
        }, 1500);
        activeTimeoutRefs.current.push(timeout);
        i++;
      }, 2000);
      activeIntervalRef.current = interval;
    }
  };

  const selectedWorkflow = WORKFLOW_OPTIONS.find((w) => w.value === workflow)!;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Multi-Agent Orchestration</h1>
        <p className="page-subtitle">Automate construction workflows with AI agents working in sequence</p>
      </div>

      {/* Workflow selector */}
      <div className="workflow-grid">
        {WORKFLOW_OPTIONS.map((wf) => (
          <button
            key={wf.value}
            className={`workflow-card ${workflow === wf.value ? 'active' : ''}`}
            onClick={() => setWorkflow(wf.value as WorkflowType)}
            id={`workflow-${wf.value}`}
          >
            <div className="wf-icon">{wf.icon}</div>
            <div className="wf-info">
              <div className="wf-label">{wf.label}</div>
              <div className="wf-desc">{wf.desc}</div>
            </div>
            <div className="wf-agents-badge">{wf.agents} agents</div>
          </button>
        ))}
      </div>

      <div className="agents-layout">
        {/* Left: Controls */}
        <div className="agents-controls">
          <div className="glass control-panel">
            <h3 className="panel-title">Workflow Parameters</h3>
            <div className="form-group">
              <label className="form-label">Project ID</label>
              <input
                type="text"
                className="form-input"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="e.g. P1001"
                id="workflow-project-id"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Additional Notes (optional)</label>
              <textarea
                className="form-textarea"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Any special instructions..."
                rows={3}
                id="workflow-notes"
              />
            </div>
            <button
              className="btn-run-workflow"
              onClick={runWorkflow}
              disabled={isRunning || !projectId.trim()}
              id="run-workflow-btn"
            >
              {isRunning ? (
                <>
                  <div className="btn-spinner" />
                  Running Workflow...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  Run {selectedWorkflow.label}
                </>
              )}
            </button>
          </div>

          {/* Past Runs */}
          {pastRuns.length > 0 && (
            <div className="glass past-runs-panel">
              <h3 className="panel-title">Past Runs</h3>
              {pastRuns.map((run) => (
                <div key={run.run_id} className="past-run-item" id={`run-${run.run_id.slice(0, 8)}`}>
                  <div className="past-run-info">
                    <span className="past-run-type">{run.workflow_type.replace(/_/g, ' ')}</span>
                    <span className="past-run-project">Project: {run.project_id}</span>
                  </div>
                  <span className={`past-run-status ${run.status}`}>{run.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Pipeline + Logs */}
        <div className="agents-right">
          {/* Agent Pipeline */}
          <div className="glass pipeline-panel">
            <h3 className="panel-title">Agent Pipeline</h3>
            {runStatus ? (
              <div className="pipeline-agents">
                {runStatus.agents.map((agent, idx) => {
                  const agentStatus = agent.status as AgentStatusType;
                  const color = AGENT_COLORS[agent.agent_name] || '#475569';
                  return (
                    <div key={idx} className="agent-wrapper">
                      <div
                        className={`agent-card ${agentStatus}`}
                        style={{
                          borderColor: agentStatus === 'idle' ? 'var(--border)' : color,
                          boxShadow: agentStatus === 'running' ? `0 0 20px ${color}40` : 'none',
                        }}
                        id={`agent-card-${agent.agent_name.replace(' ', '-').toLowerCase()}`}
                      >
                        <div className="agent-icon">{AGENT_ICONS[agent.agent_name] || '🤖'}</div>
                        <div className="agent-name">{agent.agent_name}</div>
                        <div
                          className="agent-status-badge"
                          style={{ background: `${statusColor(agentStatus)}20`, color: statusColor(agentStatus), border: `1px solid ${statusColor(agentStatus)}40` }}
                        >
                          {agentStatus === 'running' && <div className="mini-spinner" />}
                          {agentStatus === 'completed' && '✓ '}
                          {agentStatus === 'error' && '✗ '}
                          {agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)}
                        </div>
                        {agent.output && agent.output !== 'Waiting...' && agent.output !== 'Processing...' && (
                          <div className="agent-output">{agent.output.slice(0, 100)}{agent.output.length > 100 ? '...' : ''}</div>
                        )}
                      </div>
                      {idx < runStatus.agents.length - 1 && (
                        <div className="pipeline-arrow">→</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="pipeline-idle">
                <p>Select a workflow and project, then click <strong>Run</strong> to see agents in action.</p>
                <div className="pipeline-preview">
                  {['Planning Agent', 'Analytics Agent', 'Doc Agent', 'Email Agent'].slice(0, selectedWorkflow.agents).map((name, idx, arr) => (
                    <div key={name} className="agent-wrapper">
                      <div className="agent-card idle" style={{ opacity: 0.5 }}>
                        <div className="agent-icon">{AGENT_ICONS[name]}</div>
                        <div className="agent-name">{name}</div>
                        <div className="agent-status-badge" style={{ background: 'rgba(71,85,105,0.2)', color: '#475569' }}>
                          Idle
                        </div>
                      </div>
                      {idx < arr.length - 1 && <div className="pipeline-arrow" style={{ opacity: 0.3 }}>→</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {runStatus?.status === 'completed' && (
              <div className="workflow-summary">
                <span>✅</span>
                <span>{runStatus.summary}</span>
              </div>
            )}
          </div>

          {/* Workflow Log */}
          <div className="glass log-panel">
            <div className="log-header">
              <h3 className="panel-title">Workflow Log</h3>
              {logs.length > 0 && (
                <button className="btn-clear-log" onClick={() => setLogs([])} id="clear-log-btn">
                  Clear
                </button>
              )}
            </div>
            <div className="log-entries" id="workflow-log">
              {logs.length === 0 ? (
                <div className="log-empty">No activity yet. Run a workflow to see logs.</div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className={`log-entry ${log.level}`}>
                    <span className="log-time">{log.time}</span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .page-header { margin-bottom: 2rem; }
        .page-title { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.5rem; }
        .page-subtitle { color: var(--text-secondary); margin: 0; }

        .workflow-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 1rem;
          margin-bottom: 2rem;
        }
        .workflow-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 1rem;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
        }
        .workflow-card:hover { background: rgba(255,255,255,0.07); transform: translateY(-2px); }
        .workflow-card.active { border-color: var(--accent-blue); background: rgba(59,130,246,0.1); }
        .wf-icon { font-size: 1.5rem; flex-shrink: 0; }
        .wf-info { flex: 1; min-width: 0; }
        .wf-label { font-size: 0.82rem; font-weight: 600; color: var(--text-primary); }
        .wf-desc { font-size: 0.7rem; color: var(--text-secondary); margin-top: 2px; line-height: 1.4; }
        .wf-agents-badge {
          background: rgba(59,130,246,0.15);
          color: var(--accent-blue);
          border-radius: 12px;
          padding: 2px 8px;
          font-size: 0.7rem;
          font-weight: 600;
          white-space: nowrap;
          flex-shrink: 0;
        }

        .agents-layout { display: grid; grid-template-columns: 300px 1fr; gap: 1.5rem; }
        .agents-controls { display: flex; flex-direction: column; gap: 1rem; }
        .agents-right { display: flex; flex-direction: column; gap: 1rem; }

        .control-panel { padding: 1.5rem; border-radius: 16px; }
        .panel-title { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); margin: 0 0 1.25rem; }
        .form-group { margin-bottom: 1rem; }
        .form-label { display: block; font-size: 0.8rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px; }
        .form-input, .form-textarea {
          width: 100%;
          box-sizing: border-box;
          background: rgba(255,255,255,0.05);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 10px 12px;
          color: var(--text-primary);
          font-size: 0.85rem;
          font-family: inherit;
          transition: border-color 0.2s;
        }
        .form-input:focus, .form-textarea:focus { outline: none; border-color: var(--accent-blue); }
        .form-textarea { resize: vertical; }

        .btn-run-workflow {
          width: 100%;
          background: linear-gradient(135deg, #7c3aed, #3b82f6);
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
          margin-top: 0.5rem;
        }
        .btn-run-workflow:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 15px rgba(124,58,237,0.4); }
        .btn-run-workflow:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .past-runs-panel { padding: 1.25rem; border-radius: 16px; }
        .past-run-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid var(--border);
        }
        .past-run-item:last-child { border-bottom: none; }
        .past-run-info { display: flex; flex-direction: column; gap: 2px; }
        .past-run-type { font-size: 0.8rem; font-weight: 500; color: var(--text-primary); text-transform: capitalize; }
        .past-run-project { font-size: 0.7rem; color: var(--text-secondary); }
        .past-run-status { font-size: 0.7rem; font-weight: 600; border-radius: 12px; padding: 2px 8px; }
        .past-run-status.completed { background: rgba(16,185,129,0.15); color: var(--accent-green); }
        .past-run-status.running { background: rgba(245,158,11,0.15); color: var(--accent-orange); }
        .past-run-status.failed { background: rgba(239,68,68,0.15); color: var(--accent-red); }

        .pipeline-panel { padding: 1.5rem; border-radius: 16px; }
        .pipeline-agents {
          display: flex;
          align-items: flex-start;
          gap: 0;
          flex-wrap: nowrap;
          overflow-x: auto;
          padding-bottom: 0.5rem;
        }
        .agent-wrapper { display: flex; align-items: center; gap: 0; }
        .pipeline-arrow {
          font-size: 1.25rem;
          color: var(--text-secondary);
          padding: 0 0.75rem;
          flex-shrink: 0;
          margin-bottom: 40px;
        }
        .agent-card {
          background: rgba(255,255,255,0.03);
          border: 2px solid var(--border);
          border-radius: 14px;
          padding: 1rem;
          min-width: 150px;
          max-width: 180px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          transition: all 0.3s;
          text-align: center;
        }
        .agent-card.running {
          background: rgba(245,158,11,0.05);
          animation: pulse-border 1.5s infinite;
        }
        @keyframes pulse-border {
          0%, 100% { box-shadow: 0 0 0 0 rgba(245,158,11,0.4); }
          50% { box-shadow: 0 0 0 8px rgba(245,158,11,0); }
        }
        .agent-icon { font-size: 1.75rem; }
        .agent-name { font-size: 0.8rem; font-weight: 600; color: var(--text-primary); }
        .agent-status-badge {
          font-size: 0.7rem;
          font-weight: 600;
          border-radius: 12px;
          padding: 3px 8px;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .mini-spinner {
          width: 10px; height: 10px;
          border: 1.5px solid rgba(245,158,11,0.4);
          border-top-color: #f59e0b;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        .agent-output {
          font-size: 0.68rem;
          color: var(--text-secondary);
          line-height: 1.4;
          text-align: center;
          margin-top: 4px;
        }

        .pipeline-idle { text-align: center; }
        .pipeline-idle > p { color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 1.5rem; }
        .pipeline-preview { display: flex; align-items: center; justify-content: center; flex-wrap: nowrap; overflow-x: auto; gap: 0; }

        .workflow-summary {
          margin-top: 1rem;
          padding: 0.75rem 1rem;
          background: rgba(16,185,129,0.1);
          border: 1px solid rgba(16,185,129,0.3);
          border-radius: 8px;
          color: var(--accent-green);
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .log-panel { padding: 1.25rem; border-radius: 16px; }
        .log-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
        .btn-clear-log {
          background: transparent;
          border: 1px solid var(--border);
          color: var(--text-secondary);
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 0.75rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .btn-clear-log:hover { border-color: var(--accent-red); color: var(--accent-red); }
        .log-entries {
          display: flex;
          flex-direction: column;
          gap: 4px;
          max-height: 200px;
          overflow-y: auto;
          font-family: 'Courier New', monospace;
        }
        .log-empty { color: var(--text-secondary); font-size: 0.82rem; text-align: center; padding: 1rem; }
        .log-entry {
          display: flex;
          gap: 0.75rem;
          font-size: 0.78rem;
          padding: 4px 8px;
          border-radius: 6px;
        }
        .log-entry.info { color: var(--text-secondary); }
        .log-entry.success { color: #86efac; background: rgba(16,185,129,0.05); }
        .log-entry.warning { color: #fde68a; background: rgba(245,158,11,0.05); }
        .log-entry.error { color: #fca5a5; background: rgba(239,68,68,0.05); }
        .log-time { color: var(--text-secondary); flex-shrink: 0; }
        .log-msg { flex: 1; }
      `}</style>
    </div>
  );
}
