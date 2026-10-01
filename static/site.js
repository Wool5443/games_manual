(function () {
  const menuToggle = document.getElementById("menu-toggle");
  const menu = document.getElementById("header-menu");
  if (menuToggle && menu) {
    menuToggle.addEventListener("click", function () {
      const open = menu.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(open));
    });

    menu.querySelectorAll("a, button").forEach(function (element) {
      element.addEventListener("click", function () {
        if (window.innerWidth <= 860) {
          menu.classList.remove("is-open");
          menuToggle.setAttribute("aria-expanded", "false");
        }
      });
    });
  }

  document.querySelectorAll("[data-dropdown-single], [data-dropdown-multiselect]").forEach(function (dropdown) {
    const trigger = dropdown.querySelector("[data-dropdown-trigger]");
    const panel = dropdown.querySelector("[data-dropdown-panel]");
    const label = dropdown.querySelector("[data-dropdown-label]");
    const multiple = dropdown.hasAttribute("data-dropdown-multiselect");
    const optionSelector = multiple ? "[data-dropdown-option]" : "[data-dropdown-single-option]";
    const options = Array.from(dropdown.querySelectorAll(optionSelector));
    if (!trigger || !panel || !label || !options.length) return;

    const previous = dropdown.previousElementSibling;
    const hiddenInput = previous && previous.type === "hidden" ? previous : null;
    const placeholder = label.dataset.placeholder || (multiple ? "Выберите типы" : label.textContent.trim());

    const setOpen = function (open) {
      dropdown.classList.toggle("is-open", open);
      trigger.setAttribute("aria-expanded", String(open));
      panel.hidden = !open;
    };

    const updateLabel = function () {
      const selected = options.filter(function (option) { return option.checked; });
      if (hiddenInput) {
        hiddenInput.value = selected.length ? selected[0].value : "";
      }
      label.textContent = selected.length
        ? selected.map(function (option) {
            return option.closest(".dropdown-option").querySelector(".dropdown-option-label").textContent;
          }).join(", ")
        : placeholder || "Выберите значение";
    };

    trigger.addEventListener("click", function () {
      setOpen(!dropdown.classList.contains("is-open"));
    });

    options.forEach(function (option) {
      option.addEventListener("change", function () {
        updateLabel();
        if (!multiple) setOpen(false);
      });
    });

    document.addEventListener("click", function (event) {
      if (!dropdown.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });

    updateLabel();
  });
})();
