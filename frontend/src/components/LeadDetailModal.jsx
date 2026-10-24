import React, { useState, useEffect } from 'react';
import { 
  X, 
  CheckCircle2, 
  AlertCircle, 
  XCircle, 
  Phone, 
  Mail, 
  Globe, 
  Truck, 
  ShieldCheck, 
  Flame, 
  Copy, 
  Check, 
  Activity
} from 'lucide-react';
import { api } from '../services/api';
import { getSafeLeadUrl, getLeadUrlDisplay } from '../services/urlUtils';


export default function LeadDetailModal({ 
  companyId, 
  onClose, 
  onStatusUpdated 
}) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSubTab, setActiveSubTab] = useState('verification');
  const [overrideStatus, setOverrideStatus] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [savingStatus, setSavingStatus] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      if (!companyId) return;
      setLoading(true);
      try {
        const data = await api.getCompany(companyId);
        setLead(data);
        setOverrideStatus(data.lead_status);
      } catch (err) {
        console.error('Failed to load lead details:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [companyId]);

  const handleStatusSubmit = async (e) => {
    e.preventDefault();
    if (!overrideStatus) return;
    setSavingStatus(true);
    try {
      const updated = await api.updateCompanyStatus(
        companyId, 
        overrideStatus, 
        overrideReason || `Manual status update to ${overrideStatus}`
      );
      setLead(updated);
      if (onStatusUpdated) onStatusUpdated(updated);
      alert(`Lead status successfully updated to ${overrideStatus}!`);
    } catch (err) {
      alert(`Failed to update status: ${err.message}`);
    } finally {
      setSavingStatus(false);
    }
  };

  if (!companyId) return null;

  const isShipper = lead?.lead_type === 'SHIPPER' || (!lead?.fleet_size && (lead?.carrier_operation?.includes('Shipper') || lead?.source_name === 'direct_shippers'));
  const primaryDm = lead?.contacts?.find(c => c.is_decision_maker) || lead?.contacts?.[0];
  const dmName = primaryDm ? primaryDm.full_name : (isShipper ? 'Logistics / Supply Chain Director' : 'Fleet Owner');
  const dmFirstName = primaryDm?.first_name || dmName.split(' ')[0] || 'there';

  // AI Outreach Pitch Script Generator (Tailored for Carrier vs Direct Shipper)
  const carrierColdCallScript = `Hi ${dmFirstName}, this is [Your Name] from [Dispatch Company].
I saw ${lead?.company_name || 'your carrier team'} operates a clean fleet of ${lead?.fleet_size || 'small fleet'} ${Array.isArray(lead?.equipment) ? lead.equipment.join('/') : lead?.equipment || 'dry van'} units out of ${lead?.state || 'your region'}.
We specialize in dedicated high-rate freight booking and backhaul optimization for carriers with 2-10 trucks.
Are you currently booking all your own loads, or would having dedicated dispatch support free you up to add more profitable miles?`;

  const carrierColdEmailScript = `Subject: Dedicated Load Dispatching for ${lead?.company_name || 'Your Fleet'} — Direct Rates

Hi ${dmFirstName},

I noticed ${lead?.company_name} is actively running ${Array.isArray(lead?.equipment) ? lead.equipment.join(', ') : lead?.equipment || 'dry van/reefer'} freight in ${lead?.state || 'the region'}.

We help independent fleet owners keep their power units running consistent, premium-paying dedicated freight lanes with 0 load-board deadhead.

Would you be open to a quick 3-minute chat this week to see if our rate-per-mile averages beat what you're currently booking?

Best regards,
[Your Name]
[Your Phone Number]`;

  const shipperColdCallScript = `Hi ${dmFirstName}, this is [Your Name] with [Freight Logistics / Capacity Network].
I'm reaching out to ${lead?.company_name}'s outbound logistics team regarding your ${lead?.industry_sector || 'manufacturing'} shipping operations out of ${lead?.city || 'HQ'}, ${lead?.state || 'the region'}.
We provide dedicated, pre-vetted ${Array.isArray(lead?.equipment) ? lead.equipment.join('/') : lead?.equipment || 'dry van/reefer'} capacity for consistent outbound volume with a 99.4% on-time delivery record.
Who on your supply chain team handles your secondary carrier routing and spot quote RFP bids when you need reliable capacity?`;

  const shipperColdEmailScript = `Subject: Guaranteed Dedicated Freight Capacity for ${lead?.company_name} Outbound Shipping

Hi ${dmFirstName},

I'm reaching out regarding ${lead?.company_name}'s outbound freight logistics across ${lead?.state || 'regional'} and nationwide corridors.

We partner with major ${lead?.industry_sector || 'manufacturing and distribution'} shippers to eliminate tender rejections and provide contracted ${Array.isArray(lead?.equipment) ? lead.equipment.join(', ') : lead?.equipment || '53ft dry van and refrigerated'} capacity at stable, predictable rates.

Could we send over our carrier network overview and rate scorecard for your logistics procurement team to review this week?

Best regards,
[Your Name]
[Logistics Capacity Coordinator]
[Your Phone Number]`;

  const coldCallScript = isShipper ? shipperColdCallScript : carrierColdCallScript;
  const coldEmailScript = isShipper ? shipperColdEmailScript : carrierColdEmailScript;

  const copyScript = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(25, 25, 40, 0.45)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      padding: '20px'
    }}>
      <div 
        className="animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '820px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          backgroundColor: '#FFFFFF',
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-subtle)',
          boxShadow: 'var(--shadow-modal)'
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#FAFAFA'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                {loading ? 'Loading Profile...' : lead?.company_name}
              </h2>
              {lead && (
                <>
                  {isShipper ? (
                    <span style={{
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      backgroundColor: 'var(--warm-cream)',
                      color: 'var(--terracotta-dark)',
                      padding: '2px 10px',
                      borderRadius: '999px',
                      border: '1px solid var(--terracotta)'
                    }}>
                      📦 Direct Shipper (Needs Trucks)
                    </span>
                  ) : (
                    <span style={{
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      backgroundColor: 'var(--sage)',
                      color: 'var(--sage-dark)',
                      padding: '2px 10px',
                      borderRadius: '999px',
                      border: '1px solid var(--sage-dark)'
                    }}>
                      🚚 Motor Carrier (Has Trucks)
                    </span>
                  )}
                  {lead.priority === 'REJECTED' ? (
                    <span className="badge badge-status-rejected">
                      Rejected &bull; {lead.lead_score?.toFixed(1)}/10
                    </span>
                  ) : (
                    <span className={`badge badge-priority-${(lead.priority || 'c').toLowerCase()}`}>
                      Tier {lead.priority || 'C'} &bull; {lead.lead_score?.toFixed(1)}/10
                    </span>
                  )}
                </>
              )}
            </div>
            {lead && (
              <p className="text-xs" style={{ marginTop: '3px', color: 'var(--text-secondary)' }}>
                {isShipper ? (
                  <>Sector: <strong style={{ color: 'var(--text-dark)' }}>{lead.industry_sector || 'Freight Logistics'}</strong> &bull; {lead.city}, {lead.state} &bull; {lead.legal_name || lead.company_name}</>
                ) : (
                  <>USDOT: <strong style={{ color: 'var(--text-dark)' }}>{lead.usdot || 'N/A'}</strong> &bull; {lead.city}, {lead.state} &bull; {lead.legal_name || lead.company_name}</>
                )}
              </p>
            )}
          </div>

          <button
            onClick={onClose}
            className="btn btn-secondary btn-icon"
            style={{ width: '32px', height: '32px' }}
          >
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Activity size={24} style={{ margin: '0 auto 12px', animation: 'spin 1.5s linear infinite' }} />
            <p style={{ fontSize: '0.875rem' }}>Loading verified evidence and audit details...</p>
          </div>
        ) : lead ? (
          <>
            {/* Quick Summary Pill Bar */}
            <div style={{
              padding: '12px 24px',
              backgroundColor: 'var(--cream)',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '16px',
              fontSize: '0.775rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Phone size={13} color="var(--text-dark)" />
                <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 600 }}>{lead.phone || 'Direct Line Available'}</span>
              </div>
              {lead.email && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Mail size={13} color="var(--text-secondary)" />
                  <span>{lead.email}</span>
                </div>
              )}
              {(lead.website || lead.usdot) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Globe size={13} color="var(--text-secondary)" />
                  <a 
                    href={getSafeLeadUrl(lead)} 
                    target="_blank" 
                    rel="noreferrer" 
                    title={getSafeLeadUrl(lead)}
                    style={{ textDecoration: 'underline', color: 'var(--terracotta)', fontWeight: 600 }}
                  >
                    {getLeadUrlDisplay(lead)}
                  </a>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Truck size={13} color="var(--text-dark)" />
                <span>{isShipper ? (lead.freight_volume || 'Direct Outbound Freight') : (lead.fleet_size !== null && lead.fleet_size !== undefined ? `${lead.fleet_size} Power Units` : 'Unknown')}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ShieldCheck size={13} color="var(--sage-dark)" />
                <span>{isShipper ? 'Active Direct Shipper' : (lead.operating_status || 'Unknown')}</span>
              </div>
            </div>

            {/* Lead Status / Rejection / NOT_ICP / NEEDS_REVIEW_ICP Reason Banner */}
            {(lead.rejection_reason || lead.lead_status === 'NEEDS_REVIEW_ICP') && (
              <div style={{
                padding: '10px 24px',
                backgroundColor: (lead.lead_status === 'NOT_ICP' || lead.lead_status === 'NEEDS_REVIEW_ICP') ? '#FEF3C7' : '#FEE2E2',
                borderBottom: '1px solid ' + ((lead.lead_status === 'NOT_ICP' || lead.lead_status === 'NEEDS_REVIEW_ICP') ? '#FDE68A' : '#FECACA'),
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.775rem',
                color: (lead.lead_status === 'NOT_ICP' || lead.lead_status === 'NEEDS_REVIEW_ICP') ? '#92400E' : '#B91C1C'
              }}>
                <AlertTriangle size={14} />
                <span>
                  <strong>{lead.lead_status === 'NEEDS_REVIEW_ICP' ? 'Needs Review (ICP):' : (lead.lead_status === 'NOT_ICP' ? 'NOT ICP (Reviewable):' : 'Rejection Reason:')}</strong> {lead.rejection_reason || lead.qualification_reason}
                </span>
              </div>
            )}

            {/* Sub-Tab Navigation */}
            <div style={{
              display: 'flex',
              gap: '6px',
              borderBottom: '1px solid var(--border-subtle)',
              padding: '8px 24px',
              backgroundColor: '#FFFFFF'
            }}>
              {[
                { id: 'verification', label: `10-Point Verification (${lead.verification_records?.length || 0})` },
                { id: 'contacts', label: `Contacts & Intent (${lead.contacts?.length || 0})` },
                { id: 'outreach', label: 'AI Outreach Scripts' },
                { id: 'history', label: `Audit Timeline (${lead.status_history?.length || 0})` }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveSubTab(tab.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-pill)',
                    background: activeSubTab === tab.id ? 'var(--cream)' : 'transparent',
                    border: '1px solid',
                    borderColor: activeSubTab === tab.id ? 'var(--border-strong)' : 'transparent',
                    color: activeSubTab === tab.id ? 'var(--text-dark)' : 'var(--text-secondary)',
                    fontSize: '0.775rem',
                    fontWeight: activeSubTab === tab.id ? 700 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Sub-Tab Content Body */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* TAB 1: 10-Point Verification Checklist */}
              {activeSubTab === 'verification' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 700 }}>Verification Rules & Audit Evidence</h4>
                    <span className="badge badge-status-final">
                      Confidence: {Math.round((lead.verification_confidence || 0.8) * 100)}%
                    </span>
                  </div>

                  {(lead.verification_records || []).map((v, i) => (
                    <div 
                      key={v.id || i}
                      style={{
                        padding: '12px 16px',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: '#FAFAFA',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '12px'
                      }}
                    >
                      {v.status === 'PASSED' ? (
                        <CheckCircle2 size={16} color="var(--sage-dark)" style={{ marginTop: '2px', flexShrink: 0 }} />
                      ) : v.status === 'WARNING' ? (
                        <AlertCircle size={16} color="var(--warning-text)" style={{ marginTop: '2px', flexShrink: 0 }} />
                      ) : (
                        <XCircle size={16} color="var(--danger-text)" style={{ marginTop: '2px', flexShrink: 0 }} />
                      )}

                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--text-dark)' }}>
                            {v.step_name}
                          </span>
                          <span className={`badge ${v.status === 'PASSED' ? 'badge-status-final' : 'badge-status-review'}`}>
                            {v.status}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          {v.evidence_text || 'Criteria evaluated automatically.'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 2: Contacts & Intent */}
              {activeSubTab === 'contacts' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>
                      Identified Decision Makers & Staff ({lead.contacts?.length || 0})
                    </h4>
                    {(lead.contacts || []).length === 0 ? (
                      <p className="text-xs">No direct personal contact profiles found.</p>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
                        {lead.contacts.map((ct) => (
                          <div 
                            key={ct.id}
                            style={{
                              padding: '14px',
                              borderRadius: 'var(--radius-md)',
                              backgroundColor: '#FAFAFA',
                              border: ct.is_decision_maker ? '1px solid var(--border-strong)' : '1px solid var(--border-subtle)'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-dark)' }}>
                                {ct.full_name}
                              </span>
                              {ct.is_decision_maker && (
                                <span className="badge" style={{ backgroundColor: 'var(--purple-bg)', color: 'var(--purple-text)' }}>
                                  Decision Maker
                                </span>
                              )}
                            </div>
                            <p className="text-xs" style={{ marginBottom: '8px' }}>
                              {ct.title || 'Staff / Dispatch'}
                            </p>
                            {ct.email && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                                ✉ {ct.email}
                              </div>
                            )}
                            {ct.phone && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-dark)', fontFamily: 'JetBrains Mono' }}>
                                📞 {ct.phone}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Intent Signals */}
                  <div>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '10px' }}>
                      Detected Business Intent Signals ({lead.intent_signals?.length || 0})
                    </h4>
                    {(lead.intent_signals || []).length === 0 ? (
                      <p className="text-xs">No public hiring or fleet expansion signals detected.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {lead.intent_signals.map((sig) => (
                          <div
                            key={sig.id}
                            style={{
                              padding: '12px 14px',
                              borderRadius: 'var(--radius-md)',
                              backgroundColor: 'var(--peach-light)',
                              border: '1px solid var(--peach)',
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: '10px'
                            }}
                          >
                            <Flame size={16} color="var(--peach-dark)" style={{ marginTop: '2px', flexShrink: 0 }} />
                            <div>
                              <div style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--peach-dark)' }}>
                                {sig.title}
                              </div>
                              <p style={{ fontSize: '0.775rem', color: 'var(--peach-dark)', opacity: 0.9, marginTop: '2px' }}>
                                "{sig.description}"
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 3: AI Outreach Scripts */}
              {activeSubTab === 'outreach' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Cold Call Script */}
                  <div style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: '#FAFAFA',
                    border: '1px solid var(--border-subtle)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Phone size={14} color="var(--text-dark)" />
                        <h4 style={{ fontSize: '0.85rem', fontWeight: 700 }}>Personalized Cold Call Pitch</h4>
                      </div>
                      <button
                        onClick={() => copyScript(coldCallScript)}
                        className="btn btn-secondary btn-sm"
                      >
                        {copied ? <Check size={13} color="var(--success-text)" /> : <Copy size={13} />}
                        <span>{copied ? 'Copied' : 'Copy Script'}</span>
                      </button>
                    </div>
                    <pre style={{
                      backgroundColor: 'var(--cream)',
                      padding: '12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.775rem',
                      color: 'var(--text-dark)',
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.5,
                      border: '1px solid var(--border-subtle)'
                    }}>
                      {coldCallScript}
                    </pre>
                  </div>

                  {/* Cold Email Pitch */}
                  <div style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: '#FAFAFA',
                    border: '1px solid var(--border-subtle)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Mail size={14} color="var(--text-dark)" />
                        <h4 style={{ fontSize: '0.85rem', fontWeight: 700 }}>Direct Outreach Email Template</h4>
                      </div>
                      <button
                        onClick={() => copyScript(coldEmailScript)}
                        className="btn btn-secondary btn-sm"
                      >
                        {copied ? <Check size={13} color="var(--success-text)" /> : <Copy size={13} />}
                        <span>{copied ? 'Copied' : 'Copy Email'}</span>
                      </button>
                    </div>
                    <pre style={{
                      backgroundColor: 'var(--cream)',
                      padding: '12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.775rem',
                      color: 'var(--text-dark)',
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.5,
                      border: '1px solid var(--border-subtle)'
                    }}>
                      {coldEmailScript}
                    </pre>
                  </div>
                </div>
              )}

              {/* TAB 4: Audit History */}
              {activeSubTab === 'history' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>
                    Status & Verification Audit Trail
                  </h4>
                  {(lead.status_history || []).map((h) => (
                    <div 
                      key={h.id}
                      style={{
                        padding: '10px 14px',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: '#FAFAFA',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '0.775rem'
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 700, color: 'var(--text-dark)' }}>
                          {h.from_status || 'INIT'} ➔ {h.to_status}
                        </span>
                        <p className="text-xs" style={{ marginTop: '2px' }}>
                          {h.reason || 'Automated pipeline progression'}
                        </p>
                      </div>
                      <span className="text-xs">
                        {new Date(h.changed_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}

            </div>

            {/* Modal Footer / Status Override Bar */}
            <form onSubmit={handleStatusSubmit} style={{
              padding: '14px 24px',
              borderTop: '1px solid var(--border-subtle)',
              backgroundColor: '#FAFAFA',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '260px' }}>
                <select
                  value={overrideStatus}
                  onChange={(e) => setOverrideStatus(e.target.value)}
                  className="form-select"
                  style={{ width: '150px', height: '36px', borderRadius: 'var(--radius-pill)', fontSize: '0.775rem' }}
                >
                  <option value="FINAL">FINAL (Approved)</option>
                  <option value="QUALIFIED">QUALIFIED</option>
                  <option value="NEEDS_ENRICHMENT">NEEDS ENRICHMENT</option>
                  <option value="NEEDS_REVIEW">NEEDS REVIEW</option>
                  <option value="NEEDS_REVIEW_ICP">NEEDS REVIEW (ICP)</option>
                  <option value="NOT_ICP">NOT ICP</option>
                  <option value="ARCHIVED_NO_CONTACT">ARCHIVED NO CONTACT</option>
                  <option value="REJECTED">REJECTED</option>
                </select>

                <input
                  type="text"
                  placeholder="Override reason note (e.g. Verified active carrier via phone)"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  className="form-input"
                  style={{ flex: 1, height: '36px', borderRadius: 'var(--radius-pill)', fontSize: '0.775rem' }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={savingStatus}
              >
                {savingStatus ? 'Saving...' : 'Update Lead Status'}
              </button>
            </form>
          </>
        ) : null}
      </div>
    </div>
  );
}
