const README_URL = "https://github.com/MaazDhalech/BearGrubb#readme";

function wireReadmeButton() {
  const buttons = Array.from(document.querySelectorAll("button"));
  const readmeButton = buttons.find((button) => button.textContent.trim() === "Readme");

  if (!readmeButton || readmeButton.dataset.beargrubReadme === "wired") {
    return;
  }

  readmeButton.dataset.beargrubReadme = "wired";
  readmeButton.setAttribute("title", "Open the BearGrub README on GitHub");
  readmeButton.addEventListener(
    "click",
    (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      window.open(README_URL, "_blank", "noopener,noreferrer");
    },
    true
  );
}

function centerEmptyState() {
  const logo = document.querySelector('img[src*="beargrub-wordmark.svg"]');
  const composer = document.querySelector("textarea");

  if (!logo || !composer) {
    return;
  }

  window.scrollTo({ top: 600, left: 0, behavior: "instant" });
}

wireReadmeButton();
centerEmptyState();

new MutationObserver(() => {
  wireReadmeButton();
  centerEmptyState();
}).observe(document.body, {
  childList: true,
  subtree: true,
});

window.addEventListener("load", () => {
  wireReadmeButton();
  centerEmptyState();
});
