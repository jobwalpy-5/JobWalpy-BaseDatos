(() => {
  const KEY = 'jobwalpy-theme';
  const root = document.documentElement;
  const readTheme = () => {
    try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; }
    catch (_) { return root.dataset.theme === 'dark' ? 'dark' : 'light'; }
  };
  const applyTheme = (theme) => {
    const safeTheme = theme === 'dark' ? 'dark' : 'light';
    root.dataset.theme = safeTheme;
    try { localStorage.setItem(KEY, safeTheme); } catch (_) { /* almacenamiento opcional */ }
    const button = document.getElementById('theme-toggle');
    if (button) {
      const dark = safeTheme === 'dark';
      button.innerHTML = dark ? '<span aria-hidden="true">☀️</span><span>Modo claro</span>' : '<span aria-hidden="true">🌙</span><span>Modo oscuro</span>';
      button.setAttribute('aria-label', dark ? 'Activar modo claro' : 'Activar modo oscuro');
      button.setAttribute('aria-pressed', String(dark));
    }
  };
  const mountButton = () => {
    if (document.getElementById('theme-toggle')) { applyTheme(readTheme()); return; }
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'theme-toggle';
    button.className = 'theme-toggle';
    button.addEventListener('click', () => applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark'));
    const navInner = document.querySelector('.nav-inner');
    const navToggle = document.getElementById('nav-toggle');
    if (navInner) {
      if (navToggle) navInner.insertBefore(button, navToggle);
      else navInner.appendChild(button);
    } else {
      button.classList.add('theme-toggle--floating');
      document.body.appendChild(button);
    }
    applyTheme(readTheme());
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountButton, { once: true });
  else mountButton();
})();