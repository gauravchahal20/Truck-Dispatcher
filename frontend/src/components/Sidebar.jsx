import React from 'react';
import { 
  LayoutDashboard, 
  Users, 
  Zap, 
  FileSpreadsheet, 
  Sliders, 
  Truck,
  BookOpen,
  Sparkles,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';

export default function Sidebar({ 
  activeTab, 
  setActiveTab, 
  activeRun,
  backendOnline
}) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'leads', label: 'Leads Database', icon: Users },
    { id: 'runs', label: 'Pipeline Runs', icon: Zap, badge: activeRun ? 'Live' : null },
    { id: 'playbook', label: 'SOP Playbook', icon: BookOpen, badge: '41+ Methods' },
    { id: 'sheets', label: 'Google Sheets', icon: FileSpreadsheet },
    { id: 'settings', label: 'ICP Config', icon: Sliders },
  ];

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '0 8px', marginBottom: '32px' }}>
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: '10px',
          backgroundColor: 'var(--text-dark)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#FFFFFF'
        }}>
          <Truck size={18} strokeWidth={2} />
        </div>
        <div>
          <div style={{ fontSize: '0.925rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-dark)', lineHeight: 1.1 }}>
            TRUCKLEAD
          </div>
          <div style={{ fontSize: '0.675rem', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
            AUTOPILOT
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
        <div style={{ fontSize: '0.675rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '0 12px', marginBottom: '8px' }}>
          Menu
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} strokeWidth={1.8} />
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  backgroundColor: item.id === 'playbook' ? 'var(--warm-cream)' : 'var(--sage)',
                  color: item.id === 'playbook' ? 'var(--terracotta-dark)' : 'var(--sage-dark)',
                  padding: '1px 6px',
                  borderRadius: '999px'
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Engine Status Bottom Card */}
      <div style={{
        marginTop: 'auto',
        padding: '14px',
        backgroundColor: '#FFFFFF',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: backendOnline ? 'var(--sage)' : '#F5C2C0',
              display: 'inline-block'
            }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)' }}>
              {backendOnline ? 'Engine Active' : 'Connecting...'}
            </span>
          </div>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)' }}>
            v1.0
          </span>
        </div>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.35 }}>
          Autonomous 10-Point verification & 41+ Lead Methods active.
        </p>
      </div>
    </aside>
  );
}
