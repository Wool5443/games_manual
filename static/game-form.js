(function () {
  const dropzone = document.getElementById("file-dropzone");
  const input = document.getElementById("game-files");
  const button = document.getElementById("file-picker-button");
  const fileList = document.getElementById("selected-files");
  if (!dropzone || !input || !button || !fileList) return;

  let selectedFiles = [];

  const syncInputFiles = () => {
    const transfer = new DataTransfer();
    selectedFiles.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
  };

  const renderFiles = () => {
    fileList.innerHTML = "";

    if (!selectedFiles.length) {
      const item = document.createElement("li");
      item.textContent = "Файлы не выбраны";
      fileList.appendChild(item);
      return;
    }

    selectedFiles.forEach((file, index) => {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = file.name;

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "selected-file-remove";
      removeButton.textContent = "Убрать";
      removeButton.addEventListener("click", function () {
        selectedFiles = selectedFiles.filter((_, fileIndex) => fileIndex !== index);
        syncInputFiles();
        renderFiles();
      });

      item.appendChild(name);
      item.appendChild(removeButton);
      fileList.appendChild(item);
    });
  };

  const mergeFiles = (incomingFiles) => {
    selectedFiles = selectedFiles.concat(Array.from(incomingFiles || []));
    syncInputFiles();
    renderFiles();
  };

  button.addEventListener("click", function () {
    input.click();
  });

  input.addEventListener("change", function () {
    mergeFiles(input.files);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", function (event) {
    const files = event.dataTransfer ? event.dataTransfer.files : null;
    if (!files || !files.length) return;
    mergeFiles(files);
  });
})();
