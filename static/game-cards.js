(function () {
  const modal = document.getElementById("card-modal");
  const modalContent = document.getElementById("card-modal-content");
  const modalToolbarActions = document.getElementById("card-modal-toolbar-actions");
  const modalDialog = modal ? modal.querySelector(".card-modal-dialog") : null;
  const cards = Array.from(document.querySelectorAll("[data-card-expandable]"));
  if (!modal || !modalContent || !modalToolbarActions || !modalDialog || !cards.length) return;

  let activeCard = null;
  let activeGhost = null;
  let isAnimating = false;
  let cleanupTimer = null;

  const cloneCard = function (card) {
    const clone = card.cloneNode(true);
    clone.classList.remove("card-expandable");
    ["data-card-expandable", "tabindex", "role", "aria-label"].forEach(function (attribute) {
      clone.removeAttribute(attribute);
    });
    return clone;
  };

  const cleanupGhost = function () {
    if (activeGhost) {
      activeGhost.remove();
      activeGhost = null;
    }
  };

  const clearTimers = function () {
    if (cleanupTimer) {
      window.clearTimeout(cleanupTimer);
      cleanupTimer = null;
    }
  };

  const closeModal = function () {
    if (isAnimating) return;
    clearTimers();
    modal.classList.remove("is-open", "is-preparing", "is-animating", "is-finalizing");
    document.body.classList.remove("modal-open");
    cleanupGhost();
    if (activeCard) {
      activeCard.classList.remove("is-expanding");
    }
    window.setTimeout(function () {
      modal.hidden = true;
      modalContent.innerHTML = "";
      modalToolbarActions.innerHTML = "";
    }, 220);
    if (activeCard) {
      activeCard.focus();
      activeCard = null;
    }
  };

  const openModal = function (card) {
    if (isAnimating || !modal.hidden) return;
    activeCard = card;
    activeCard.classList.add("is-expanding");
    modalContent.innerHTML = "";
    const clone = cloneCard(card);
    clone.id = "card-modal-title";
    const cloneActions = clone.querySelector(".card-overlay-actions");
    if (cloneActions) {
      modalToolbarActions.innerHTML = cloneActions.innerHTML;
      cloneActions.remove();
    } else {
      modalToolbarActions.innerHTML = "";
    }
    modalContent.appendChild(clone);

    const sourceRect = card.getBoundingClientRect();
    modal.hidden = false;
    document.body.classList.add("modal-open");
    modal.classList.add("is-preparing", "is-animating");

    const ghost = cloneCard(card);
    ghost.classList.add("card-modal-ghost");
    ghost.style.top = sourceRect.top + "px";
    ghost.style.left = sourceRect.left + "px";
    ghost.style.width = sourceRect.width + "px";
    ghost.style.height = sourceRect.height + "px";
    ghost.style.borderRadius = getComputedStyle(card).borderRadius;
    document.body.appendChild(ghost);
    activeGhost = ghost;
    isAnimating = true;

    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        const targetRect = clone.getBoundingClientRect();
        ghost.style.top = targetRect.top + "px";
        ghost.style.left = targetRect.left + "px";
        ghost.style.width = targetRect.width + "px";
        ghost.style.height = targetRect.height + "px";
        ghost.style.borderRadius = getComputedStyle(clone).borderRadius;
        ghost.classList.add("is-expanding");
      });
    });

    cleanupTimer = window.setTimeout(function () {
      modal.classList.remove("is-preparing", "is-animating");
      modal.classList.add("is-open", "is-finalizing");
      cleanupGhost();
      if (activeCard) {
        activeCard.classList.remove("is-expanding");
      }
      isAnimating = false;
      cleanupTimer = null;
      requestAnimationFrame(function () {
        modal.classList.remove("is-finalizing");
      });
    }, 340);
  };

  cards.forEach(function (card) {
    card.addEventListener("click", function (event) {
      if (event.target.closest("a")) return;
      openModal(card);
    });
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openModal(card);
      }
    });
  });

  modal.querySelectorAll("[data-card-modal-close]").forEach(function (element) {
    element.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
})();
