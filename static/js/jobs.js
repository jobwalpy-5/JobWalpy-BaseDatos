// ── JOBS PAGE ─────────────────────────────────────────────────────────────────

// Auto-submit filter form on select change
(function () {
  const categorySelect = document.querySelector('select[name="category"]');
  const typeSelect = document.querySelector('select[name="type"]');

  [categorySelect, typeSelect].forEach((el) => {
    if (el) {
      el.addEventListener("change", () => {
        el.closest("form")?.submit();
      });
    }
  });

  // Highlight active filters
  const urlParams = new URLSearchParams(window.location.search);
  const activeFilters = ["search", "category", "type"].filter(
    (k) => urlParams.get(k)
  );
  if (activeFilters.length > 0) {
    const clearBtn = document.querySelector('a[href="/jobs"]');
    if (clearBtn) {
      clearBtn.textContent = `Limpiar (${activeFilters.length})`;
      clearBtn.style.color = "var(--accent)";
      clearBtn.style.borderColor = "var(--accent)";
    }
  }

  // Animate job cards on load
  const cards = document.querySelectorAll(".job-card");
  cards.forEach((card, i) => {
    card.style.opacity = "0";
    card.style.transform = "translateY(16px)";
    card.style.transition = `opacity .3s ease ${i * 50}ms, transform .3s ease ${i * 50}ms`;
    requestAnimationFrame(() => {
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    });
  });
})();
