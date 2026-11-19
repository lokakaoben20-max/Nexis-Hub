// Page d'accueil de l'aperçu : l'adresse à épingler sur l'écran d'accueil
// du téléphone ou de l'ordinateur. Elle s'ouvre comme une application
// (manifest + icône) et mène à chaque vue de la Mini App. Elle suit la
// branche publiée : chaque modification envoyée y apparaît d'elle-même.

const VUES = [
  ["prestataire", "Prestataire", "Accueil, missions, services, profil. Bascule Prestataire / Client en haut."],
  ["attente", "Prestataire en vérification", "Ouvre l'espace client tant que l'équipe vérifie le profil."],
  ["client", "Client seulement", "Portefeuille et demandes d'un client qui n'est pas prestataire."],
  ["inscription", "Devenir prestataire", "Le formulaire d'inscription."],
];
const LANGUES = [["fr", "Français"], ["ln", "Lingala"], ["en", "English"]];

const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function accueil(version) {
  const lignes = VUES.map(([vue, titre, note]) => `
      <a class="item" href="/?vue=${vue}" data-vue="${vue}">
        <span class="txt"><b>${esc(titre)}</b><small>${esc(note)}</small></span>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>
      </a>`).join("");
  const langues = LANGUES.map(([code, nom]) => `<button type="button" data-langue="${code}" aria-pressed="${code === "fr"}">${nom}</button>`).join("");
  return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="noindex">
<title>Nexis Aperçu</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" href="/icone-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Nexis Aperçu">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="#F6F8FB" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0B1424" media="(prefers-color-scheme: dark)">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Unbounded:wght@500;600&display=swap">
<style>
:root { --bg:#F6F8FB; --surface:#FFFFFF; --ink:#021937; --muted:#5B667A; --line:#E3E8F0; --brand:#0350E6; --soft:#E8F0FE; color-scheme: light; }
@media (prefers-color-scheme: dark) { :root { --bg:#0B1424; --surface:#121E33; --ink:#EAF0FA; --muted:#9AA7BD; --line:#22314B; --brand:#5B8CFF; --soft:#1A2B4D; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 Inter, system-ui, -apple-system, sans-serif; }
.wrap { max-width:560px; margin:0 auto; display:grid; gap:20px;
  padding: calc(20px + env(safe-area-inset-top, 0px)) max(16px, env(safe-area-inset-right, 0px)) calc(32px + env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px)); }
.head { display:flex; align-items:center; gap:12px; }
.head img { width:48px; height:48px; border-radius:13px; }
h1 { margin:0; font:600 22px/1.2 Unbounded, Inter, sans-serif; }
.head small { display:block; color:var(--muted); font-size:13px; }
h2 { margin:0 4px; font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
section { display:grid; gap:8px; }
.list { background:var(--surface); border-radius:18px; box-shadow:0 0 0 1px var(--line); overflow:hidden; }
.item { display:flex; align-items:center; gap:12px; padding:14px; color:inherit; text-decoration:none; }
.item + .item { border-top:1px solid var(--line); }
.item:active { background:var(--soft); }
.item:focus-visible, .seg button:focus-visible { outline:2px solid var(--brand); outline-offset:2px; }
.txt { flex:1; min-width:0; display:grid; gap:2px; }
.txt b { font-weight:600; }
.txt small { color:var(--muted); font-size:12.5px; }
.item svg { color:var(--muted); flex:none; }
.seg { display:grid; grid-template-columns:repeat(3,1fr); background:var(--surface); box-shadow:0 0 0 1px var(--line); border-radius:999px; padding:4px; }
.seg button { border:0; background:none; color:var(--muted); font:600 13px Inter, sans-serif; padding:8px 0; border-radius:999px; cursor:pointer; }
.seg button[aria-pressed="true"] { background:var(--ink); color:var(--bg); }
.note { margin:0; background:var(--soft); border-radius:14px; padding:12px 14px; font-size:13px; color:var(--muted); }
.note b { color:var(--ink); }
.foot { margin:0 4px; font-size:12px; color:var(--muted); }
</style>
</head>
<body>
<main class="wrap">
  <div class="head">
    <img src="/icone-192.png" alt="">
    <div><h1>Nexis Aperçu</h1><small>Données fictives, rien n'est enregistré.</small></div>
  </div>
  <section>
    <h2>Langue</h2>
    <div class="seg" role="group" aria-label="Langue">${langues}</div>
  </section>
  <section>
    <h2>Mini App Telegram</h2>
    <div class="list">${lignes}</div>
  </section>
  <section>
    <h2>Application mobile</h2>
    <p class="note"><b>Pas encore construite.</b> Ses écrans apparaîtront ici, à cette même adresse, dès que les premiers seront codés.</p>
  </section>
  <p class="note">Pour l'épingler : dans Safari, Partager puis « Sur l'écran d'accueil ». Sur Android, menu ⋮ puis « Ajouter à l'écran d'accueil ». Sur ordinateur (Chrome ou Edge), l'icône d'installation dans la barre d'adresse.</p>
  <p class="foot">Version publiée : ${esc(version)}</p>
</main>
<script>
(function () {
  var key = "nexis.apercu.langue", langue = "fr";
  try { langue = localStorage.getItem(key) || "fr"; } catch (e) {}
  function apply() {
    document.querySelectorAll("[data-langue]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.langue === langue)); });
    document.querySelectorAll("[data-vue]").forEach(function (a) { a.href = "/?vue=" + a.dataset.vue + (langue === "fr" ? "" : "&langue=" + langue); });
  }
  document.querySelectorAll("[data-langue]").forEach(function (b) {
    b.addEventListener("click", function () { langue = b.dataset.langue; try { localStorage.setItem(key, langue); } catch (e) {} apply(); });
  });
  apply();
})();
</script>
</body>
</html>`;
}

export function manifest() {
  return {
    name: "Nexis Aperçu",
    short_name: "Nexis",
    lang: "fr",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#F6F8FB",
    theme_color: "#0350E6",
    icons: [
      { src: "/icone-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icone-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
