const README_URL = "https://github.com/MaazDhalech/BearGrubb#readme";
const ICON_URL = "/public/beargrub-icon.png";

function setFavicon() {
  const selectors = [
    'link[rel="icon"]',
    'link[rel="shortcut icon"]',
    'link[rel="apple-touch-icon"]',
  ];

  selectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((link) => link.remove());
  });

  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/png";
  favicon.href = ICON_URL;
  document.head.appendChild(favicon);

  const appleTouchIcon = document.createElement("link");
  appleTouchIcon.rel = "apple-touch-icon";
  appleTouchIcon.href = ICON_URL;
  document.head.appendChild(appleTouchIcon);
}

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

function disableThemeControl() {
  const buttons = Array.from(document.querySelectorAll("button"));
  const themeButton = buttons.find((button) => button.textContent.trim() === "Toggle theme");

  if (!themeButton) {
    return;
  }

  themeButton.style.display = "none";
  document.documentElement.classList.remove("light");
  document.documentElement.classList.add("dark");
}

setFavicon();
wireReadmeButton();
centerEmptyState();
disableThemeControl();

new MutationObserver(() => {
  setFavicon();
  wireReadmeButton();
  centerEmptyState();
  disableThemeControl();
}).observe(document.body, {
  childList: true,
  subtree: true,
});

window.addEventListener("load", () => {
  setFavicon();
  wireReadmeButton();
  centerEmptyState();
  disableThemeControl();
});
