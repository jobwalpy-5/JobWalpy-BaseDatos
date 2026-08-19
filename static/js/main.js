document.addEventListener("DOMContentLoaded", function () {

  // ── NAV TOGGLE MÓVIL ─────────────────────────────────────────────────────
  const navToggle = document.getElementById("nav-toggle");
  const navLinks  = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
    document.addEventListener("click", function (e) {
      if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
        navLinks.classList.remove("open");
      }
    });
  }

  // ── FILTROS — DRAWER ──────────────────────────────────────────────────────
  const filterToggle  = document.getElementById("filter-toggle");
  const filterSidebar = document.getElementById("filters-sidebar");
  const filterClose   = document.getElementById("filter-close");
  const filterOverlay = document.getElementById("filters-overlay");

  function openFilters() {
    filterSidebar.classList.add("open");
    filterOverlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeFilters() {
    filterSidebar.classList.remove("open");
    filterOverlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  if (filterToggle)  filterToggle.addEventListener("click", openFilters);
  if (filterClose)   filterClose.addEventListener("click", closeFilters);
  if (filterOverlay) filterOverlay.addEventListener("click", closeFilters);

  // Cerrar con Escape
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeFilters();
  });

  // Enviar filtros al cambiar cualquier select (UX mejorada)
  const filterForm = document.getElementById("filter-form");
  if (filterForm) {
    filterForm.querySelectorAll("select").forEach(function (select) {
      select.addEventListener("change", function () {
        filterForm.submit();
      });
    });
  }

});