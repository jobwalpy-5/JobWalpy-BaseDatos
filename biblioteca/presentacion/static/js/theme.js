// Tema claro/oscuro: lee y guarda la preferencia en localStorage (la misma clave que usan las plantillas).
(function () {
  var KEY = "jobwalpy-theme";
  function aplicar(t) { document.documentElement.dataset.theme = t; }
  try { aplicar(localStorage.getItem(KEY) || "light"); } catch (e) { aplicar("light"); }
  window.jobwalpyToggleTheme = function () {
    var nuevo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    aplicar(nuevo);
    try { localStorage.setItem(KEY, nuevo); } catch (e) {}
  };
})();
