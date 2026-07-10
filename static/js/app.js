/* ============================================================
   Resident Panel - app.js
   Premium SPA logic: navigation, data loading, toast, modals
   ============================================================ */

const API = 'http://localhost:5000/api';
let user = null;
let residentProfile = null;
let allNotices = [];
let allComplaints = [];
const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

/* ---------- HELPERS ---------- */
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

/* ---------- TOAST NOTIFICATIONS ---------- */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const icons = { success: 'check-circle', error: 'alert-circle', info: 'info' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<i data-feather="${icons[type] || 'info'}"></i><span>${message}</span>`;
  container.appendChild(toast);
  feather.replace();
  setTimeout(() => {
    toast.classList.add('fade-out');
    toast.addEventListener('animationend', () => toast.remove());
  }, 3500);
}

/* ---------- NAVIGATION ---------- */
function switchTab(targetId) {
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  const target = document.getElementById(targetId);
  if (target) target.classList.add('active');

  document.querySelectorAll('.nav-link[data-target]').forEach(l => l.classList.remove('active'));
  const activeLink = document.querySelector(`.nav-link[data-target="${targetId}"]`);
  if (activeLink) activeLink.classList.add('active');

  if (window.innerWidth <= 768) {
    document.getElementById('sidebar').classList.remove('open');
  }
  window.scrollTo(0, 0);
}

/* ---------- SIDEBAR / THEME ---------- */
function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');

  // Restore preferences
  if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-mode');
    document.getElementById('themeIcon').setAttribute('data-feather', 'sun');
    document.querySelector('#themeToggle .nav-text').textContent = 'Light Mode';
  }
  if (localStorage.getItem('sidebarCollapsed') === 'true' && window.innerWidth > 768) {
    sidebar.classList.add('collapsed');
    mainContent.classList.add('expanded');
    const icon = document.getElementById('collapseIcon');
    if (icon) icon.setAttribute('data-feather', 'chevron-right');
  }
  feather.replace();

  // Theme toggle
  document.getElementById('themeToggle').addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    document.getElementById('themeIcon').setAttribute('data-feather', isDark ? 'sun' : 'moon');
    document.querySelector('#themeToggle .nav-text').textContent = isDark ? 'Light Mode' : 'Dark Mode';
    feather.replace();
  });

  // Collapse toggle
  document.getElementById('collapseToggle').addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (window.innerWidth > 768) {
      mainContent.classList.toggle('expanded', isCollapsed);
    }
    localStorage.setItem('sidebarCollapsed', isCollapsed);
    document.getElementById('collapseIcon').setAttribute('data-feather', isCollapsed ? 'chevron-right' : 'chevron-left');
    feather.replace();
  });

  // Mobile toggle
  document.getElementById('menuToggle').addEventListener('click', () => {
    sidebar.classList.toggle('open');
  });

  // Nav links
  document.querySelectorAll('.nav-link[data-target]').forEach(link => {
    link.addEventListener('click', () => switchTab(link.getAttribute('data-target')));
  });

  // Logout
  document.getElementById('logoutBtn').addEventListener('click', () => {
    sessionStorage.removeItem('user');
    window.location.href = 'login.html';
  });
}

/* ---------- BOOT / AUTH ---------- */
function getUser() {
  const raw = sessionStorage.getItem('user');
  if (!raw) { window.location.href = 'login.html'; return null; }
  return JSON.parse(raw);
}

async function loadResidentProfile() {
  try {
    const r = await fetch(`${API}/resident/${user.id}`);
    if (r.ok) {
      residentProfile = await r.json();
      document.getElementById('flatNumberBadge').textContent = residentProfile.flat_number || 'TBD';
      document.getElementById('billingName').textContent = user.name;
      document.getElementById('billingFlat').textContent = residentProfile.flat_number || 'TBD';
      document.getElementById('billingMembers').textContent = residentProfile.family_members || '1';
    }
  } catch (e) { console.warn('Profile load failed', e); }
}

async function render() {
  user = getUser();
  if (!user) return;

  document.getElementById('avatarLetter').textContent = user.name[0].toUpperCase();
  document.getElementById('userName').textContent = user.name;
  document.getElementById('userRole').textContent = user.role;
  document.getElementById('greetingName').textContent = user.name.split(' ')[0];

  await loadResidentProfile();
  loadNotices();
  loadEvents();
  loadComplaints();
  loadMaintenance();
  loadFraudWarnings();
}

/* ============================================================
   NOTICES MODULE
   ============================================================ */
function getNoticeCategory(title) {
  const t = title.toLowerCase();
  if (/water|electricity|repair|maintenance|power/.test(t)) return 'Maintenance';
  if (/urgent|alert|warning|security|immediate/.test(t)) return 'Urgent';
  return 'General';
}

function renderNotices() {
  const search = document.getElementById('noticeSearch').value.toLowerCase();
  const filter = document.getElementById('noticeFilter').value;

  const filtered = allNotices.filter(n => {
    const matchesSearch = n.title.toLowerCase().includes(search) || n.content.toLowerCase().includes(search);
    const matchesFilter = filter === 'All' || n.category === filter;
    return matchesSearch && matchesFilter;
  });

  const grid = document.getElementById('fullNoticeGrid');

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1">
        <i data-feather="inbox"></i>
        <h3>No notices found</h3>
        <p>Try adjusting your search or category filter.</p>
      </div>`;
    feather.replace(); return;
  }

  let html = '';
  filtered.forEach((n, idx) => {
    const catClass = n.category === 'Urgent' ? 'category-urgent' : (n.category === 'Maintenance' ? 'category-maintenance' : '');
    const icon = n.category === 'Urgent' ? 'alert-circle' : (n.category === 'Maintenance' ? 'tool' : 'info');
    const dataAttr = `data-notice='${JSON.stringify(n).replace(/'/g, "&apos;")}'`;

    if (idx === 0 && !search && filter === 'All') {
      html += `
        <div class="highlight-card">
          <div class="highlight-content">
            <div class="highlight-badge"><i data-feather="star" style="width:12px;height:12px;"></i> Latest Announcement</div>
            <h3 class="highlight-title">${esc(n.title)}</h3>
            <p class="highlight-desc">${esc(n.content).substring(0, 160)}${n.content.length > 160 ? '...' : ''}</p>
            <div class="notice-card-date"><i data-feather="calendar" style="width:14px;height:14px;"></i> ${n.created_at} &middot; By ${esc(n.posted_by)}</div>
          </div>
          <div class="highlight-action">
            <button class="btn notice-read-btn" ${dataAttr}>Read Full Notice</button>
          </div>
        </div>`;
    } else {
      html += `
        <div class="notice-card">
          <div class="notice-card-header">
            <span class="category-badge ${catClass}"><i data-feather="${icon}" style="width:12px;height:12px;"></i> ${n.category}</span>
            <span class="notice-card-date">${n.created_at.split(' ')[0]}</span>
          </div>
          <h3 class="notice-card-title">${esc(n.title)}</h3>
          <p class="notice-card-desc">${esc(n.content)}</p>
          <div class="notice-card-footer">
            <span class="notice-card-date"><i data-feather="user" style="width:12px;height:12px;"></i> ${esc(n.posted_by)}</span>
            <button class="btn-read-more notice-read-btn" ${dataAttr}>Read <i data-feather="arrow-right" style="width:16px;"></i></button>
          </div>
        </div>`;
    }
  });
  grid.innerHTML = html;
  feather.replace();

  // Attach events using data-notice attribute (avoids inline JSON issues)
  grid.querySelectorAll('.notice-read-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const n = JSON.parse(btn.getAttribute('data-notice'));
      showNoticeModal(n);
    });
  });
}

