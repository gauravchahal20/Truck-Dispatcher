import React, { useState, useEffect } from 'react';
import './styles/App.css';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DashboardStats from './components/DashboardStats';
import LeadsTable from './components/LeadsTable';
import RunsManager from './components/RunsManager';
import SheetsManager from './components/SheetsManager';
import ConfigSettings from './components/ConfigSettings';
import SearchPlaybook from './components/SearchPlaybook';
import LeadDetailModal from './components/LeadDetailModal';
import NewRunModal from './components/NewRunModal';
import ReadyToContact from './components/ReadyToContact';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState(null);
  const [isNewRunModalOpen, setIsNewRunModalOpen] = useState(false);
  const [filterRunId, setFilterRunId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [autopilotStatus, setAutopilotStatus] = useState(null);
  const [isTriggeringAutopilot, setIsTriggeringAutopilot] = useState(false);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, autoRes] = await Promise.allSettled([
        api.getStats(),
        api.getAutopilotStatus()
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value);
        setBackendOnline(true);
      }
      if (autoRes.status === 'fulfilled') {
        setAutopilotStatus(autoRes.value);
      }
    } catch (err) {
      console.warn('Backend currently unreachable:', err.message);
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 2500);
    return () => clearInterval(interval);
  }, []);

  const handleToggleAutopilot = async () => {
    if (!autopilotStatus) return;
    try {
      if (autopilotStatus.is_paused) {
        const updated = await api.resumeAutopilot();
        setAutopilotStatus(updated);
      } else {
        const updated = await api.pauseAutopilot();
        setAutopilotStatus(updated);
      }
    } catch (err) {
      console.error('Failed to toggle autopilot:', err);
    }
  };

  const handleTriggerAutopilot = async () => {
    setIsTriggeringAutopilot(true);
    try {
      const updated = await api.triggerAutopilot();
      setAutopilotStatus(updated);
      await fetchDashboardData();
    } catch (err) {
      console.error('Failed to trigger autopilot cycle:', err);
    } finally {
      setTimeout(() => setIsTriggeringAutopilot(false), 2000);
    }
  };

  const handleChangeAutopilotInterval = async (seconds) => {
    try {
      const updated = await api.setAutopilotInterval(seconds);
      setAutopilotStatus(updated);
    } catch (err) {
      console.error('Failed to update autopilot interval:', err);
    }
  };

  const handleSelectRunLeads = (runId) => {
    setFilterRunId(runId);
    setActiveTab('leads');
  };

  const handleViewLead = (lead) => {
    setSelectedCompanyId(lead.id);
  };

  const handleLeadStatusUpdated = () => {
    fetchDashboardData();
  };

  const handleRunStarted = (run) => {
    fetchDashboardData();
    setActiveTab('runs');
  };

  const handleHeaderSearchSubmit = () => {
    if (searchQuery.trim()) {
      setActiveTab('leads');
    }
  };

  return (
    <div className="app-layout">
      {/* Soft-Minimal Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeRun={stats?.active_run}
        backendOnline={backendOnline}
      />

      {/* Main Content Area */}
      <div className="main-content-wrapper">
        <Header
          activeTab={activeTab}
          onNewRunClick={() => setIsNewRunModalOpen(true)}
          backendOnline={backendOnline}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSearchSubmit={handleHeaderSearchSubmit}
          autopilotStatus={autopilotStatus}
          onToggleAutopilot={handleToggleAutopilot}
          onTriggerAutopilot={handleTriggerAutopilot}
          isTriggeringAutopilot={isTriggeringAutopilot}
        />

        <main className="content-container">
          {activeTab === 'dashboard' && (
            <DashboardStats
              stats={stats}
              activeRun={stats?.active_run}
              onViewLead={handleViewLead}
              onNewRunClick={() => setIsNewRunModalOpen(true)}
              onViewAllLeads={() => {
                setFilterRunId(null);
                setActiveTab('leads');
              }}
              autopilotStatus={autopilotStatus}
              onToggleAutopilot={handleToggleAutopilot}
              onTriggerAutopilot={handleTriggerAutopilot}
              onChangeAutopilotInterval={handleChangeAutopilotInterval}
              isTriggeringAutopilot={isTriggeringAutopilot}
            />
          )}

          {activeTab === 'contact' && (
            <ReadyToContact
              onViewLead={handleViewLead}
            />
          )}

          {activeTab === 'leads' && (
            <LeadsTable
              initialRunId={filterRunId}
              onViewLead={handleViewLead}
              globalSearch={searchQuery}
            />
          )}

          {activeTab === 'runs' && (
            <RunsManager
              onSelectRunLeads={handleSelectRunLeads}
              onNewRunClick={() => setIsNewRunModalOpen(true)}
            />
          )}

          {activeTab === 'playbook' && (
            <SearchPlaybook />
          )}

          {activeTab === 'sheets' && (
            <SheetsManager />
          )}

          {activeTab === 'settings' && (
            <ConfigSettings />
          )}
        </main>

        {/* Minimal Footer */}
        <footer style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '16px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.75rem',
          color: 'var(--text-muted)'
        }}>
          <div>TRUCKLEAD AUTOPILOT &bull; Autonomous Dispatch & Lead Verification Engine</div>
          <div>41+ Discovery Methods &bull; 10-Point Grounded Audit &bull; Google Sheets Sync</div>
        </footer>
      </div>

      {/* Modal: Lead Detail Inspection */}
      {selectedCompanyId && (
        <LeadDetailModal
          companyId={selectedCompanyId}
          onClose={() => setSelectedCompanyId(null)}
          onStatusUpdated={handleLeadStatusUpdated}
        />
      )}

      {/* Modal: New Pipeline Run Creator */}
      {isNewRunModalOpen && (
        <NewRunModal
          onClose={() => setIsNewRunModalOpen(false)}
          onRunStarted={handleRunStarted}
        />
      )}
    </div>
  );
}
