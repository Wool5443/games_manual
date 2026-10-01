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
})();
