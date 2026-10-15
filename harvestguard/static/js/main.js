// Simple English / Kiswahili toggle: any element with data-sw swaps its text.
const btn = document.getElementById("lang");
let sw = localStorage.getItem("hg-lang") === "sw";

function applyLang() {
  document.querySelectorAll("[data-sw]").forEach(el => {
    if (!el.dataset.en) el.dataset.en = el.textContent;
    el.textContent = sw ? el.dataset.sw : el.dataset.en;
  });
  document.documentElement.lang = sw ? "sw" : "en";
  btn.textContent = sw ? "SW | EN" : "EN | SW";
}

btn.addEventListener("click", () => {
  sw = !sw;
  localStorage.setItem("hg-lang", sw ? "sw" : "en");
  applyLang();
});
applyLang();
