// ── PROFILE PAGE ──────────────────────────────────────────────────────────────

(function () {
  // Skills tag input — convert comma-separated input into visual tags preview
  const skillsInput = document.querySelector('input[name="skills"]');
  const skillsPreview = document.getElementById("skills-preview");

  function renderSkillTags(value) {
    if (!skillsPreview) return;
    skillsPreview.innerHTML = "";
    value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((skill) => {
        const tag = document.createElement("span");
        tag.className = "tag tag-soft";
        tag.textContent = skill;
        skillsPreview.appendChild(tag);
      });
  }

  if (skillsInput) {
    renderSkillTags(skillsInput.value);
    skillsInput.addEventListener("input", () => renderSkillTags(skillsInput.value));
  }

  // Confirm before leaving with unsaved changes
  const profileForm = document.querySelector('form[action="/profile/update"]');
  if (profileForm) {
    let dirty = false;
    profileForm.querySelectorAll("input, textarea, select").forEach((el) => {
      el.addEventListener("input", () => (dirty = true));
    });
    profileForm.addEventListener("submit", () => (dirty = false));
    window.addEventListener("beforeunload", (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  }

  // Character counter for bio textarea
  const bioTextarea = document.querySelector('textarea[name="bio"]');
  if (bioTextarea) {
    const counter = document.createElement("small");
    counter.style.color = "var(--text-muted)";
    counter.style.marginTop = "4px";
    counter.style.display = "block";
    bioTextarea.parentNode.appendChild(counter);
    const update = () =>
      (counter.textContent = `${bioTextarea.value.length} / 300 caracteres`);
    update();
    bioTextarea.addEventListener("input", update);
  }
})();