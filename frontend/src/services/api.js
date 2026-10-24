const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const res = await fetch(url, config);
    if (!res.ok) {
      let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorData = await res.json();
        errorMsg = errorData.detail || errorMsg;
      } catch (e) {
        // Fallback to status text
      }
      throw new Error(errorMsg);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Request Error [${endpoint}]:`, err);
    throw err;
  }
}

export const api = {
  // Stats & Dashboard
  getStats: () => request('/api/stats'),
  getHealth: () => request('/health'),

  // Pipeline Runs
  getRuns: (limit = 20, offset = 0) => request(`/api/runs?limit=${limit}&offset=${offset}`),
  getRun: (runId) => request(`/api/runs/${runId}`),
  createRun: (runData) => request('/api/runs', {
    method: 'POST',
    body: JSON.stringify(runData),
  }),
  cancelRun: (runId) => request(`/api/runs/${runId}/cancel`, { method: 'POST' }),

  // Companies / Leads
  getCompanies: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.run_id) params.append('run_id', filters.run_id);
    if (filters.lead_status && filters.lead_status !== 'ALL') params.append('lead_status', filters.lead_status);
    if (filters.state) params.append('state', filters.state);
    if (filters.priority) params.append('priority', filters.priority);
    if (filters.min_score) params.append('min_score', filters.min_score);
    if (filters.search) params.append('search', filters.search);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    
    return request(`/api/companies?${params.toString()}`);
  },

  getCompany: (companyId) => request(`/api/companies/${companyId}`),
  updateCompanyStatus: (companyId, newStatus, reason) => request(`/api/companies/${companyId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ new_status: newStatus, reason }),
  }),

  // System Configuration
  getConfig: () => request('/api/config'),
  updateConfig: (yamlContent) => request('/api/config', {
    method: 'PUT',
    body: JSON.stringify({ yaml_content: yamlContent }),
  }),

  // Google Sheets & Export Sync
  getSheetsStatus: () => request('/api/sheets/status'),
  syncSheets: (runId = null) => request('/api/sheets/sync', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId }),
  }),

  // Continuous Autopilot Engine
  getAutopilotStatus: () => request('/api/autopilot/status'),
  startAutopilot: () => request('/api/autopilot/start', { method: 'POST' }),
  pauseAutopilot: () => request('/api/autopilot/pause', { method: 'POST' }),
  resumeAutopilot: () => request('/api/autopilot/resume', { method: 'POST' }),
  triggerAutopilot: () => request('/api/autopilot/trigger', { method: 'POST' }),
  setAutopilotInterval: (intervalSeconds) => request('/api/autopilot/interval', {
    method: 'POST',
    body: JSON.stringify({ interval_seconds: intervalSeconds }),
  }),

  // Callable & Mailable Leads (Workstream E)
  getCallableMailableLeads: (filterMode = 'all', limit = 100) =>
    request(`/api/leads/callable-mailable?filter_mode=${filterMode}&limit=${limit}`),
  logLeadOutcome: (data) =>
    request('/api/leads/outcome', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getDraftEmail: (companyId) =>
    request(`/api/leads/companies/${companyId}/draft-email`),
  verifyAuthorityManual: (companyId, data) =>
    request(`/api/leads/${companyId}/verify-authority-manual`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
