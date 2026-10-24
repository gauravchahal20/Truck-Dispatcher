import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  Mail, 
  Clock, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Copy, 
  Check, 
  PhoneCall, 
  Download, 
  RefreshCw,
  Send,
  User,
  Truck,
  Filter,
  FileSpreadsheet,
  Globe,
  SlidersHorizontal,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';

export default function ReadyToContact({ onViewLead }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterMode, setFilterMode] = useState('all'); // all, callable, mailable, both
  const [searchTerm, setSearchTerm] = useState('');
  const [stateFilter, setStateFilter] = useState('ALL');
  
  // Modals & Action States
  const [selectedLeadForOutcome, setSelectedLeadForOutcome] = useState(null);
  const [outcomeChannel, setOutcomeChannel] = useState('PHONE'); // PHONE or EMAIL
  const [outcomeNotes, setOutcomeNotes] = useState('');
  const [isSubmittingOutcome, setIsSubmittingOutcome] = useState(false);
  
  const [draftEmailLead, setDraftEmailLead] = useState(null);
  const [draftEmailContent, setDraftEmailContent] = useState(null);
  const [draftEmailError, setDraftEmailError] = useState(null);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [copiedDraft, setCopiedDraft] = useState(false);

  // Manual Authority Verification Modal States (L2i)
  const [selectedLeadForVerify, setSelectedLeadForVerify] = useState(null);
  const [verifyDate, setVerifyDate] = useState(new Date().toISOString().split('T')[0]);
  const [verifyMc, setVerifyMc] = useState('');
  const [verifyStatus, setVerifyStatus] = useState('ACTIVE');
  const [verifyInsurance, setVerifyInsurance] = useState(true);
  const [verifyAmount, setVerifyAmount] = useState(750000);
  const [verifyNotes, setVerifyNotes] = useState('');
  const [isSubmittingVerify, setIsSubmittingVerify] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  const [verifySuccess, setVerifySuccess] = useState(null);

  const handleOpenVerify = (lead) => {
    setSelectedLeadForVerify(lead);
    setVerifyDate(new Date().toISOString().split('T')[0]);
    setVerifyMc(lead.mc_number || '');
    setVerifyStatus('ACTIVE');
    setVerifyInsurance(true);
    setVerifyAmount(750000);
    setVerifyNotes(`Verified active common carrier authority and $750k+ BIPD insurance on SAFER for USDOT ${lead.usdot || ''}`);
    setVerifyError(null);
    setVerifySuccess(null);
  };

  const handleSubmitVerify = async (e) => {
    e.preventDefault();
    if (!selectedLeadForVerify) return;
    setIsSubmittingVerify(true);
    setVerifyError(null);
    setVerifySuccess(null);
    try {
      const res = await api.verifyAuthorityManual(selectedLeadForVerify.id, {
        verification_date: verifyDate,
        mc_number: verifyMc || null,
        authority_status: verifyStatus,
        insurance_on_file: verifyInsurance,
        insurance_amount: Number(verifyAmount) || 750000,
        notes: verifyNotes
      });
      setVerifySuccess(`Verified authority for ${selectedLeadForVerify.company}! New Status: ${res.lead_status} (Score ${res.lead_score?.toFixed(1)})`);
      setTimeout(() => {
        setSelectedLeadForVerify(null);
        fetchLeads();
      }, 1500);
    } catch (err) {
      console.error('Manual verification failed:', err);
      setVerifyError(err.message || 'Failed to submit manual verification');
    } finally {
      setIsSubmittingVerify(false);
    }
  };

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const data = await api.getCallableMailableLeads(filterMode, 200);
      setLeads(data.leads || []);
    } catch (err) {
      console.error('Failed to load callable & mailable leads:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [filterMode]);

  const handleOpenDraft = async (lead) => {
    setDraftEmailLead(lead);
    setLoadingDraft(true);
    setCopiedDraft(false);
    setDraftEmailError(null);
    setDraftEmailContent(null);
    try {
      const draft = await api.getDraftEmail(lead.id);
      setDraftEmailContent(draft);
    } catch (err) {
      console.error('Failed to fetch email draft:', err);
      const msg = err.message || 'Set your postal address in Settings to generate drafts';
      setDraftEmailError(msg);
    } finally {
      setLoadingDraft(false);
    }
  };

  const handleCopyDraft = () => {
    if (!draftEmailContent) return;
    const recipient = draftEmailContent.recipient || draftEmailContent.recipient_email || draftEmailLead?.email || '';
    const textToCopy = `Subject: ${draftEmailContent.subject}\nTo: ${recipient}\n\n${draftEmailContent.body}`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedDraft(true);
    setTimeout(() => setCopiedDraft(false), 2500);
  };

  const handleOpenOutcome = (lead, channel) => {
    setSelectedLeadForOutcome(lead);
    setOutcomeChannel(channel);
    setOutcomeNotes('');
  };

  const handleSubmitOutcome = async (outcomeType) => {
    if (!selectedLeadForOutcome) return;
    setIsSubmittingOutcome(true);
    try {
      await api.logLeadOutcome({
        company_id: selectedLeadForOutcome.id,
        channel: outcomeChannel,
        outcome: outcomeType,
        notes: outcomeNotes || `Logged from UI: ${outcomeType}`
      });
      setSelectedLeadForOutcome(null);
      await fetchLeads();
    } catch (err) {
      alert(`Error logging outcome: ${err.message}`);
    } finally {
      setIsSubmittingOutcome(false);
    }
  };

  // Filtered Leads
  const filteredLeads = leads.filter(l => {
    const matchesSearch = !searchTerm || 
      l.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.contact_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (l.usdot && l.usdot.includes(searchTerm)) ||
      (l.equipment && l.equipment.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesState = stateFilter === 'ALL' || l.state === stateFilter;
    return matchesSearch && matchesState;
  });

  const availableStates = Array.from(new Set(leads.map(l => l.state).filter(Boolean))).sort();

  // Metrics
  const callableCount = leads.filter(l => l.phone_e164).length;
  const mailableCount = leads.filter(l => l.is_mailable).length;
  const bothCount = leads.filter(l => l.phone_e164 && l.is_mailable).length;

  return (
    <div className="ready-to-contact-page" style={{ padding: '0 4px' }}>
      {/* Header & Description */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-dark)', margin: 0 }}>
              Ready to Contact
            </h1>
            <span style={{ 
              backgroundColor: 'var(--sage-light)', 
              color: 'var(--sage-dark)', 
              fontSize: '0.72rem', 
              fontWeight: 700, 
              padding: '2px 8px', 
              borderRadius: '999px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <ShieldCheck size={12} /> Contact Layer Verified
            </span>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
            Curated list of outreach-ready owner-operators and carrier decision-makers with E.164 phones, local calling windows, and verified email deliverability.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={fetchLeads} 
            className="btn btn-secondary" 
            style={{ fontSize: '0.8rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <a
            href="http://localhost:8000/api/sheets/sync"
            target="_blank"
            rel="noreferrer"
            className="btn btn-primary"
            style={{ fontSize: '0.8rem', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Download size={14} /> Export CSV / XLSX
          </a>
        </div>
      </div>

      {/* Metric Cards Banner */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px', 
        marginBottom: '24px' 
      }}>
        <div className="stat-card" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
            TOTAL OUTREACH READY
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-dark)' }}>
            {leads.length}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            FINAL + QUALIFIED with active authority
          </div>
        </div>

        <div className="stat-card" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
            CALLABLE (+1 E.164)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--ocean-dark)' }}>
            {callableCount} <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>({leads.length ? Math.round(callableCount / leads.length * 100) : 0}%)</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Valid assigned format with local time zone
          </div>
        </div>

        <div className="stat-card" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
            MAILABLE (MX VERIFIED)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--sage-dark)' }}>
            {mailableCount} <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>({leads.length ? Math.round(mailableCount / leads.length * 100) : 0}%)</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Deliverable or safe role mailbox
          </div>
        </div>

        <div className="stat-card" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
            CALLABLE & MAILABLE
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--terracotta-dark)' }}>
            {bothCount}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Dual-channel reachable decision-makers
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        gap: '12px',
        marginBottom: '16px',
        backgroundColor: '#FFFFFF',
        padding: '12px 16px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)'
      }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Leads' },
            { id: 'callable', label: 'Callable (+1)' },
            { id: 'mailable', label: 'Mailable (Deliverable)' },
            { id: 'both', label: 'Both Channels' },
            { id: 'unproven_authority', label: 'Authority unproven - verify manually' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setFilterMode(tab.id)}
              className="btn"
              style={{
                fontSize: '0.75rem',
                padding: '5px 12px',
                borderRadius: '999px',
                fontWeight: 600,
                backgroundColor: filterMode === tab.id ? 'var(--text-dark)' : 'var(--warm-cream)',
                color: filterMode === tab.id ? '#FFFFFF' : 'var(--text-dark)',
                border: 'none'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="text"
            placeholder="Search company, USDOT, contact..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              fontSize: '0.8rem',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              width: '220px'
            }}
          />

          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            style={{
              fontSize: '0.8rem',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: '#FFFFFF'
            }}
          >
            <option value="ALL">All States</option>
            {availableStates.map(st => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Guidance Banner for Unproven Authority (L2i) */}
      {filterMode === 'unproven_authority' && (
        <div style={{
          backgroundColor: '#EFF6FF',
          border: '1px solid #BFDBFE',
          borderRadius: 'var(--radius-md)',
          padding: '16px',
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color="#1D4ED8" />
              <strong style={{ color: '#1E40AF', fontSize: '0.9rem' }}>
                Authority Verification Queue (SAFER & L&I Manual Check)
              </strong>
            </div>
            <a
              href="https://safer.fmcsa.dot.gov/CompanySnapshot.aspx"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              Open SAFER Company Snapshot <ExternalLink size={12} />
            </a>
          </div>
          <p style={{ fontSize: '0.78rem', color: '#1E3A8A', margin: '0 0 8px 0' }}>
            These carriers have valid outreach contact info, but their operating authority or insurance filings are unproven in local datasets. Verify them against official SAFER records to admit them to QUALIFIED status.
          </p>
          <div style={{ fontSize: '0.72rem', color: '#1E40AF', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '6px' }}>
            <div>1. Search USDOT/MC on SAFER Company Snapshot</div>
            <div>2. Confirm Operating Status is "AUTHORIZED FOR HIRE"</div>
            <div>3. Click Licensing & Insurance link to check Active Authority status</div>
            <div>4. Check BIPD Insurance on file ($750k+ minimum for general freight)</div>
            <div>5. Click "Verify Authority" on row to update lead and re-score</div>
          </div>
        </div>
      )}

      {/* Main Table */}
      <div style={{ 
        backgroundColor: '#FFFFFF', 
        borderRadius: 'var(--radius-md)', 
        border: '1px solid var(--border-subtle)',
        overflowX: 'auto',
        boxShadow: 'var(--shadow-subtle)'
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--warm-cream)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>COMPANY & AUTHORITY</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>CONTACT NAME & TITLE</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>+1 PHONE & GUIDANCE</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>EMAIL & DELIVERABILITY</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>BEST CALL WINDOW</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>FLEET & EQUIPMENT</th>
              <th style={{ padding: '10px 14px', fontWeight: 700 }}>SCORE & STATUS</th>
              <th style={{ padding: '10px 14px', fontWeight: 700, textAlign: 'right' }}>OPERATOR ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="8" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                  <div>Loading verified contacts...</div>
                </td>
              </tr>
            ) : filteredLeads.length === 0 ? (
              <tr>
                <td colSpan="8" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No leads found matching current filter criteria.
                </td>
              </tr>
            ) : (
              filteredLeads.map((lead) => {
                const isMobile = lead.phone_line_type?.toLowerCase() === 'mobile';
                const isSoleProp = lead.call_guidance?.includes('manually');

                return (
                  <tr key={lead.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    {/* 1. Company */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-dark)', cursor: 'pointer' }} onClick={() => onViewLead && onViewLead(lead)}>
                        {lead.company}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', gap: '6px', marginTop: '2px', flexWrap: 'wrap' }}>
                        <span>USDOT #{lead.usdot || 'N/A'}</span>
                        {lead.mc_number && <span>&bull; MC #{lead.mc_number}</span>}
                        {lead.state && <span>&bull; {lead.state}</span>}
                      </div>
                      {/* Sanity & Quality Flags (L2i) */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                        {lead.fleet_inconsistent && (
                          <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#FEE2E2', color: '#991B1B', fontWeight: 700 }} title="Power units, trucks, and drivers diverge significantly">
                            ⚠️ Fleet Inconsistent
                          </span>
                        )}
                        {lead.hazmat_carrier && (
                          <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 700 }} title="Carrier hauls hazardous materials">
                            ☣️ Hazmat
                          </span>
                        )}
                        {lead.phone_region_mismatch && (
                          <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#EDE9FE', color: '#5B21B6', fontWeight: 700 }} title="Phone area code geocoded state does not match company physical address state">
                            📍 Phone Mismatch
                          </span>
                        )}
                        {lead.authority_status && lead.authority_status !== 'ACTIVE' && (
                          <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#F3F4F6', color: '#4B5563', fontWeight: 600 }}>
                            Auth: {lead.authority_status}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* 2. Contact */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-dark)' }}>
                        {lead.contact_name}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {lead.title || 'Decision Maker'}
                      </div>
                    </td>

                    {/* 3. Phone */}
                    <td style={{ padding: '12px 14px' }}>
                      {lead.phone_e164 ? (
                        <div>
                          <a 
                            href={lead.dial_link} 
                            style={{ 
                              fontWeight: 700, 
                              color: 'var(--ocean-dark)', 
                              textDecoration: 'none', 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: '4px' 
                            }}
                          >
                            <Phone size={12} /> {lead.phone_display || lead.phone_e164}
                          </a>
                          <div style={{ display: 'flex', gap: '4px', marginTop: '3px' }}>
                            <span style={{
                              fontSize: '0.65rem',
                              padding: '1px 5px',
                              borderRadius: '4px',
                              backgroundColor: lead.phone_status === 'VERIFIED' ? 'var(--sage-light)' : (lead.phone_status === 'CORROBORATED' ? '#E0E7FF' : 'var(--warm-cream)'),
                              color: lead.phone_status === 'VERIFIED' ? 'var(--sage-dark)' : (lead.phone_status === 'CORROBORATED' ? '#3730A3' : 'var(--text-muted)'),
                              fontWeight: 600
                            }}>
                              {lead.phone_status}
                            </span>
                            {isSoleProp && (
                              <span style={{
                                fontSize: '0.65rem',
                                padding: '1px 5px',
                                borderRadius: '4px',
                                backgroundColor: '#FFF3CD',
                                color: '#856404',
                                fontWeight: 700
                              }}>
                                Manual Call Only (DNC)
                              </span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>No phone</span>
                      )}
                    </td>

                    {/* 4. Email */}
                    <td style={{ padding: '12px 14px' }}>
                      {lead.email ? (
                        <div>
                          <a 
                            href={lead.mailto_link} 
                            style={{ 
                              fontWeight: 600, 
                              color: 'var(--terracotta-dark)', 
                              textDecoration: 'none', 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: '4px' 
                            }}
                          >
                            <Mail size={12} /> {lead.email}
                          </a>
                          <div style={{ marginTop: '2px', display: 'flex', gap: '4px', alignItems: 'center' }}>
                            <span style={{
                              fontSize: '0.65rem',
                              padding: '1px 5px',
                              borderRadius: '4px',
                              backgroundColor: lead.email_status === 'DELIVERABLE' ? 'var(--sage-light)' : (lead.email_status === 'DOMAIN_OK' ? '#DBEAFE' : (lead.email_status === 'RISKY' ? '#FFF3CD' : 'var(--warm-cream)')),
                              color: lead.email_status === 'DELIVERABLE' ? 'var(--sage-dark)' : (lead.email_status === 'DOMAIN_OK' ? '#1E40AF' : (lead.email_status === 'RISKY' ? '#856404' : 'var(--text-muted)')),
                              fontWeight: 700
                            }}>
                              {lead.email_status}
                            </span>
                            {lead.is_named_email && (
                              <span style={{
                                fontSize: '0.63rem',
                                padding: '1px 5px',
                                borderRadius: '4px',
                                backgroundColor: '#F3E8FF',
                                color: '#6B21A8',
                                fontWeight: 600
                              }}>
                                Named
                              </span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Pending email</span>
                      )}
                    </td>

                    {/* 5. Call Window */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)' }}>
                        <Clock size={12} color="var(--ocean-dark)" /> {lead.call_window_local || '09:00 - 17:00 Local'}
                      </div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        IST: {lead.call_window_ist || '18:30 - 02:30 IST'}
                      </div>
                    </td>

                    {/* 6. Fleet & Equipment */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-dark)' }}>
                        {lead.fleet_size ? `${lead.fleet_size} Trucks` : 'Owner-Operator'}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', maxWidth: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {lead.equipment}
                      </div>
                    </td>

                    {/* 7. Score & Priority */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          padding: '1px 6px',
                          borderRadius: '4px',
                          backgroundColor: lead.priority === 'A' ? 'var(--terracotta-light)' : 'var(--warm-cream)',
                          color: lead.priority === 'A' ? 'var(--terracotta-dark)' : 'var(--text-dark)'
                        }}>
                          Tier {lead.priority}
                        </span>
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                          {lead.lead_score?.toFixed(1)}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Status: {lead.lead_status}
                      </div>
                      <div style={{ marginTop: '3px' }}>
                        <span style={{
                          fontSize: '0.65rem',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          backgroundColor: lead.contact_confidence === 'HIGH' ? '#D1FAE5' : (lead.contact_confidence === 'MEDIUM' ? '#FEF3C7' : '#F3F4F6'),
                          color: lead.contact_confidence === 'HIGH' ? '#065F46' : (lead.contact_confidence === 'MEDIUM' ? '#92400E' : '#4B5563'),
                          fontWeight: 700
                        }}>
                          Ready: {lead.contact_confidence || 'LOW'}
                        </span>
                      </div>
                    </td>

                    {/* 8. Operator Actions */}
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                        {lead.phone_e164 && (
                          <button
                            onClick={() => handleOpenOutcome(lead, 'PHONE')}
                            className="btn btn-secondary"
                            style={{ fontSize: '0.7rem', padding: '4px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                            title="Log Call Outcome"
                          >
                            <PhoneCall size={12} /> Log Call
                          </button>
                        )}

                        <button
                          onClick={() => handleOpenDraft(lead)}
                          className="btn btn-secondary"
                          style={{ fontSize: '0.7rem', padding: '4px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          title="Generate CAN-SPAM Draft"
                        >
                          <Mail size={12} /> Draft Email
                        </button>

                        <button
                          onClick={() => handleOpenOutcome(lead, 'EMAIL')}
                          className="btn"
                          style={{ fontSize: '0.7rem', padding: '4px 8px', backgroundColor: 'var(--warm-cream)', color: 'var(--text-muted)', border: 'none' }}
                          title="Log Email Outcome"
                        >
                          Log Email
                        </button>

                        {(lead.authority_status !== 'ACTIVE' || lead.lead_status === 'NEEDS_ENRICHMENT') && (
                          <button
                            onClick={() => handleOpenVerify(lead)}
                            className="btn btn-secondary"
                            style={{
                              fontSize: '0.7rem',
                              padding: '4px 8px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              backgroundColor: '#EFF6FF',
                              color: '#1D4ED8',
                              borderColor: '#BFDBFE'
                            }}
                            title="Verify Operating Authority against SAFER"
                          >
                            <ShieldCheck size={12} /> Verify
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* MODAL 1: Log Outcome Modal */}
      {selectedLeadForOutcome && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 'var(--radius-lg)',
            width: '460px',
            maxWidth: '90%',
            padding: '24px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: '0 0 8px 0', color: 'var(--text-dark)' }}>
              Log {outcomeChannel === 'PHONE' ? 'Call' : 'Email'} Outcome
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 16px 0' }}>
              Record operator outreach result for <strong>{selectedLeadForOutcome.company}</strong> ({selectedLeadForOutcome.contact_name}).
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, display: 'block', marginBottom: '8px' }}>
                SELECT OUTCOME:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {outcomeChannel === 'PHONE' ? [
                  { id: 'interested', label: 'Interested / Booked Load', color: 'var(--sage-light)', text: 'var(--sage-dark)' },
                  { id: 'voicemail', label: 'Left Voicemail', color: 'var(--warm-cream)', text: 'var(--text-dark)' },
                  { id: 'no_answer', label: 'No Answer / Busy', color: 'var(--warm-cream)', text: 'var(--text-muted)' },
                  { id: 'not_interested', label: 'Not Interested', color: 'var(--warm-cream)', text: 'var(--text-muted)' },
                  { id: 'wrong_number', label: 'Wrong Number', color: '#FFF3CD', text: '#856404' },
                  { id: 'do_not_contact', label: 'Do Not Contact / DNC', color: 'var(--terracotta-light)', text: 'var(--terracotta-dark)' }
                ].map(opt => (
                  <button
                    key={opt.id}
                    disabled={isSubmittingOutcome}
                    onClick={() => handleSubmitOutcome(opt.id)}
                    className="btn"
                    style={{
                      padding: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      backgroundColor: opt.color,
                      color: opt.text,
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)'
                    }}
                  >
                    {opt.label}
                  </button>
                )) : [
                  { id: 'interested', label: 'Replied: Interested', color: 'var(--sage-light)', text: 'var(--sage-dark)' },
                  { id: 'not_interested', label: 'Replied: Not Interested', color: 'var(--warm-cream)', text: 'var(--text-muted)' },
                  { id: 'bounced', label: 'Email Bounced', color: '#FFF3CD', text: '#856404' },
                  { id: 'do_not_contact', label: 'Opt-Out / Unsubscribe', color: 'var(--terracotta-light)', text: 'var(--terracotta-dark)' }
                ].map(opt => (
                  <button
                    key={opt.id}
                    disabled={isSubmittingOutcome}
                    onClick={() => handleSubmitOutcome(opt.id)}
                    className="btn"
                    style={{
                      padding: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      backgroundColor: opt.color,
                      color: opt.text,
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)'
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                Optional Notes:
              </label>
              <textarea
                rows={2}
                value={outcomeNotes}
                onChange={(e) => setOutcomeNotes(e.target.value)}
                placeholder="Details of conversation, next call date, rate expectations..."
                style={{
                  width: '100%',
                  fontSize: '0.8rem',
                  padding: '8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)'
                }}
              />
            </div>

            <div style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              backgroundColor: 'var(--warm-cream)',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '16px'
            }}>
              Selecting <strong>'Do Not Contact'</strong> or <strong>'Bounced'</strong> permanently suppresses this carrier and contact in future runs.
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                onClick={() => setSelectedLeadForOutcome(null)}
                className="btn btn-secondary"
                style={{ fontSize: '0.8rem', padding: '6px 14px' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: CAN-SPAM Compliant Draft Email Viewer */}
      {draftEmailLead && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 'var(--radius-lg)',
            width: '600px',
            maxWidth: '92%',
            padding: '24px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                  Fact-Grounded Email Draft (CAN-SPAM Compliant)
                </h3>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  For: {draftEmailLead.company} &bull; {draftEmailLead.contact_name}
                </div>
              </div>

              <span style={{
                fontSize: '0.68rem',
                backgroundColor: 'var(--warm-cream)',
                color: 'var(--text-dark)',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '999px'
              }}>
                Manual Operator Send Only
              </span>
            </div>

            {loadingDraft ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                <div>Generating fact-grounded draft...</div>
              </div>
            ) : draftEmailError ? (
              <div style={{
                padding: '28px 20px',
                textAlign: 'center',
                backgroundColor: '#FEF2F2',
                border: '1px solid #FCA5A5',
                borderRadius: 'var(--radius-md)',
                margin: '12px 0 20px'
              }}>
                <AlertTriangle size={32} color="#DC2626" style={{ margin: '0 auto 10px' }} />
                <div style={{ fontSize: '0.96rem', fontWeight: 700, color: '#991B1B', marginBottom: '8px' }}>
                  CAN-SPAM Physical Address Required
                </div>
                <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#B91C1C', marginBottom: '12px' }}>
                  {draftEmailError}
                </div>
                <div style={{ fontSize: '0.74rem', color: '#6B7280', maxWidth: '420px', margin: '0 auto', lineHeight: 1.4 }}>
                  Federal CAN-SPAM Act (15 U.S.C. § 7704(a)(5)(A)) strictly mandates a valid physical postal address and verified sender identity on all commercial outreach emails.
                </div>
                <div style={{ marginTop: '16px' }}>
                  <button
                    onClick={() => setDraftEmailLead(null)}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : draftEmailContent ? (
              <div>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)' }}>RECIPIENT:</div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-dark)' }}>
                    {draftEmailContent.recipient || draftEmailContent.recipient_email || draftEmailLead.email || 'dispatch@carrier.example.com'}
                  </div>
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)' }}>SUBJECT LINE:</div>
                  <input
                    type="text"
                    readOnly
                    value={draftEmailContent.subject}
                    style={{
                      width: '100%',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--warm-cream)'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>EMAIL BODY:</div>
                  <textarea
                    readOnly
                    rows={10}
                    value={draftEmailContent.body}
                    style={{
                      width: '100%',
                      fontSize: '0.82rem',
                      lineHeight: 1.5,
                      padding: '12px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      fontFamily: 'monospace',
                      backgroundColor: '#FAFAFA'
                    }}
                  />
                </div>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: '8px',
                  borderTop: '1px solid var(--border-subtle)'
                }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Physical Address & Unsubscribe footer verified from configuration.
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={handleCopyDraft}
                      className="btn btn-primary"
                      style={{ fontSize: '0.8rem', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      {copiedDraft ? <Check size={14} /> : <Copy size={14} />}
                      {copiedDraft ? 'Copied to Clipboard!' : 'Copy Draft'}
                    </button>
                    <button
                      onClick={() => setDraftEmailLead(null)}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* MODAL 3: Manual Authority Verification Modal (L2i) */}
      {selectedLeadForVerify && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '16px'
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 'var(--radius-lg)',
            width: '100%',
            maxWidth: '540px',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={20} color="var(--ocean-dark)" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                  Manual Authority Verification
                </h3>
              </div>
              <button
                onClick={() => setSelectedLeadForVerify(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            </div>

            {/* Target Carrier Summary Banner */}
            <div style={{
              backgroundColor: 'var(--warm-cream)',
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '16px',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>
                {selectedLeadForVerify.company}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '10px', marginTop: '4px', flexWrap: 'wrap' }}>
                <span><strong>USDOT:</strong> #{selectedLeadForVerify.usdot || 'N/A'}</span>
                <span><strong>State:</strong> {selectedLeadForVerify.state || 'N/A'}</span>
                <span><strong>Phone:</strong> {selectedLeadForVerify.phone_display || selectedLeadForVerify.phone_e164 || 'N/A'}</span>
              </div>
            </div>

            {/* SAFER Reference Box */}
            <div style={{
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 14px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E40AF' }}>
                  Verify on Official FMCSA SAFER
                </div>
                <div style={{ fontSize: '0.72rem', color: '#3B82F6' }}>
                  Search by USDOT #{selectedLeadForVerify.usdot || ''} to inspect authority & filings
                </div>
              </div>
              <a
                href="https://safer.fmcsa.dot.gov/CompanySnapshot.aspx"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary"
                style={{ fontSize: '0.72rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                Open SAFER <ExternalLink size={12} />
              </a>
            </div>

            {verifyError && (
              <div style={{
                backgroundColor: '#FEE2E2',
                border: '1px solid #FCA5A5',
                color: '#991B1B',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                marginBottom: '14px'
              }}>
                {verifyError}
              </div>
            )}

            {verifySuccess && (
              <div style={{
                backgroundColor: '#DCFCE7',
                border: '1px solid #86EFAC',
                color: '#166534',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                marginBottom: '14px'
              }}>
                {verifySuccess}
              </div>
            )}

            <form onSubmit={handleSubmitVerify}>
              {/* Verification Date */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  VERIFICATION DATE
                </label>
                <input
                  type="date"
                  value={verifyDate}
                  onChange={(e) => setVerifyDate(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: '0.82rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)'
                  }}
                  required
                />
              </div>

              {/* MC Number */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  MC DOCKET NUMBER (IF OBSERVED ON SAFER / L&I)
                </label>
                <input
                  type="text"
                  placeholder="e.g. MC-123456 or 123456"
                  value={verifyMc}
                  onChange={(e) => setVerifyMc(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: '0.82rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)'
                  }}
                />
              </div>

              {/* Authority Status & Insurance on File */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                    OPERATING AUTHORITY STATUS
                  </label>
                  <select
                    value={verifyStatus}
                    onChange={(e) => setVerifyStatus(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      fontSize: '0.82rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: '#FFFFFF'
                    }}
                  >
                    <option value="ACTIVE">ACTIVE (Authorized For Hire)</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="REVOKED">REVOKED</option>
                    <option value="DISMISSED">DISMISSED</option>
                    <option value="PENDING">PENDING</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                    INSURANCE AMOUNT ($)
                  </label>
                  <input
                    type="number"
                    value={verifyAmount}
                    onChange={(e) => setVerifyAmount(e.target.value)}
                    placeholder="750000"
                    step="50000"
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      fontSize: '0.82rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)'
                    }}
                  />
                </div>
              </div>

              {/* Insurance on file checkbox */}
              <div style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="insuranceCheck"
                  checked={verifyInsurance}
                  onChange={(e) => setVerifyInsurance(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <label htmlFor="insuranceCheck" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dark)', cursor: 'pointer' }}>
                  Confirmed active BIPD / Cargo Insurance filing on file in L&I database
                </label>
              </div>

              {/* Operator Notes */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  OPERATOR VERIFICATION NOTES
                </label>
                <textarea
                  rows={2}
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: '0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)'
                  }}
                  placeholder="Notes from SAFER / L&I lookup..."
                />
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)' }}>
                <button
                  type="button"
                  onClick={() => setSelectedLeadForVerify(null)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                  disabled={isSubmittingVerify}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', padding: '6px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  disabled={isSubmittingVerify}
                >
                  {isSubmittingVerify ? <RefreshCw size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                  {isSubmittingVerify ? 'Saving & Re-scoring...' : 'Save & Re-score Lead'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
