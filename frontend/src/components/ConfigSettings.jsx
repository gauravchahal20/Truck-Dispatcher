import React, { useState, useEffect } from 'react';
import { Sliders, Save, RefreshCw, CheckCircle2, FileCode, ShieldAlert, PhoneCall, Mail } from 'lucide-react';
import { api } from '../services/api';

export default function ConfigSettings() {
  const [yamlContent, setYamlContent] = useState('');
  const [compliance, setCompliance] = useState({
    postal_address: '',
    sender_identity: '',
    call_script_status: 'hidden: sender_identity not set',
    email_readiness_status: 'blocked: postal_address not set'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const data = await api.getConfig();
      setYamlContent(data.yaml_content || '');
      if (data.compliance) {
        setCompliance(data.compliance);
      }
    } catch (err) {
      console.error('Failed to fetch config:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateConfig(yamlContent);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
      fetchConfig();
    } catch (err) {
      alert(`Failed to save config: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header */}
      <div className="bento-card" style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Ideal Customer Profile (ICP) & Scoring Config</h2>
          <p className="text-xs" style={{ marginTop: '2px' }}>
            Live runtime configuration governing verification rules, fleet size thresholds, and scoring weights
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {savedSuccess && (
            <span className="badge badge-status-final">
              <CheckCircle2 size={13} /> Saved!
            </span>
          )}

          <button
            onClick={fetchConfig}
            className="btn btn-secondary btn-sm"
            disabled={loading}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Reload</span>
          </button>
        </div>
      </div>

      {/* Compliance & Outreach Status Bento Card (N9f) */}
      <div className="bento-card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <ShieldAlert size={16} color="var(--primary)" />
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Outreach & Compliance Prerequisites (CAN-SPAM / TCPA)</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Call Script Status */}
          <div style={{ padding: '14px 16px', backgroundColor: '#F8F9FA', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <PhoneCall size={14} /> Call Script Status
              </span>
              <span className={`badge ${compliance.call_script_status === 'active' ? 'badge-status-final' : 'badge-status-rejected'}`}>
                {compliance.call_script_status === 'active' ? 'Active' : 'Hidden'}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {compliance.call_script_status === 'active'
                ? `Sender Identity: "${compliance.sender_identity}" (Active in Verify-and-Call Queue)`
                : 'Call script hidden until sender_identity is configured in compliance settings.'}
            </p>
          </div>

          {/* Email Outreach Readiness */}
          <div style={{ padding: '14px 16px', backgroundColor: '#F8F9FA', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Mail size={14} /> Email Outreach Status
              </span>
              <span className={`badge ${compliance.email_readiness_status === 'ready_for_outreach' ? 'badge-status-final' : 'badge-status-rejected'}`}>
                {compliance.email_readiness_status === 'ready_for_outreach' ? 'Ready for Outreach' : 'Blocked'}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {compliance.email_readiness_status === 'ready_for_outreach'
                ? `Physical Address: "${compliance.postal_address}" (Ready to contact)`
                : 'Email-ready list blocked until postal_address is configured in compliance settings.'}
            </p>
          </div>
        </div>
      </div>

      {/* YAML Editor Bento Card */}
      <div className="bento-card">
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading configuration...
          </div>
        ) : (
          <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              <FileCode size={15} color="var(--text-dark)" />
              <span style={{ fontWeight: 600 }}>default_config.yaml (Dynamic Runtime Engine)</span>
            </div>

            <textarea
              value={yamlContent}
              onChange={(e) => setYamlContent(e.target.value)}
              rows={22}
              style={{
                width: '100%',
                backgroundColor: '#FAFAFA',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                color: 'var(--text-dark)',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.8125rem',
                lineHeight: 1.6,
                outline: 'none',
                resize: 'vertical'
              }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
                style={{ minWidth: '160px' }}
              >
                <Save size={14} />
                <span>{saving ? 'Applying...' : 'Save & Reload Config'}</span>
              </button>
            </div>
          </form>
        )}
      </div>

    </div>
  );
}
