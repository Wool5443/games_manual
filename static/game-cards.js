(function () {
  const dialog = document.getElementById("card-modal");
  const content = document.getElementById("card-modal-content");
  const toolbar = document.getElementById("card-modal-toolbar-actions");
  if (!dialog || !content || !toolbar) return;

  const closeButton = dialog.querySelector("[data-card-modal-close]");
  let activeCard = null;

  const openCard = function (card) {
    if (dialog.open) return;
    activeCard = card;
    const clone = card.cloneNode(true);
    clone.classList.remove("card-expandable");
    ["data-card-expandable", "tabindex", "role", "aria-label"].forEach(function (attribute) {
      clone.removeAttribute(attribute);
    });
    clone.querySelector("h2").id = "card-modal-title";

    const actions = clone.querySelector(".card-overlay-actions");
    toolbar.replaceChildren();
    if (actions) {
      toolbar.append(...actions.children);
      actions.remove();
    }
    content.replaceChildren(clone);
    dialog.showModal();
    document.body.classList.add("modal-open");
    closeButton.focus();
  };

  document.querySelectorAll("[data-card-expandable]").forEach(function (card) {
    card.addEventListener("click", function (event) {
      if (!event.target.closest("a, button")) openCard(card);
    });
    card.addEventListener("keydown", function (event) {
      if (event.target === card && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        openCard(card);
      }
    });
  });

  closeButton.addEventListener("click", function () {
    dialog.close();
  });

  dialog.addEventListener("click", function (event) {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) {
      dialog.close();
    }
  });

  // Native Escape dismissal also reaches this cleanup path.
  dialog.addEventListener("close", function () {
    document.body.classList.remove("modal-open");
    content.replaceChildren();
    toolbar.replaceChildren();
    if (activeCard) activeCard.focus();
    activeCard = null;
  });
})();
