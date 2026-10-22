import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  FileSpreadsheet, 
  RefreshCw, 
  Sparkles,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';

export default function RunsManager({ onSelectRunLeads, onNewRunClick }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncingId, setSyncingId] = useState(null);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const data = await api.getRuns(50, 0);
      setRuns(data || []);
    } catch (err) {
      console.error('Failed to fetch pipeline runs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(() => {
      if (runs.some(r => r.status === 'RUNNING' || r.status === 'PENDING')) {
        fetchRuns();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSyncToSheets = async (runId, e) => {
    e.stopPropagation();
    setSyncingId(runId);
    try {
      await api.syncSheets(runId);
      alert(`Export synced! Final leads pushed to Google Sheets & XLSX.`);
      fetchRuns();
    } catch (err) {
      alert(`Sheets sync failed: ${err.message}`);
    } finally {
      setSyncingId(null);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="badge badge-status-final">COMPLETED</span>;
      case 'RUNNING':
        return <span className="badge badge-status-running">PROCESSING</span>;
      case 'PENDING':
        return <span className="badge badge-status-review">QUEUED</span>;
      case 'FAILED':
        return <span className="badge badge-status-rejected">FAILED</span>;
      default:
        return <span className="badge badge-priority-c">{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header */}
      <div className="bento-card" style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Pipeline Execution History</h2>
          <p className="text-xs" style={{ marginTop: '2px' }}>
            Audit batch generation runs, candidate discovery yield, and exported sheets
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={fetchRuns}
            className="btn btn-secondary btn-sm"
            disabled={loading}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button
            onClick={onNewRunClick}
            className="btn btn-primary btn-sm"
          >
            <Sparkles size={13} />
            <span>New Lead Run</span>
          </button>
        </div>
      </div>

      {/* Runs Table */}
      <div className="table-container">
        {loading && runs.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px auto', color: 'var(--text-dark)' }} />
            <p style={{ fontSize: '0.875rem' }}>Loading pipeline history...</p>
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Activity size={32} style={{ margin: '0 auto 12px auto', opacity: 0.3 }} />
            <h4 style={{ color: 'var(--text-dark)', marginBottom: '4px' }}>No runs recorded yet</h4>
            <p style={{ fontSize: '0.8125rem' }}>Launch your first autonomous run above to start generating leads.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="minimal-table">
              <thead>
                <tr>
                  <th>Run Identifier</th>
                  <th>Status</th>
                  <th>Target Scope</th>
                  <th>Raw Scraped</th>
                  <th>Final Approved</th>
                  <th>Priority A</th>
                  <th>Duplicates Blocked</th>
                  <th>Created At</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr 
                    key={r.id}
                    onClick={() => onSelectRunLeads(r.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    {/* Run Name */}
                    <td>
                      <div style={{ fontWeight: 700, color: 'var(--text-dark)', fontSize: '0.85rem' }}>
                        {r.name}
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                        ID: {r.id.substring(0, 8)}...
                      </span>
                    </td>

                    {/* Status */}
                    <td>
                      {getStatusBadge(r.status)}
                    </td>

                    {/* Target Scope */}
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {(r.target_states || ['ALL']).map((st, idx) => (
                          <span key={idx} style={{
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            padding: '1px 6px',
                            borderRadius: 'var(--radius-pill)',
                            backgroundColor: 'var(--cream)',
                            color: 'var(--text-dark)'
                          }}>
                            {st}
                          </span>
                        ))}
                      </div>
                      <div className="text-xs" style={{ marginTop: '2px' }}>
                        Fleet: {r.fleet_size_min}–{r.fleet_size_max} Trucks
                      </div>
                    </td>

                    {/* Counts */}
                    <td style={{ fontWeight: 600, color: 'var(--text-dark)' }}>
                      {r.raw_count}
                    </td>

                    <td>
                      <span style={{ fontWeight: 800, color: 'var(--sage-dark)', fontSize: '0.925rem' }}>
                        {r.final_count}
                      </span>
                    </td>

                    <td>
                      <span style={{ fontWeight: 700, color: 'var(--danger-text)' }}>
                        {r.priority_a_count}
                      </span>
                    </td>

                    <td style={{ color: 'var(--warning-text)', fontWeight: 600 }}>
                      {r.duplicate_count}
                    </td>

                    <td className="text-xs">
                      {new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '6px' }}>
                        <button
                          onClick={(e) => handleSyncToSheets(r.id, e)}
                          className="btn btn-secondary btn-sm"
                          disabled={syncingId === r.id}
                          title="Export to Sheets / XLSX"
                        >
                          <FileSpreadsheet size={13} color="var(--sage-dark)" />
                          <span>{syncingId === r.id ? 'Syncing...' : 'Export'}</span>
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectRunLeads(r.id);
                          }}
                          className="btn btn-primary btn-sm"
                        >
                          <span>Leads</span>
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