function skeletonCards(count) {
  return Array(count).fill(0).map(() => `
    <div class="skel-card">
      <div class="skel-line skeleton w-50"></div>
      <div class="skel-line skeleton" style="margin-top:16px;"></div>
      <div class="skel-line skeleton"></div>
      <div class="skel-line skeleton w-75"></div>
    </div>`).join('');
}

async function loadNotices() {
  document.getElementById('fullNoticeGrid').innerHTML = skeletonCards(4);
  try {
    const r = await fetch(`${API}/notices`);
    let list = await r.json();
    list = list.map(n => ({ ...n, category: getNoticeCategory(n.title) }));
    allNotices = list;
    document.getElementById('noticeCount').textContent = list.length;

    // Dashboard preview
    document.getElementById('dashboardNoticeList').innerHTML = list.slice(0, 4).map(n => {
      const catClass = n.category === 'Urgent' ? 'category-urgent' : (n.category === 'Maintenance' ? 'category-maintenance' : '');
      return `
        <div class="list-item" style="cursor:pointer;" data-notice='${JSON.stringify(n).replace(/'/g, "&apos;")}'>
          <div class="list-icon-box" style="background:var(--info-bg); border-color:var(--border);">
            <i data-feather="bell" style="color:var(--primary)"></i>
          </div>
          <div class="list-content">
            <div class="list-title">${esc(n.title)} <span class="category-badge ${catClass}" style="margin-left:8px;font-size:10px;">${n.category}</span></div>
            <div class="list-meta"><i data-feather="clock" style="width:12px;height:12px;"></i> ${n.created_at}</div>
          </div>
        </div>`;
    }).join('');
    feather.replace();

    document.querySelectorAll('#dashboardNoticeList .list-item').forEach(item => {
      item.addEventListener('click', () => showNoticeModal(JSON.parse(item.getAttribute('data-notice'))));
    });

    renderNotices();
  } catch (e) {
    document.getElementById('fullNoticeGrid').innerHTML = `<div class="empty-state" style="grid-column:1/-1"><i data-feather="wifi-off"></i><h3>Connection Error</h3><p>Could not load notices. Check your connection.</p></div>`;
    feather.replace();
    showToast('Failed to load notices', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('noticeSearch').addEventListener('input', renderNotices);
  document.getElementById('noticeFilter').addEventListener('change', renderNotices);
});

function showNoticeModal(n) {
  const catClass = n.category === 'Urgent' ? 'category-urgent' : (n.category === 'Maintenance' ? 'category-maintenance' : '');
  const icon = n.category === 'Urgent' ? 'alert-circle' : (n.category === 'Maintenance' ? 'tool' : 'info');
  document.getElementById('modalNoticeBadge').className = `category-badge ${catClass}`;
  document.getElementById('modalNoticeBadge').innerHTML = `<i data-feather="${icon}" style="width:12px;height:12px;"></i> ${n.category}`;
  document.getElementById('modalNoticeTitle').textContent = n.title;
  document.getElementById('modalNoticeDate').textContent = n.created_at;
  document.getElementById('modalNoticeAuthor').textContent = n.posted_by;
  document.getElementById('modalNoticeContent').textContent = n.content;
  feather.replace();
  openModal('noticeModal');
}

/* ============================================================
   EVENTS
   ============================================================ */
async function loadEvents() {
  try {
    const r = await fetch(`${API}/events`);
    const list = await r.json();
    document.getElementById('eventCount').textContent = list.length;
    document.getElementById('eventList').innerHTML = list.slice(0, 3).map(e => {
      const d = new Date(e.event_date + 'T00:00:00');
      return `<div class="list-item">
        <div class="list-icon-box">
          <div class="day">${d.getDate()}</div>
          <div class="mon">${d.toLocaleString('en', { month: 'short' })}</div>
        </div>
        <div class="list-content">
          <div class="list-title">${esc(e.title)}</div>
          <div class="list-meta" style="color:var(--primary);"><i data-feather="map-pin" style="width:12px;height:12px;"></i> ${e.venue ? esc(e.venue) : 'TBA'}</div>
        </div>
      </div>`;
    }).join('') || `<div class="empty-state" style="border:none;padding:32px;"><i data-feather="calendar"></i><h3 style="font-size:15px;">No upcoming events</h3></div>`;
    feather.replace();
  } catch (e) { console.warn(e); }
}

/* ============================================================
   COMPLAINTS MODULE
   ============================================================ */
function getComplaintPriority(title, desc) {
  return /urgent|emergency|leak|fire|security/.test((title + ' ' + desc).toLowerCase()) ? 'High' : 'Normal';
}

function renderComplaints() {
  const search = document.getElementById('complaintSearch').value.toLowerCase();
  const filter = document.getElementById('complaintFilter').value;

  const filtered = allComplaints.filter(c => {
    const matchesSearch = c.title.toLowerCase().includes(search) || c.description.toLowerCase().includes(search) || String(c.id).includes(search);
    const matchesFilter = filter === 'All' || c.status === filter;
    return matchesSearch && matchesFilter;
  });

  const container = document.getElementById('fullComplaintList');

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <i data-feather="check-circle" style="color:var(--success);opacity:1;"></i>
        <h3>No tickets found</h3>
        <p>Try a different search or status filter.</p>
      </div>`;
    feather.replace(); return;
  }

  container.innerHTML = filtered.map(c => {
    const priority = getComplaintPriority(c.title, c.description);
    const prioClass = priority === 'High' ? 'priority-high' : '';
    const prioIcon = priority === 'High' ? 'alert-triangle' : 'flag';
    return `
      <div class="complaint-card">
        <div class="complaint-card-left">
          <div class="complaint-card-header">
            <span style="font-size:13px;font-weight:700;color:var(--primary);">#TKT-${c.id}</span>
            <span class="priority-badge ${prioClass}"><i data-feather="${prioIcon}" style="width:12px;height:12px;"></i> ${priority}</span>
          </div>
          <h3 class="complaint-card-title">${esc(c.title)}</h3>
          <p class="complaint-card-desc">${esc(c.description)}</p>
          <div class="complaint-card-meta">
            <span><i data-feather="calendar" style="width:14px;height:14px;"></i> ${c.created_at}</span>
            ${c.resolved_at ? `<span><i data-feather="check" style="width:14px;height:14px;"></i> Resolved: ${c.resolved_at}</span>` : ''}
          </div>
        </div>
        <div class="complaint-card-right">
          <span class="status-badge status-${c.status}">${c.status.replace('_', ' ')}</span>
        </div>
      </div>`;
  }).join('');
  feather.replace();
}

async function loadComplaints() {
  const container = document.getElementById('fullComplaintList');
  container.innerHTML = Array(3).fill(0).map(() => `
    <div class="skel-card" style="flex-direction:row;height:140px;">
      <div style="flex:1"><div class="skel-line skeleton w-50"></div><div class="skel-line skeleton" style="margin-top:16px;"></div><div class="skel-line skeleton w-75" style="margin-top:16px;"></div></div>
    </div>`).join('');
  try {
    const r = await fetch(`${API}/complaints?user_id=${user.id}`);
    const list = await r.json();
    allComplaints = list;

    const activeCount = list.filter(c => c.status !== 'resolved' && c.status !== 'discarded').length;
    document.getElementById('activeComplaintCount').textContent = activeCount;

    const dashList = document.getElementById('dashboardComplaintList');
    dashList.innerHTML = list.length ? list.slice(0, 3).map(c => `
      <div class="list-item" style="border-bottom:none;padding:12px;border-radius:12px;background:var(--bg);margin-bottom:8px;">
        <div class="list-content">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <div class="list-title" style="margin:0;font-size:14px;">${esc(c.title)}</div>
            <span class="status-badge status-${c.status}" style="font-size:9px;padding:2px 8px;">${c.status.replace('_', ' ')}</span>
          </div>
          <div class="list-meta" style="margin-top:4px;"><i data-feather="clock" style="width:10px;height:10px;"></i> ${c.created_at}</div>
        </div>
      </div>`).join('')
    : `<div style="color:var(--text-muted);font-size:13px;text-align:center;padding:16px;">No active tickets</div>`;

    feather.replace();
    renderComplaints();
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><i data-feather="wifi-off"></i><h3>Connection Error</h3><p>Could not load tickets.</p></div>`;
    feather.replace();
    showToast('Failed to load tickets', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('complaintSearch').addEventListener('input', renderComplaints);
  document.getElementById('complaintFilter').addEventListener('change', renderComplaints);

  document.getElementById('modalComplaintForm').addEventListener('submit', async e => {
    e.preventDefault();
    const title = document.getElementById('modalComplaintTitle').value.trim();
    const desc = document.getElementById('modalComplaintDesc').value.trim();
    if (!title || !desc) return;

    const btn = document.getElementById('modalComplaintSubmit');
    btn.disabled = true;
    btn.innerHTML = `<i data-feather="loader" style="width:18px;height:18px;animation:spin 1s linear infinite;"></i> Sending...`;
    feather.replace();

    try {
      const r = await fetch(`${API}/complaints`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, user_name: user.name, title, description: desc })
      });
      const d = await r.json();
      if (d.ok) {
        document.getElementById('modalComplaintForm').reset();
        closeModal('createComplaintModal');
        showToast('Ticket submitted successfully!', 'success');
        await loadComplaints();
      } else {
        showToast(d.error || 'Submission failed', 'error');
      }
    } catch {
      showToast('Server error. Please try again.', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Submit Ticket';
    }
  });
});

