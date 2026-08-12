/* ===== JUSTILINK API CLIENT ===== */
const API_BASE = 'http://127.0.0.1:8000/api';

const Auth = {
  getToken: () => localStorage.getItem('jl_token'),
  setToken: (t) => localStorage.setItem('jl_token', t),
  getUser:  () => JSON.parse(localStorage.getItem('jl_user') || 'null'),
  setUser:  (u) => localStorage.setItem('jl_user', JSON.stringify(u)),
  clear:    () => { localStorage.removeItem('jl_token'); localStorage.removeItem('jl_user'); },
  isLogged: () => !!localStorage.getItem('jl_token'),
};

async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) { Auth.clear(); window.location.href = 'index.html'; return; }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

const AuthAPI = {
  login: (email, mot_de_passe) => apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ email, mot_de_passe }) }),
  logout: () => apiFetch('/auth/logout', { method: 'POST' }),
  me: () => apiFetch('/auth/me'),
};

const DashboardAPI = { stats: () => apiFetch('/dashboard/stats') };

const AdmissibiliteAPI = {
  creer:  (data) => apiFetch('/admissibilite/', { method: 'POST', body: JSON.stringify(data) }),
  liste:  (params = '') => apiFetch(`/admissibilite/?${params}`),
  detail: (id) => apiFetch(`/admissibilite/${id}`),
  evaluer:(id) => apiFetch(`/admissibilite/${id}/evaluer`, { method: 'POST' }),
};

const DossiersAPI = {
  creer:     (data) => apiFetch('/dossiers/', { method: 'POST', body: JSON.stringify(data) }),
  liste:     (params = '') => apiFetch(`/dossiers/?${params}`),
  detail:    (id) => apiFetch(`/dossiers/${id}`),
  modifier:  (id, data) => apiFetch(`/dossiers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  cloturer:  (id) => apiFetch(`/dossiers/${id}`, { method: 'DELETE' }),
  historique:(id) => apiFetch(`/dossiers/${id}/historique`),
  stats:     () => apiFetch('/dossiers/stats'),
};

const DocumentsAPI = {
  liste:   (params = '') => apiFetch(`/documents/?${params}`),
  valider: (id) => apiFetch(`/documents/${id}/valider`, { method: 'PATCH' }),
  stats:   () => apiFetch('/documents/stats/resume'),
  deposer: async (dossierId, file, categorie, description) => {
    const token = Auth.getToken();
    const form = new FormData();
    form.append('fichier', file);
    form.append('dossier_id', dossierId);
    form.append('categorie', categorie);
    if (description) form.append('description', description);
    const res = await fetch(`${API_BASE}/documents/`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Erreur upload');
    return data;
  },
};

const TransmissionsAPI = {
  creer: (data) => apiFetch('/greffe/transmettre', { method: 'POST', body: JSON.stringify(data) }),
  liste: (params = '') => apiFetch(`/greffe/?${params}`),
};

const UtilisateursAPI = {
  liste: () => apiFetch('/utilisateurs/'),
  creer: (data) => apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
};

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('fr-CA', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('fr-CA', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatMoney(n) {
  return new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(n || 0);
}

function statutBadge(statut) {
  const map = {
    ouvert: ['badge-info', 'Ouvert'], en_cours: ['badge-warning', 'En cours'],
    en_attente: ['badge-secondary', 'En attente'], cloture: ['badge-success', 'Clôturé'],
    rejete: ['badge-danger', 'Rejeté'], admissible: ['badge-success', 'Admissible'],
    non_admissible: ['badge-danger', 'Non admissible'], revision_requise: ['badge-warning', 'Révision requise'],
    depose: ['badge-secondary', 'Déposé'], valide: ['badge-success', 'Validé'],
    transmis: ['badge-info', 'Transmis'], confirme: ['badge-success', 'Confirmé'], echec: ['badge-danger', 'Échec'],
  };
  const [cls, label] = map[statut] || ['badge-secondary', statut];
  return `<span class="badge ${cls}">${label}</span>`;
}

function prioriteBadge(p) {
  const map = { 1: ['badge-danger', '🔴 Urgent'], 2: ['badge-warning', '🟡 Normal'], 3: ['badge-secondary', '🟢 Faible'] };
  const [cls, label] = map[p] || ['badge-secondary', 'Normal'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function roleBadge(role) {
  const map = {
    admin: ['badge-purple', '👑 Admin'], greffier: ['badge-info', '⚖️ Greffier'],
    avocat: ['badge-warning', '👨‍⚖️ Avocat'], agent_aj: ['badge-success', '🏛️ Agent AJ'],
    citoyen: ['badge-secondary', '👤 Citoyen'],
  };
  const [cls, label] = map[role] || ['badge-secondary', role];
  return `<span class="badge ${cls}">${label}</span>`;
}

function requireAuth() {
  if (!Auth.isLogged()) window.location.href = 'index.html';
}

function initSidebar(activeItem) {
  const user = Auth.getUser();
  if (!user) return;
  const avatar = document.getElementById('sidebar-avatar');
  const name   = document.getElementById('sidebar-name');
  const role   = document.getElementById('sidebar-role');
  if (avatar) avatar.textContent = (user.prenom?.[0] || '') + (user.nom?.[0] || '');
  if (name)   name.textContent   = `${user.prenom} ${user.nom}`;
  if (role)   role.textContent   = user.role?.replace('_', ' ').toUpperCase();
  document.querySelectorAll('.nav-item').forEach(el => {
    if (el.dataset.page === activeItem) el.classList.add('active');
  });
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', () => { Auth.clear(); window.location.href = 'index.html'; });
  document.querySelectorAll('[data-role="admin"]').forEach(el => {
    if (user.role !== 'admin') el.style.display = 'none';
  });
}
