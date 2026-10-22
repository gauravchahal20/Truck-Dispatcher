import React, { useState } from 'react';
import { 
  X, 
  Sparkles, 
  Truck, 
  Package,
  Layers,
  Play, 
  Check, 
  ShieldCheck, 
  MapPin, 
  Zap, 
  Search,
  CheckSquare,
  Square,
  BookOpen
} from 'lucide-react';
import { api } from '../services/api';

const ALL_50_STATES = [
  { code: 'AL', name: 'Alabama' },
  { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' },
  { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' },
  { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' },
  { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' },
  { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' },
  { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' }
];

const REGIONAL_PRESETS = [
  { label: 'All 50 States', states: ALL_50_STATES.map(s => s.code) },
  { label: 'Top 10 Freight Hubs', states: ['TX', 'GA', 'FL', 'IL', 'OH', 'PA', 'CA', 'NC', 'IN', 'TN'] },
  { label: 'Southeast Corridor', states: ['GA', 'FL', 'NC', 'SC', 'TN', 'AL', 'MS'] },
  { label: 'Midwest Logistics', states: ['IL', 'OH', 'IN', 'MI', 'MO', 'IA', 'WI', 'MN'] },
  { label: 'Texas Triangle', states: ['TX', 'OK', 'AR', 'LA', 'NM'] },
  { label: 'West Coast / Pacific', states: ['CA', 'WA', 'OR', 'AZ', 'NV', 'UT'] },
  { label: 'Northeast Region', states: ['PA', 'NJ', 'NY', 'MD', 'VA', 'CT', 'MA'] },
];

const SOURCE_CHANNELS = [
  { id: 'fmcsa_safer', label: 'FMCSA SAFER Snapshot', desc: 'Active motor carriers & power unit census' },
  { id: 'fmcsa_li', label: 'FMCSA Licensing & Insurance', desc: 'Operating authority & $750k+ BIPD insurance' },
  { id: 'direct_shippers', label: 'Direct Shippers & Manufacturers', desc: 'Companies with outbound freight who need trucks' },
  { id: 'google_maps', label: 'Google Maps & Local Yards', desc: 'Brick-and-mortar local carrier yards & direct phones' },
  { id: 'google_search', label: 'Google Advanced Boolean', desc: 'Carrier websites, freight portals & unlisted fleets' },
  { id: 'indeed', label: 'Indeed & ZipRecruiter Hiring', desc: 'High-intent hiring signals for dispatchers & fleet ops' },
  { id: 'industry_directories', label: 'ATA Associations & Carrier411', desc: '50 State ATA associations, BBB & Chamber registries' },
  { id: 'procurement_news', label: 'SAM.gov & Freight News', desc: 'Federal freight contract awards & expansion events' },
  { id: 'specialized_verticals', label: 'Port Drayage & Dispatch Intent', desc: 'Sea ports, logistics parks & "looking for dispatcher"' },
  { id: 'b2b_enrichment', label: 'Apollo & Lusha B2B Intel', desc: 'Owner/Fleet Executive direct emails & phone dials' }
];

const EQUIPMENT_OPTIONS = [
  { id: 'dry_van', label: 'Dry Van (53ft)', popular: true },
  { id: 'reefer', label: 'Reefer (Refrigerated)', popular: true },
  { id: 'flatbed', label: 'Flatbed (48/53ft)', popular: true },
  { id: 'stepdeck', label: 'Stepdeck / Dropdeck', popular: false },
  { id: 'hotshot', label: 'Hotshot (40ft Gooseneck)', popular: true },
  { id: 'box_truck', label: 'Straight Box Truck (26ft)', popular: true },
  { id: 'power_only', label: 'Power Only (Hook & Drop)', popular: false },
  { id: 'drayage', label: 'Port / Rail Drayage', popular: false },
  { id: 'tanker', label: 'Liquid / Bulk Tanker', popular: false },
  { id: 'car_hauler', label: 'Car Hauler (Auto Transport)', popular: false },
];

export default function NewRunModal({ onClose, onRunStarted }) {
  const [name, setName] = useState(`Two-Sided Freight Run - ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`);
  const [leadType, setLeadType] = useState('ALL'); // 'ALL', 'CARRIER', 'SHIPPER'
  const [selectedStates, setSelectedStates] = useState(['TX', 'GA', 'FL', 'IL', 'OH', 'PA', 'CA', 'NC', 'IN', 'TN']);
  const [stateSearch, setStateSearch] = useState('');
  const [fleetMin, setFleetMin] = useState(1);
  const [fleetMax, setFleetMax] = useState(9999);
  const [fleetPreset, setFleetPreset] = useState('ALL'); // 'ALL', 'SOLO', 'SMALL', 'MID', 'LARGE', 'CUSTOM'
  const [selectedEquipment, setSelectedEquipment] = useState(['dry_van', 'reefer', 'flatbed', 'hotshot', 'box_truck']);
  const [selectedSources, setSelectedSources] = useState(SOURCE_CHANNELS.map(s => s.id));
  const [targetCount, setTargetCount] = useState(50);
  const [scoreThreshold, setScoreThreshold] = useState(5.0);
  const [submitting, setSubmitting] = useState(false);

  const applyFleetPreset = (presetKey) => {
    setFleetPreset(presetKey);
    if (presetKey === 'ALL') {
      setFleetMin(1);
      setFleetMax(9999);
    } else if (presetKey === 'SOLO') {
      setFleetMin(1);
      setFleetMax(1);
    } else if (presetKey === 'SMALL') {
      setFleetMin(2);
      setFleetMax(10);
    } else if (presetKey === 'MID') {
      setFleetMin(11);
      setFleetMax(50);
    } else if (presetKey === 'LARGE') {
      setFleetMin(51);
      setFleetMax(9999);
    }
  };

  const toggleState = (code) => {
    setSelectedStates(prev => 
      prev.includes(code) ? prev.filter(s => s !== code) : [...prev, code]
    );
  };

  const applyPreset = (states) => {
    setSelectedStates(states);
  };

  const selectAllEquipment = () => {
    setSelectedEquipment(EQUIPMENT_OPTIONS.map(e => e.id));
  };

  const toggleEquipment = (id) => {
    setSelectedEquipment(prev =>
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]
    );
  };

  const toggleSource = (id) => {
    setSelectedSources(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    );
  };

  const filteredStates = ALL_50_STATES.filter(s => 
    s.name.toLowerCase().includes(stateSearch.toLowerCase()) || 
    s.code.toLowerCase().includes(stateSearch.toLowerCase())
  );

  const handleLaunch = async (e) => {
    e.preventDefault();
    if (selectedStates.length === 0) {
      alert('Please select at least one target U.S. state.');
      return;
    }
    if (selectedEquipment.length === 0) {
      alert('Please select at least one equipment type.');
      return;
    }

    setSubmitting(true);
    try {
      const run = await api.createRun({
        name,
        target_states: selectedStates,
        lead_type: leadType,
        fleet_size_min: Number(fleetMin),
        fleet_size_max: Number(fleetMax),
        equipment_types: selectedEquipment,
        target_lead_count: Number(targetCount),
        score_threshold: Number(scoreThreshold)
      });
      if (onRunStarted) onRunStarted(run);
      onClose();
    } catch (err) {
      alert(`Failed to launch pipeline run: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(25, 25, 40, 0.5)',
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
          maxWidth: '780px',
          maxHeight: '90vh',
          backgroundColor: '#FFFFFF',
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-subtle)',
          boxShadow: 'var(--shadow-modal)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#FAFAFA'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-pill)',
              backgroundColor: 'var(--text-dark)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF'
            }}>
              <Zap size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                Generate Verified Trucking &amp; Freight Leads
              </h2>
              <p className="text-xs">
                Two-sided lead discovery: Carriers (who have trucks) and Direct Shippers (who need trucks)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="btn btn-secondary btn-icon"
            style={{ width: '32px', height: '32px' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleLaunch} style={{ padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
          
          {/* 1. Two-Sided Market Objective Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)', marginBottom: '8px' }}>
              Target Lead Persona / Market Side
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              
              {/* Option 1: Both */}
              <div
                onClick={() => setLeadType('ALL')}
                style={{
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: '2px solid',
                  borderColor: leadType === 'ALL' ? 'var(--text-dark)' : 'var(--border-subtle)',
                  backgroundColor: leadType === 'ALL' ? 'var(--cream)' : '#FFFFFF',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Layers size={16} color="var(--text-dark)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-dark)' }}>
                    Both Sides (Unified)
                  </span>
                </div>
                <p style={{ fontSize: '0.675rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.3 }}>
                  Balanced pipeline of both shippers with loads and carriers with trucks.
                </p>
              </div>

              {/* Option 2: Have Trucks (Carriers) */}
              <div
                onClick={() => setLeadType('CARRIER')}
                style={{
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: '2px solid',
                  borderColor: leadType === 'CARRIER' ? 'var(--sage-dark)' : 'var(--border-subtle)',
                  backgroundColor: leadType === 'CARRIER' ? 'var(--sage-light)' : '#FFFFFF',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Truck size={16} color="var(--sage-dark)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--sage-dark)' }}>
                    Have Trucks (Carriers)
                  </span>
                </div>
                <p style={{ fontSize: '0.675rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.3 }}>
                  Small fleets &amp; owner-operators seeking dispatch services &amp; loads.
                </p>
              </div>

              {/* Option 3: Need Trucks (Shippers) */}
              <div
                onClick={() => setLeadType('SHIPPER')}
                style={{
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: '2px solid',
                  borderColor: leadType === 'SHIPPER' ? 'var(--terracotta)' : 'var(--border-subtle)',
                  backgroundColor: leadType === 'SHIPPER' ? 'var(--warm-cream)' : '#FFFFFF',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Package size={16} color="var(--terracotta)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--terracotta-dark)' }}>
                    Need Trucks (Shippers)
                  </span>
                </div>
                <p style={{ fontSize: '0.675rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.3 }}>
                  Direct manufacturers &amp; distributors with freight needing carrier capacity.
                </p>
              </div>

            </div>
          </div>

          {/* Run Identifier */}
          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)', marginBottom: '6px' }}>
              Run Identifier
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="form-input"
              required
            />
          </div>

          {/* Lead Volume Presets */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                Target Lead Volume
              </label>
              <span className="text-xs">
                Requested: <strong>{targetCount} Qualified Leads</strong>
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
              {[
                { count: 25, label: '25 Fast' },
                { count: 50, label: '50 Standard' },
                { count: 100, label: '100 Scale' },
                { count: 250, label: '250 Bulk' },
                { count: 500, label: '500 Mega' },
              ].map(p => (
                <button
                  key={p.count}
                  type="button"
                  onClick={() => setTargetCount(p.count)}
                  style={{
                    padding: '8px 4px',
                    borderRadius: 'var(--radius-pill)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    border: '1px solid',
                    borderColor: targetCount === p.count ? 'var(--text-dark)' : 'var(--border-subtle)',
                    backgroundColor: targetCount === p.count ? 'var(--text-dark)' : 'var(--cream)',
                    color: targetCount === p.count ? '#FFFFFF' : 'var(--text-dark)',
                    transition: 'all 0.15s ease',
                    textAlign: 'center'
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Carrier Fleet Size Capacity (1 to Any Trucks) */}
          {leadType !== 'SHIPPER' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <label style={{ fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                  Carrier Fleet Capacity (1 to Any Power Units)
                </label>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {fleetPreset === 'ALL' ? 'Any Fleet Size (1 to Any Trucks)' : `${fleetMin} to ${fleetMax > 500 ? 'Any' : fleetMax} Trucks`}
                </span>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {[
                  { key: 'ALL', label: '🚀 Any Fleet Size (1+ Trucks)' },
                  { key: 'SOLO', label: '👤 Solo Owner-Op (1 Truck)' },
                  { key: 'SMALL', label: '🚚 Small Fleet (2–10 Trucks)' },
                  { key: 'MID', label: '🏢 Mid Fleet (11–50 Trucks)' },
                  { key: 'LARGE', label: '🏭 Large Fleet (50+ Trucks)' },
                ].map(p => (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => applyFleetPreset(p.key)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 'var(--radius-pill)',
                      fontSize: '0.725rem',
                      fontWeight: fleetPreset === p.key ? 700 : 500,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: fleetPreset === p.key ? 'var(--sage-dark)' : 'var(--border-subtle)',
                      backgroundColor: fleetPreset === p.key ? 'var(--sage-light)' : '#FFFFFF',
                      color: fleetPreset === p.key ? 'var(--sage-dark)' : 'var(--text-dark)',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Regional Corridors & 50 States Selection */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                Target States ({selectedStates.length} Selected)
              </label>
              <button
                type="button"
                onClick={() => setSelectedStates([])}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: '0.725rem', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Clear Selection
              </button>
            </div>

            {/* Quick Regional Preset Chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
              {REGIONAL_PRESETS.map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => applyPreset(preset.states)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-pill)',
                    fontSize: '0.725rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--cream)',
                    color: 'var(--text-dark)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Search Filter for 50 States */}
            <div style={{ position: 'relative', marginBottom: '8px' }}>
              <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
              <input
                type="text"
                placeholder="Search state name or abbreviation (e.g. Florida, TX, Ohio)..."
                value={stateSearch}
                onChange={(e) => setStateSearch(e.target.value)}
                className="form-input"
                style={{ paddingLeft: '34px', height: '34px', fontSize: '0.775rem', borderRadius: 'var(--radius-sm)' }}
              />
            </div>

            {/* Scrollable 50 States Grid */}
            <div style={{
              maxHeight: '110px',
              overflowY: 'auto',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '8px',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '4px',
              backgroundColor: '#FAFAFA'
            }}>
              {filteredStates.map((st) => {
                const isSelected = selectedStates.includes(st.code);
                return (
                  <button
                    key={st.code}
                    type="button"
                    onClick={() => toggleState(st.code)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 'var(--radius-pill)',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: isSelected ? 'var(--sage)' : 'var(--border-subtle)',
                      backgroundColor: isSelected ? 'var(--sage-light)' : '#FFFFFF',
                      color: isSelected ? 'var(--sage-dark)' : 'var(--text-secondary)',
                      transition: 'all 0.1s ease'
                    }}
                  >
                    {st.code} &bull; {st.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Equipment Selection */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                Equipment &amp; Cargo Types ({selectedEquipment.length} Selected)
              </label>
              <button
                type="button"
                onClick={selectAllEquipment}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-dark)', fontSize: '0.725rem', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
              >
                Select All
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '6px' }}>
              {EQUIPMENT_OPTIONS.map((eq) => {
                const isChecked = selectedEquipment.includes(eq.id);
                return (
                  <label
                    key={eq.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isChecked ? 'var(--cream)' : '#FFFFFF',
                      border: '1px solid',
                      borderColor: isChecked ? 'var(--border-strong)' : 'var(--border-subtle)',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      color: 'var(--text-dark)'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleEquipment(eq.id)}
                      style={{ accentColor: 'var(--text-dark)' }}
                    />
                    <span>{eq.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Action Footer */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: '16px',
            borderTop: '1px solid var(--border-subtle)'
          }}>
            <div className="text-xs">
              Two-sided 10-Point verification active
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ minWidth: '180px' }}
              >
                <Play size={14} fill="currentColor" />
                <span>{submitting ? 'Generating Leads...' : `Launch ${targetCount} Leads Run`}</span>
              </button>
            </div>
          </div>

        </form>
      </div>
    </div>
  );
}