function openComplaintModal() {
  document.getElementById('modalComplaintForm').reset();
  openModal('createComplaintModal');
}

/* ============================================================
   MAINTENANCE MODULE
   ============================================================ */
async function payMaintenance(mid) {
  const btn = document.getElementById('btnPayNow');
  btn.disabled = true;
  btn.innerHTML = `<i data-feather="loader" style="animation:spin 1s linear infinite;"></i> Processing...`;
  feather.replace();
  try {
    await new Promise(res => setTimeout(res, 1500));
    const r = await fetch(`${API}/maintenance/${mid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'paid' })
    });
    const d = await r.json();
    if (d.ok) {
      showToast('Payment successful! 🎉', 'success');
      await loadMaintenance();
    } else {
      showToast('Payment failed. Try again.', 'error');
      btn.disabled = false;
      btn.innerHTML = `<i data-feather="credit-card"></i> Pay Now`;
      feather.replace();
    }
  } catch (e) {
    showToast('Server error during payment.', 'error');
    btn.disabled = false;
    btn.innerHTML = `<i data-feather="credit-card"></i> Retry`;
    feather.replace();
  }
}

async function loadMaintenance() {
  try {
    const [currentRes, historyRes] = await Promise.all([
      fetch(`${API}/maintenance/current?user_id=${user.id}`),
      fetch(`${API}/maintenance?user_id=${user.id}`)
    ]);
    const row = await currentRes.json();
    const all = await historyRes.json();

    const badge = document.getElementById('mtBadge');
    const amt = document.getElementById('mtAmount');
    const card = document.getElementById('maintenanceCard');
    const hero = document.getElementById('mtFullSummary');

    if (row && row.id) {
      const isPaid = row.status === 'paid';
      const monthName = months[parseInt(row.month) - 1];

      badge.textContent = isPaid ? 'Paid' : 'Pending';
      badge.className = `mt-status-badge mt-status-${row.status}`;
      amt.textContent = `₹${Number(row.amount).toLocaleString()}`;
      card.classList.add('mt-card-clickable');
      card.onclick = () => showInvoice(row);

      hero.innerHTML = `
        <div class="mt-summary-bg"></div>
        <div class="mt-summary-header">
          <span class="mt-summary-title">${monthName} ${row.year} Dues</span>
          <span class="mt-summary-status ${row.status}">${isPaid ? 'Paid' : 'Pending'}</span>
        </div>
        <div class="mt-summary-body">
          <div class="mt-summary-amount">₹${Number(row.amount).toLocaleString()}</div>
          ${isPaid
            ? `<div class="mt-summary-due" style="color:#6EE7B7;"><i data-feather="check-circle" style="width:14px;height:14px;margin-right:4px;"></i> Paid on ${row.paid_date}</div>`
            : `<div class="mt-summary-due"><i data-feather="alert-circle" style="width:14px;height:14px;margin-right:4px;"></i> Due by 5th ${monthName} ${row.year}</div>`}
        </div>
        <div class="mt-summary-actions">
          ${isPaid
            ? `<button class="btn btn-outline" style="background:rgba(255,255,255,0.1);color:white;border-color:rgba(255,255,255,0.3);" data-invoice='${JSON.stringify(row).replace(/'/g, "&apos;")}' id="viewReceiptBtn"><i data-feather="file-text"></i> View Receipt</button>`
            : `<button class="btn btn-success" id="btnPayNow" onclick="payMaintenance(${row.id})"><i data-feather="credit-card"></i> Pay Now</button>`
          }
        </div>`;
      feather.replace();
      const receiptBtn = document.getElementById('viewReceiptBtn');
      if (receiptBtn) receiptBtn.addEventListener('click', () => showInvoice(JSON.parse(receiptBtn.getAttribute('data-invoice'))));
    } else {
      badge.textContent = 'No Record';
      badge.className = 'mt-status-badge';
      badge.style.cssText = 'background:var(--bg);color:var(--text-muted);';
      amt.textContent = '₹0';
      card.classList.remove('mt-card-clickable');
      card.onclick = null;
      hero.innerHTML = `
        <div class="mt-summary-bg"></div>
        <div class="mt-summary-header"><span class="mt-summary-title">Current Dues</span></div>
        <div class="mt-summary-body"><div class="mt-summary-amount">₹0</div><div class="mt-summary-due">No maintenance record for this month.</div></div>`;
      feather.replace();
    }

    // Dashboard history list
    document.getElementById('mtHistoryList').innerHTML = all.length
      ? all.slice(0, 3).map(m => `
          <div class="mt-row">
            <span class="mt-row-month">${months[parseInt(m.month)-1].substring(0,3)} ${m.year}</span>
            <span class="mt-row-status mt-status-${m.status}">${m.status === 'paid' ? 'Paid' : 'Pending'}</span>
            <div class="mt-row-actions">
              <span class="mt-row-date">${m.paid_date || '-'}</span>
              <button class="btn-invoice invoice-btn" data-mt='${JSON.stringify(m).replace(/'/g,"&apos;")}'>
                <i data-feather="file-text" style="width:14px;height:14px;"></i>
              </button>
            </div>
          </div>`).join('')
      : `<div class="mt-row" style="color:var(--text-muted);justify-content:center;border:none;background:transparent;">No payment history found</div>`;

    // Full table
    const tableBody = document.getElementById('fullMtTableBody');
    tableBody.innerHTML = all.length
      ? all.map(m => {
          const invNo = `INV-${m.year}-${m.month}-${String(m.user_id).padStart(3,'0')}`;
          const statusClass = m.status === 'paid' ? 'mt-status-paid' : 'mt-status-pending';
          return `
            <tr>
              <td data-label="Invoice #"><strong>${invNo}</strong></td>
              <td data-label="Period">${months[parseInt(m.month)-1]} ${m.year}</td>
              <td data-label="Amount" style="font-weight:700;">₹${Number(m.amount).toLocaleString()}</td>
              <td data-label="Status"><span class="mt-status-badge ${statusClass}">${m.status === 'paid' ? 'Paid' : 'Pending'}</span></td>
              <td data-label="Paid On">${m.paid_date || '<span style="color:var(--text-muted)">-</span>'}</td>
              <td data-label="Action">
                <button class="btn-outline btn invoice-btn" style="height:32px;padding:0 12px;font-size:12px;" data-mt='${JSON.stringify(m).replace(/'/g,"&apos;")}'>View Receipt</button>
              </td>
            </tr>`;
        }).join('')
      : `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted);">No payment records found.</td></tr>`;

    feather.replace();

    // Attach invoice button events
    document.querySelectorAll('.invoice-btn').forEach(btn => {
      btn.addEventListener('click', () => showInvoice(JSON.parse(btn.getAttribute('data-mt'))));
    });

  } catch (e) {
    console.error(e);
    showToast('Failed to load maintenance data', 'error');
  }
}

