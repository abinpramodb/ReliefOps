/* ═══════════════════════════════════════════
   ReliefOps — auth.js
   Shared auth utilities used by all pages
═══════════════════════════════════════════ */

const Auth = {
  getRole()  { return localStorage.getItem('ro_role')  || ''; },
  getEmail() { return localStorage.getItem('ro_email') || ''; },
  getName()  { return localStorage.getItem('ro_name')  || ''; },
  getId()    { return localStorage.getItem('ro_id')    || ''; },
  isAdmin()      { return this.getRole() === 'admin'; },
  isVolunteer()  { return this.getRole() === 'volunteer'; },
  isDonor()      { return this.getRole() === 'donor'; },
  isLoggedIn()   { return !!this.getRole(); },

  save(data) {
    localStorage.setItem('ro_role',  data.role);
    localStorage.setItem('ro_email', data.email);
    localStorage.setItem('ro_name',  data.name  || data.email);
    localStorage.setItem('ro_id',    data.id    || '');
  },

  clear() {
    ['ro_role','ro_email','ro_name','ro_id'].forEach(k => localStorage.removeItem(k));
  },

  logout() {
    this.clear();
    window.location.href = 'login.html';
  },

  // Redirect to login if not logged in
  require(allowedRoles) {
    if (!this.isLoggedIn()) {
      window.location.href = 'login.html';
      return false;
    }
    if (allowedRoles && !allowedRoles.includes(this.getRole())) {
      window.location.href = 'dashboard.html';
      return false;
    }
    return true;
  },

  // Inject sidebar user info
  renderUser() {
    const name   = this.getName();
    const role   = this.getRole();
    const initials = name ? name.substring(0,2).toUpperCase() : '??';
    const roleLabel = { admin: 'Administrator', volunteer: 'Volunteer', donor: 'Donor' }[role] || role;

    const avEl   = document.getElementById('sb-av');
    const nameEl = document.getElementById('sb-name');
    const roleEl = document.getElementById('sb-role');
    if (avEl)   avEl.textContent   = initials;
    if (nameEl) nameEl.textContent = name;
    if (roleEl) roleEl.textContent = roleLabel;
  }
};

// Toast helper (global)
function showToast(msg, type = 'success') {
  const t   = document.getElementById('toast');
  const ico = document.getElementById('toast-ico');
  const txt = document.getElementById('toast-txt');
  if (!t) return;
  if (ico) ico.style.color = type === 'success' ? '#4ade80' : type === 'warn' ? '#fbbf24' : '#f87171';
  if (txt) txt.textContent = msg;
  t.classList.remove('show');
  void t.offsetWidth;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// API helper
async function api(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Role': Auth.getRole(), 'X-User-Id': Auth.getId() }
  };
  if (body) opts.body = JSON.stringify(body);
  const res  = await fetch('/api' + path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}
// ─────────────────────────────────────────────
// Convenience helpers used by new pages
// ─────────────────────────────────────────────
function getUser() {
  const role = Auth.getRole();
  if (!role) return null;
  return {
    id:           Auth.getId(),
    name:         Auth.getName(),
    email:        Auth.getEmail(),
    role:         role,
    phone:        localStorage.getItem('ro_phone')   || '',
    organization: localStorage.getItem('ro_org')     || '',
    joined_date:  localStorage.getItem('ro_joined')  || ''
  };
}

function logout() {
  Auth.clear();
  ['ro_phone','ro_org','ro_joined'].forEach(k => localStorage.removeItem(k));
  window.location.href = 'login.html';
}