(function () {
  document.querySelectorAll(".admin-import-form").forEach(function (form) {
    const input = form.querySelector(".admin-import-picker input[type='file']");
    if (!input) return;

    input.addEventListener("change", function () {
      if (input.files && input.files[0]) {
        form.requestSubmit();
      }
    });
  });
})();