function showInvoice(m) {
  const mos = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const invNo = `INV-${m.year}-${m.month}-${String(m.user_id).padStart(3,'0')}`;
  document.getElementById('invoiceBody').innerHTML = `
    <div class="invoice-row"><span class="invoice-label">Invoice No.</span><span class="invoice-value">${invNo}</span></div>
    <div class="invoice-row"><span class="invoice-label">Resident</span><span class="invoice-value">${esc(m.name || user.name)}</span></div>
    <div class="invoice-row"><span class="invoice-label">Flat Number</span><span class="invoice-value">${m.flat_number || (residentProfile ? residentProfile.flat_number : '-')}</span></div>
    <div class="invoice-row"><span class="invoice-label">Period</span><span class="invoice-value">${mos[parseInt(m.month)-1]} ${m.year}</span></div>
    <div class="invoice-row"><span class="invoice-label">Status</span><span class="invoice-value" style="color:${m.status==='paid'?'var(--success)':'var(--danger)'};">${m.status==='paid'?'Paid':'Pending'}</span></div>
    ${m.paid_date ? `<div class="invoice-row"><span class="invoice-label">Paid On</span><span class="invoice-value">${m.paid_date}</span></div>` : ''}
    <div class="invoice-total"><span>Total Amount</span><span>₹${Number(m.amount).toLocaleString()}</span></div>
    <div style="text-align:center;margin-top:16px;font-size:13px;color:var(--text-muted);font-weight:500;">
      ${m.status==='paid'?'<span style="color:var(--success)">✓ This invoice has been paid. Thank you!</span>':'⚠️ Payment pending. Please pay before the due date.'}
    </div>`;
  openModal('invoiceModal');
}

/* ============================================================
   FRAUD WARNINGS
   ============================================================ */
async function loadFraudWarnings() {
  try {
    const r = await fetch(`${API}/complaints?warnings=1&user_id=${user.id}`);
    const warnings = await r.json();
    const el = document.getElementById('fraudWarning');
    if (warnings.length) {
      document.getElementById('fraudTitle').textContent = warnings[0].title;
      el.classList.add('show');
    } else {
      el.classList.remove('show');
    }
  } catch (e) { /* silent */ }
}

/* ============================================================
   MODALS
   ============================================================ */
function openModal(id) {
  const overlay = document.getElementById(id);
  overlay.classList.add('show');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('show');
}

document.addEventListener('DOMContentLoaded', () => {
  // Close on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) overlay.classList.remove('show');
    });
  });

  // Print invoice
  document.getElementById('invoicePrint').addEventListener('click', () => window.print());

  // Init sidebar + theme
  initSidebar();

  // Boot render
  render();
});
