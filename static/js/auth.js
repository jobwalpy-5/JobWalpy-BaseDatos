// Auto-submit filters on change
document.querySelectorAll('#filter-form select').forEach(sel => {
  sel.addEventListener('change', () => document.getElementById('filter-form').submit());
});

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.style.display = 'none';
  });
});

// Auto-hide alerts
document.querySelectorAll('.alert').forEach(alert => {
  setTimeout(() => alert.style.opacity = '0', 4000);
  setTimeout(() => alert.remove(), 4500);
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    document.querySelector(a.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth' });
  });
});

// ── Toggle login / registro ──
const container = document.getElementById('container');

document.getElementById('btn-sign-up')?.addEventListener('click', () => {
  container.classList.add('toggle');
});

document.getElementById('btn-sign-in')?.addEventListener('click', () => {
  container.classList.remove('toggle');
});

document.getElementById('btn-sign-up-mobile')?.addEventListener('click', () => {
  container.classList.add('toggle');
});

document.getElementById('btn-sign-in-mobile')?.addEventListener('click', () => {
  container.classList.remove('toggle');
});