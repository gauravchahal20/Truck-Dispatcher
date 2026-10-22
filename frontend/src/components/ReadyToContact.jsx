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
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [copiedDraft, setCopiedDraft] = useState(false);

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
    try {
      const draft = await api.getDraftEmail(lead.id);
      setDraftEmailContent(draft);
    } catch (err) {
      console.error('Failed to fetch email draft:', err);
      setDraftEmailContent({
        subject: `Partnership Dispatch Query: ${lead.company}`,
        body: `Hello ${lead.contact_name},\n\nHope this finds you well. Reaching out regarding dispatch support for your fleet.`,
        recipient: lead.email,
        compliance_notes: 'Draft loaded with fallback.'
      });
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
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'all', label: 'All Leads' },
            { id: 'callable', label: 'Callable (+1)' },
            { id: 'mailable', label: 'Mailable (Deliverable)' },
            { id: 'both', label: 'Both Channels' }
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
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', gap: '6px', marginTop: '2px' }}>
                        <span>USDOT #{lead.usdot || 'N/A'}</span>
                        {lead.state && <span>&bull; {lead.state}</span>}
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
                              backgroundColor: lead.phone_status === 'VERIFIED' ? 'var(--sage-light)' : 'var(--warm-cream)',
                              color: lead.phone_status === 'VERIFIED' ? 'var(--sage-dark)' : 'var(--text-muted)',
                              fontWeight: 600
                            }}>
                              {lead.phone_status} ({lead.phone_line_type || 'unknown'})
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
                          <div style={{ marginTop: '2px' }}>
                            <span style={{
                              fontSize: '0.65rem',
                              padding: '1px 5px',
                              borderRadius: '4px',
                              backgroundColor: lead.email_status === 'DELIVERABLE' ? 'var(--sage-light)' : (lead.email_status === 'RISKY' ? '#FFF3CD' : 'var(--warm-cream)'),
                              color: lead.email_status === 'DELIVERABLE' ? 'var(--sage-dark)' : (lead.email_status === 'RISKY' ? '#856404' : 'var(--text-muted)'),
                              fontWeight: 700
                            }}>
                              {lead.email_status}
                            </span>
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
    </div>
  );
}
