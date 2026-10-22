import React from 'react';
import { 
  Search, 
  Sparkles, 
  Bell, 
  CheckCircle2, 
  HelpCircle,
  Menu,
  Play,
  Pause,
  RotateCw,
  Zap,
  Activity
} from 'lucide-react';

export default function Header({ 
  activeTab, 
  onNewRunClick, 
  backendOnline, 
  searchQuery, 
  setSearchQuery,
  onSearchSubmit,
  onToggleMobileMenu,
  autopilotStatus,
  onToggleAutopilot,
  onTriggerAutopilot,
  isTriggeringAutopilot
}) {
  const getTabTitle = () => {
    switch (activeTab) {
      case 'dashboard': return 'Dashboard Overview';
      case 'leads': return 'Leads Database';
      case 'runs': return 'Pipeline History';
      case 'sheets': return 'Google Sheets Export';
      case 'settings': return 'ICP & Scoring Config';
      default: return 'Overview';
    }
  };

  const isPaused = autopilotStatus?.is_paused;
  const isExecuting = autopilotStatus?.is_executing || autopilotStatus?.status === 'EXECUTING';
  const nextSeconds = autopilotStatus?.next_run_in_seconds ?? 0;
  const currentCorridor = autopilotStatus?.current_corridor;

  return (
    <header className="top-header">
      {/* Title & Context */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {onToggleMobileMenu && (
          <button 
            onClick={onToggleMobileMenu}
            className="btn btn-secondary btn-icon"
            style={{ display: 'none' }} /* visible on mobile */
          >
            <Menu size={16} />
          </button>
        )}
        <div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-dark)' }}>
            {getTabTitle()}
          </h2>
        </div>
      </div>

      {/* Center Search Pill */}
      <div style={{ flex: '0 1 320px', position: 'relative' }}>
        <form onSubmit={(e) => { e.preventDefault(); if (onSearchSubmit) onSearchSubmit(); }}>
          <Search 
            size={15} 
            color="var(--text-muted)" 
            style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }} 
          />
          <input
            type="text"
            placeholder="Search leads, USDOT, states..."
            value={searchQuery || ''}
            onChange={(e) => setSearchQuery && setSearchQuery(e.target.value)}
            className="search-pill-input"
          />
        </form>
      </div>

      {/* Right Action Area */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        
        {/* Continuous Autopilot Live Pill */}
        {autopilotStatus && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '4px 10px',
            borderRadius: 'var(--radius-pill)',
            backgroundColor: isPaused ? 'var(--sand-light, #FAF4E8)' : isExecuting ? '#EFF6FF' : 'var(--sage-light)',
            border: `1px solid ${isPaused ? '#E8D5B5' : isExecuting ? '#BFDBFE' : 'var(--sage)'}`,
            fontSize: '0.75rem',
            color: 'var(--text-dark)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: isPaused ? '#D97706' : isExecuting ? '#2563EB' : '#16A34A',
                animation: (!isPaused && !isExecuting) ? 'pulse 2s infinite' : 'none'
              }} />
              <span style={{ fontWeight: 700, color: isPaused ? '#B45309' : isExecuting ? '#1D4ED8' : 'var(--sage-dark)' }}>
                {isExecuting ? 'Autopilot: Generating...' : isPaused ? 'Autopilot: Paused' : `Autopilot: Next in ${nextSeconds}s`}
              </span>
            </div>

            {/* Quick Pause / Resume Button */}
            <button
              onClick={onToggleAutopilot}
              title={isPaused ? "Resume Continuous Runner" : "Pause Continuous Runner"}
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: '2px 4px',
                display: 'flex',
                alignItems: 'center',
                color: isPaused ? '#B45309' : 'var(--text-secondary)',
                borderRadius: '4px'
              }}
            >
              {isPaused ? <Play size={13} fill="#B45309" /> : <Pause size={13} fill="currentColor" />}
            </button>

            {/* Quick Trigger Now Button */}
            <button
              onClick={onTriggerAutopilot}
              disabled={isTriggeringAutopilot || isExecuting}
              title="Run Next Corridor Cycle Immediately"
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border-subtle)',
                cursor: (isTriggeringAutopilot || isExecuting) ? 'not-allowed' : 'pointer',
                padding: '3px 7px',
                fontSize: '0.675rem',
                fontWeight: 600,
                borderRadius: '999px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                color: 'var(--text-dark)',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
              }}
            >
              <RotateCw size={11} className={isTriggeringAutopilot || isExecuting ? "spin-icon" : ""} />
              <span>Run Now</span>
            </button>
          </div>
        )}

        {/* Primary CTA Button */}
        <button 
          onClick={onNewRunClick}
          className="btn btn-primary"
          style={{ padding: '7px 14px', fontSize: '0.8rem' }}
        >
          <Sparkles size={14} />
          <span>New Run</span>
        </button>
      </div>
    </header>
  );
}
