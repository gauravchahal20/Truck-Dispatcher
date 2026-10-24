import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  CheckCircle2, 
  AlertCircle, 
  XCircle, 
  Phone, 
  Mail, 
  Sparkles, 
  Truck, 
  Package,
  RefreshCw,
  Check,
  ChevronRight,
  Download,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';
import { getSafeLeadUrl, getLeadUrlDisplay } from '../services/urlUtils';


const US_STATES_LIST = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
];

export default function LeadsTable({ 
  initialRunId = null, 
  onViewLead,
  globalSearch = ''
}) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState(globalSearch || '');
  const [leadTypeFilter, setLeadTypeFilter] = useState('ALL'); // 'ALL', 'CARRIER', 'SHIPPER'
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [stateFilter, setStateFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [limitFilter, setLimitFilter] = useState(100);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    if (globalSearch) {
      setSearchTerm(globalSearch);
    }
  }, [globalSearch]);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const data = await api.getCompanies({
        search: searchTerm || undefined,
        lead_status: statusFilter !== 'ALL' ? statusFilter : undefined,
        state: stateFilter || undefined,
        priority: priorityFilter || undefined,
        run_id: initialRunId || undefined,
        limit: limitFilter || 100
      });
      setLeads(data || []);
    } catch (err) {
      console.error('Failed to fetch companies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [statusFilter, stateFilter, priorityFilter, limitFilter, initialRunId, searchTerm]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchLeads();
  };

  const handleQuickStatusUpdate = async (companyId, newStatus, e) => {
    e.stopPropagation();
    try {
      await api.updateCompanyStatus(companyId, newStatus, `Updated to ${newStatus} via Quick Action`);
      setLeads(prev => prev.map(l => l.id === companyId ? { ...l, lead_status: newStatus } : l));
    } catch (err) {
      alert(`Failed to update status: ${err.message}`);
    }
  };

  const copyToClipboard = (text, id, e) => {
    e.stopPropagation();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Direct CSV Export in Browser
  const exportToCSV = () => {
    if (!leads || leads.length === 0) {
      alert('No leads available to export.');
      return;
    }

    const headers = [
      "Company Name", "Lead Type", "Industry / Sector", "Legal Name", "USDOT", "MC Number", "City", "State", "Zip",
      "Fleet / Freight Volume", "Equipment", "Phone", "Email", "Decision Maker", "DM Title",
      "Lead Status", "Priority", "Lead Score", "Operating Status"
    ];

    const rows = filteredLeads.map(l => {
      const dm = (l.contacts && l.contacts.find(c => c.is_decision_maker)) || (l.contacts && l.contacts[0]);
      const isShipper = l.lead_type === 'SHIPPER' || (!l.fleet_size && l.carrier_operation?.includes('Shipper'));
      const volumeOrFleet = isShipper ? (l.freight_volume || 'Direct Freight Demand') : (l.fleet_size !== null && l.fleet_size !== undefined ? `${l.fleet_size} Trucks` : 'Unknown');

      return [
        `"${(l.company_name || '').replace(/"/g, '""')}"`,
        `"${isShipper ? 'Shipper (Needs Trucks)' : 'Carrier (Has Trucks)'}"`,
        `"${(l.industry_sector || 'Logistics').replace(/"/g, '""')}"`,
        `"${(l.legal_name || '').replace(/"/g, '""')}"`,
        `"${l.usdot || ''}"`,
        `"${l.mc_number || ''}"`,
        `"${l.city || 'Unknown'}"`,
        `"${l.state || ''}"`,
        `"${l.zip_code || ''}"`,
        `"${volumeOrFleet}"`,
        `"${(Array.isArray(l.equipment) && l.equipment.length > 0 ? l.equipment.join(', ') : (l.equipment || 'Unknown')).replace(/"/g, '""')}"`,
        `"${l.phone || ''}"`,
        `"${l.email || ''}"`,
        `"${(dm ? dm.full_name : '').replace(/"/g, '""')}"`,
        `"${(dm ? dm.title : '').replace(/"/g, '""')}"`,
        `"${l.lead_status || ''}"`,
        `"${l.priority || ''}"`,
        `"${l.lead_score || ''}"`,
        `"${l.operating_status || 'Unknown'}"`
      ].join(',');
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `trucklead_verified_leads_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Client-side filtering by Lead Type (Carriers with trucks vs Shippers needing trucks)
  const filteredLeads = leads.filter(l => {
    if (leadTypeFilter === 'ALL') return true;
    const isShipper = l.lead_type === 'SHIPPER' || (!l.fleet_size && (l.carrier_operation?.includes('Shipper') || l.source_name === 'direct_shippers'));
    if (leadTypeFilter === 'SHIPPER') return isShipper;
    if (leadTypeFilter === 'CARRIER') return !isShipper;
    return true;
  });

  const carriersCount = leads.filter(l => l.lead_type !== 'SHIPPER' && (l.fleet_size || !l.carrier_operation?.includes('Shipper'))).length;
  const shippersCount = leads.filter(l => l.lead_type === 'SHIPPER' || l.carrier_operation?.includes('Shipper') || l.source_name === 'direct_shippers').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Two-Sided Market Filter Banner */}
      <div className="bento-card" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Lead Persona:
          </span>

          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              onClick={() => setLeadTypeFilter('ALL')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '999px',
                fontSize: '0.75rem',
                fontWeight: leadTypeFilter === 'ALL' ? 700 : 500,
                backgroundColor: leadTypeFilter === 'ALL' ? 'var(--text-dark)' : '#FFFFFF',
                color: leadTypeFilter === 'ALL' ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid',
                borderColor: leadTypeFilter === 'ALL' ? 'var(--text-dark)' : 'var(--border-subtle)',
                cursor: 'pointer'
              }}
            >
              <span>All Leads</span>
              <span style={{ fontSize: '0.65rem', opacity: 0.8 }}>({leads.length})</span>
            </button>

            <button
              onClick={() => setLeadTypeFilter('CARRIER')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '999px',
                fontSize: '0.75rem',
                fontWeight: leadTypeFilter === 'CARRIER' ? 700 : 500,
                backgroundColor: leadTypeFilter === 'CARRIER' ? 'var(--sage)' : '#FFFFFF',
                color: leadTypeFilter === 'CARRIER' ? 'var(--sage-dark)' : 'var(--text-secondary)',
                border: '1px solid',
                borderColor: leadTypeFilter === 'CARRIER' ? 'var(--sage-dark)' : 'var(--border-subtle)',
                cursor: 'pointer'
              }}
            >
              <Truck size={14} />
              <span>Have Trucks (Carriers)</span>
              <span style={{ fontSize: '0.65rem', fontWeight: 700 }}>({carriersCount})</span>
            </button>

            <button
              onClick={() => setLeadTypeFilter('SHIPPER')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '999px',
                fontSize: '0.75rem',
                fontWeight: leadTypeFilter === 'SHIPPER' ? 700 : 500,
                backgroundColor: leadTypeFilter === 'SHIPPER' ? 'var(--terracotta)' : '#FFFFFF',
                color: leadTypeFilter === 'SHIPPER' ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid',
                borderColor: leadTypeFilter === 'SHIPPER' ? 'var(--terracotta)' : 'var(--border-subtle)',
                cursor: 'pointer'
              }}
            >
              <Package size={14} />
              <span>Need Trucks (Shippers)</span>
              <span style={{ fontSize: '0.65rem', fontWeight: 700 }}>({shippersCount})</span>
            </button>
          </div>
        </div>

        {/* Quick CSV Export Button */}
        <button
          onClick={exportToCSV}
          className="button-secondary"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 14px',
            fontSize: '0.75rem',
            fontWeight: 600,
            borderRadius: 'var(--radius-sm)'
          }}
        >
          <Download size={14} />
          <span>Export CSV ({filteredLeads.length})</span>
        </button>
      </div>

      {/* Filter Controls Card */}
      <div className="bento-card" style={{ padding: '16px 20px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          
          {/* Search Box */}
          <div style={{ position: 'relative', flex: '1', minWidth: '220px' }}>
            <Search size={15} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search company, DOT, city, contact name, or industry..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="form-input"
              style={{ paddingLeft: '34px', height: '36px', fontSize: '0.775rem' }}
            />
          </div>

          {/* Status Filter */}
          <div style={{ minWidth: '130px' }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="form-select"
              style={{ height: '36px', fontSize: '0.775rem' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="FINAL">FINAL (Approved)</option>
              <option value="QUALIFIED">QUALIFIED</option>
              <option value="NEEDS_ENRICHMENT">NEEDS ENRICHMENT</option>
              <option value="RESEARCHING">RESEARCHING</option>
              <option value="NEEDS_REVIEW">NEEDS REVIEW</option>
              <option value="NEEDS_REVIEW_ICP">NEEDS REVIEW (ICP)</option>
              <option value="NOT_ICP">NOT ICP</option>
              <option value="ARCHIVED_NO_CONTACT">ARCHIVED NO CONTACT</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div style={{ minWidth: '120px' }}>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="form-select"
              style={{ height: '36px', fontSize: '0.775rem' }}
            >
              <option value="">All Priorities</option>
              <option value="A">Priority A (≥ 8.0)</option>
              <option value="B">Priority B (6.0 - 7.9)</option>
              <option value="C">Priority C (5.0 - 5.9)</option>
              <option value="REJECTED">Rejected (&lt; 5.0)</option>
            </select>
          </div>

          {/* State Filter */}
          <div style={{ minWidth: '110px' }}>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="form-select"
              style={{ height: '36px', fontSize: '0.775rem' }}
            >
              <option value="">All States</option>
              {US_STATES_LIST.map(st => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
          </div>

          {/* Refresh Action */}
          <button
            type="button"
            onClick={fetchLeads}
            className="button-ghost"
            style={{ height: '36px', padding: '0 12px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem' }}
          >
            <RefreshCw size={13} />
            <span>Refresh</span>
          </button>
        </form>
      </div>

      {/* Leads Table Container */}
      <div className="bento-card" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--text-dark)' }}>
              Verified Logistics Opportunities
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '8px' }}>
              Showing {filteredLeads.length} verified records
            </span>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table-minimal" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: '22%' }}>Company &amp; Website</th>
                <th style={{ width: '14%' }}>Lead Type &amp; Market</th>
                <th style={{ width: '16%' }}>Capacity / Demand</th>
                <th style={{ width: '20%' }}>Decision Maker</th>
                <th style={{ width: '16%' }}>Contact Info</th>
                <th style={{ width: '12%', textAlign: 'right' }}>Score &amp; Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading verified leads...
                  </td>
                </tr>
              ) : filteredLeads.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No leads found matching your criteria. Try adjusting filters or launching a new lead run.
                  </td>
                </tr>
              ) : (
                filteredLeads.map((lead) => {
                  const dm = (lead.contacts && lead.contacts.find(c => c.is_decision_maker)) || (lead.contacts && lead.contacts[0]);
                  const isShipper = lead.lead_type === 'SHIPPER' || (!lead.fleet_size && (lead.carrier_operation?.includes('Shipper') || lead.source_name === 'direct_shippers'));

                  return (
                    <tr 
                      key={lead.id}
                      onClick={() => onViewLead(lead)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* 1. Company Name & Website */}
                      <td>
                        <div style={{ fontWeight: 700, color: 'var(--text-dark)', fontSize: '0.825rem', marginBottom: '2px' }}>
                          {lead.company_name}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          <span>{lead.city || 'Unknown'}, {lead.state || 'N/A'}</span>
                          {lead.usdot && (
                            <span style={{ color: 'var(--text-muted)' }}>&bull; DOT {lead.usdot}</span>
                          )}
                        </div>
                        {(lead.website || lead.usdot) && (
                          <div style={{ marginTop: '3px' }}>
                            <a 
                              href={getSafeLeadUrl(lead)} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              title={getSafeLeadUrl(lead)}
                              style={{ 
                                fontSize: '0.7rem', 
                                color: 'var(--terracotta)', 
                                textDecoration: 'none',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '3px'
                              }}
                            >
                              <span>{getLeadUrlDisplay(lead)}</span>
                              <ExternalLink size={10} />
                            </a>
                          </div>
                        )}
                      </td>

                      {/* 2. Lead Type Badge & Sector */}
                      <td>
                        <div style={{ marginBottom: '4px' }}>
                          {isShipper ? (
                            <span style={{
                              fontSize: '0.675rem',
                              fontWeight: 700,
                              backgroundColor: 'var(--warm-cream)',
                              color: 'var(--terracotta-dark)',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}>
                              <Package size={11} />
                              <span>Needs Trucks</span>
                            </span>
                          ) : (
                            <span style={{
                              fontSize: '0.675rem',
                              fontWeight: 700,
                              backgroundColor: 'var(--sage)',
                              color: 'var(--sage-dark)',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}>
                              <Truck size={11} />
                              <span>Has Trucks</span>
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>
                          {lead.industry_sector || (isShipper ? 'Manufacturing / Freight' : 'Motor Freight')}
                        </div>
                      </td>

                      {/* 3. Capacity or Freight Volume */}
                      <td>
                        <div style={{ fontSize: '0.775rem', fontWeight: 600, color: 'var(--text-dark)' }}>
                          {isShipper ? (
                            lead.freight_volume || 'Daily FTL Freight'
                          ) : (
                            lead.fleet_size !== null && lead.fleet_size !== undefined ? `${lead.fleet_size} Power Units` : 'Unknown'
                          )}
                        </div>
                        <div style={{ fontSize: '0.675rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          {Array.isArray(lead.equipment) && lead.equipment.length > 0 ? lead.equipment.slice(0, 2).join(', ') : (lead.equipment || 'Unknown')}
                        </div>
                      </td>

                      {/* 4. Decision Maker */}
                      <td>
                        {dm ? (
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '0.775rem', color: 'var(--text-dark)' }}>
                              {dm.full_name}
                            </div>
                            <div style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>
                              {dm.title || 'Executive Leadership'}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            Operations Desk
                          </span>
                        )}
                      </td>

                      {/* 5. Contact Info */}
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          {lead.phone && (
                            <div 
                              onClick={(e) => copyToClipboard(lead.phone, `ph-${lead.id}`, e)}
                              style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '4px', 
                                fontSize: '0.725rem', 
                                color: 'var(--text-dark)',
                                cursor: 'pointer'
                              }}
                              title="Click to copy phone"
                            >
                              <Phone size={11} color="var(--text-muted)" />
                              <span>{lead.phone}</span>
                              {copiedId === `ph-${lead.id}` && <Check size={11} color="var(--sage-dark)" />}
                            </div>
                          )}

                          {lead.email && (
                            <div 
                              onClick={(e) => copyToClipboard(lead.email, `em-${lead.id}`, e)}
                              style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '4px', 
                                fontSize: '0.7rem', 
                                color: 'var(--text-secondary)',
                                cursor: 'pointer',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                maxWidth: '180px'
                              }}
                              title="Click to copy email"
                            >
                              <Mail size={11} color="var(--text-muted)" />
                              <span>{lead.email}</span>
                              {copiedId === `em-${lead.id}` && <Check size={11} color="var(--sage-dark)" />}
                            </div>
                          )}
                        </div>
                      </td>

                      {/* 6. Score & Priority Actions */}
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                          <span style={{
                            fontSize: '0.7rem',
                            fontWeight: 800,
                            padding: '2px 7px',
                            borderRadius: '999px',
                            backgroundColor: lead.lead_status === 'ARCHIVED_NO_CONTACT' ? '#f1f5f9' : (lead.lead_status === 'NEEDS_REVIEW_ICP' || lead.priority === 'NEEDS_REVIEW_ICP' ? '#fef3c7' : (lead.priority === 'A' ? 'var(--sage)' : (lead.priority === 'B' ? 'var(--warm-cream)' : (lead.priority === 'C' ? 'var(--sand-light)' : '#fee2e2')))),
                            color: lead.lead_status === 'ARCHIVED_NO_CONTACT' ? '#64748b' : (lead.lead_status === 'NEEDS_REVIEW_ICP' || lead.priority === 'NEEDS_REVIEW_ICP' ? '#92400E' : (lead.priority === 'A' ? 'var(--sage-dark)' : (lead.priority === 'B' ? 'var(--terracotta-dark)' : (lead.priority === 'C' ? 'var(--text-secondary)' : '#991b1b'))))
                          }}>
                            {lead.lead_status === 'ARCHIVED_NO_CONTACT' ? 'Archived (No Contact)' : (lead.lead_status === 'NEEDS_REVIEW_ICP' || lead.priority === 'NEEDS_REVIEW_ICP' ? 'Needs Review (ICP)' : (lead.priority === 'REJECTED' ? `Rejected (${lead.lead_score ?? 0})` : (lead.priority === 'NOT_ICP' ? 'NOT ICP' : `Tier ${lead.priority || 'C'} (${lead.lead_score ?? 0})`)))}
                          </span>

                          <ChevronRight size={14} color="var(--text-muted)" />
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
