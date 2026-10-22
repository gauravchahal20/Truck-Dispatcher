import React, { useState, useEffect } from 'react';
import { 
  FileSpreadsheet, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  ExternalLink, 
  Download, 
  ShieldCheck
} from 'lucide-react';
import { api } from '../services/api';

export default function SheetsManager() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await api.getSheetsStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch Sheets status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await api.syncSheets(null);
      alert(`Full batch sync completed! Leads exported cleanly.`);
      fetchStatus();
    } catch (err) {
      alert(`Sync failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header */}
      <div className="bento-card" style={{ padding: '20px 24px' }}>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Google Sheets & File Export Hub</h2>
        <p className="text-xs" style={{ marginTop: '2px' }}>
          Automated multi-tab spreadsheet sync with decision maker contacts and verification evidence
        </p>
      </div>

      {/* Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        
        {/* Connection Bento Card */}
        <div className="bento-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <div style={{
              width: '34px',
              height: '34px',
              borderRadius: 'var(--radius-pill)',
              backgroundColor: 'var(--sage-light)',
              color: 'var(--sage-dark)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <FileSpreadsheet size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Google Sheets Integration</h3>
              <p className="text-xs">Service Account API Status</p>
            </div>
          </div>

          <div style={{
            padding: '14px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--cream)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            {status?.configured ? (
              <CheckCircle2 size={18} color="var(--sage-dark)" />
            ) : (
              <AlertCircle size={18} color="var(--warning-text)" />
            )}
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.8125rem', color: status?.configured ? 'var(--sage-dark)' : 'var(--warning-text)' }}>
                {status?.configured ? 'Connected to Live Google Sheet' : 'Local File Backup Active'}
              </div>
              <p className="text-xs" style={{ marginTop: '2px' }}>
                {status?.configured 
                  ? `Spreadsheet ID: ${status.spreadsheet_id || 'Configured via .env'}`
                  : 'Automated backup to data/exports/ as XLSX/CSV. Add GOOGLE_APPLICATION_CREDENTIALS in .env for cloud sync.'}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handleSyncAll}
              className="btn btn-primary"
              disabled={syncing}
              style={{ flex: 1 }}
            >
              <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
              <span>{syncing ? 'Syncing...' : 'Trigger Export Sync'}</span>
            </button>

            {status?.spreadsheet_url && (
              <a
                href={status.spreadsheet_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary"
              >
                <ExternalLink size={14} />
                <span>Open Sheet</span>
              </a>
            )}
          </div>
        </div>

        {/* Tab Structure Bento Card */}
        <div className="bento-card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '10px' }}>
            Multi-Sheet Export Hierarchy
          </h3>
          <p className="text-xs" style={{ marginBottom: '14px' }}>
            Each run formats carrier data into 3 distinct, organized spreadsheet tabs:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-md)', backgroundColor: '#FAFAFA', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ fontSize: '0.8125rem', color: 'var(--sage-dark)' }}>1. Final Qualified Leads</strong>
              <p className="text-xs" style={{ marginTop: '2px' }}>
                Company, USDOT, Fleet Size, Verified Decision Maker, Phone, Email & Lead Score.
              </p>
            </div>

            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-md)', backgroundColor: '#FAFAFA', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ fontSize: '0.8125rem', color: 'var(--warning-text)' }}>2. Review Queue</strong>
              <p className="text-xs" style={{ marginTop: '2px' }}>
                Unverified candidates requiring manual review by a dispatcher.
              </p>
            </div>

            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-md)', backgroundColor: '#FAFAFA', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ fontSize: '0.8125rem', color: 'var(--danger-text)' }}>3. Disqualified Leads</strong>
              <p className="text-xs" style={{ marginTop: '2px' }}>
                Full rejection reasons (mega-fleet, inactive operating authority, passenger carrier).
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}
