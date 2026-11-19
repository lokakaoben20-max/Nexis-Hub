// Aperçu de la Mini App sur un téléphone, sans Telegram ni backend.
//
// Cloudflare (Workers Builds) publie ce Worker pour chaque branche : la
// page est celle de mini_app/static telle qu'elle est sur la branche, mais
// Telegram est simulé et toutes les données sont FICTIVES (aucun appel au
// backend, aucun compte réel, aucun argent). Un bandeau le rappelle.
//
// Choix dans l'adresse : ?vue=prestataire (défaut) | inscription | client,
// ?langue=fr | ln | en. Le thème suit celui du téléphone.

const SERVICES = {
  service_plomberie: ["Plomberie", "Plomberie", "Plumbing"],
  service_electricite: ["Électricité", "Kokotisa mwinda", "Electrical"],
  service_climatisation: ["Climatisation", "Climatisation", "Air conditioning"],
  service_informatique: ["Informatique", "Informatique", "IT"],
  service_graphisme: ["Graphisme", "Graphisme", "Graphic design"],
  service_coiffure: ["Coiffure", "Kosala nsuki", "Hairdressing"],
  service_nettoyage: ["Nettoyage", "Kopetola", "Cleaning"],
  service_jardinage: ["Jardinage", "Jardin", "Gardening"],
  service_autre: ["Autre service", "Mosala mosusu", "Other service"],
};
const COMMUNES = ["Gombe", "Kinshasa", "Limete", "Ngaliema", "Lemba", "Kalamu", "Barumbu", "Lingwala"];
const LANGS = ["fr", "ln", "en"];

function daysAgo(days) {
  return new Date(Date.now() - days * 86400000).toISOString();
}

function demoProvider(services = ["service_nettoyage", "service_jardinage"], communes = ["Limete", "Gombe"], status = "available") {
  return {
    full_name: "Patrick Kabongo", phone_number: "+243812345678", services, communes, status,
    badge: "verified", total_missions: 24, success_rate: 96, rating: 4.8,
    is_verified: true, is_suspended: false, has_documents: true,
  };
}

function demoMissions() {
  return [
    { id: 42, service: "service_nettoyage", commune: "Limete", status: "confirmed", payment_status: "paid_escrow", currency: "CDF", net_provider: 25000, client_name: "Grâce N.", description: "Nettoyage complet d'un appartement de 3 pièces, cuisine comprise.", urgent: true, release_after: null },
    { id: 43, service: "service_plomberie", commune: "Gombe", status: "in_progress", payment_status: "paid_escrow", currency: "USD", net_provider: 40, client_name: "Jean M.", description: "Fuite sous l'évier de la cuisine." },
    { id: 44, service: "service_electricite", commune: "Ngaliema", status: "awaiting_confirmation", payment_status: "paid_escrow", currency: "USD", net_provider: 12.5, client_name: "Aline", description: "Remplacer deux prises du salon." },
    { id: 30, service: "service_jardinage", commune: "Gombe", status: "completed", payment_status: "released", currency: "CDF", net_provider: 30000, client_name: "Marc" },
  ];
}

function profile(view, lang) {
  const base = {
    telegram_id: 42, language: lang,
    client: null, provider: demoProvider(),
    client_missions: [], provider_missions: demoMissions(),
    service_requests: [{ service_name: "Pose de carrelage", status: "pending", created_at: daysAgo(3), admin_note: null }],
    service_additions: [
      { id: 5, service_key: "service_electricite", status: "pending", created_at: daysAgo(1), admin_note: null, photo_count: 3 },
    ],
    wallet: { wallet_balance_usd: 152.5, wallet_balance_cdf: 120000, secured_usd: 52.5, secured_cdf: 25000 },
    wallet_history: [
      { id: 9, kind: "release", mission_id: 30, currency: "CDF", amount: "30000.00", created_at: daysAgo(1) },
      { id: 8, kind: "payout_hold", mission_id: null, currency: "USD", amount: "-20.00", created_at: daysAgo(3) },
      { id: 7, kind: "auto_release", mission_id: 28, currency: "USD", amount: "45.00", created_at: daysAgo(5) },
      { id: 6, kind: "split", mission_id: 25, currency: "USD", amount: "12.50", created_at: daysAgo(7) },
    ],
    max_services: 3,
    provider_excluded_services: ["service_autre"],
    available_services: Object.fromEntries(Object.entries(SERVICES).map(([key, names]) => [key, names[0]])),
    service_names: Object.fromEntries(Object.entries(SERVICES).map(([key, [fr, ln, en]]) => [key, { fr, ln, en }])),
    available_communes: COMMUNES,
  };
  if (view === "inscription") return { ...base, provider: null, provider_missions: null, service_additions: [], service_requests: [] };
  if (view === "client") {
    return {
      ...base, provider: null, provider_missions: null, service_additions: [], service_requests: [],
      client: { first_name: "Grâce", phone_number: "+243811111111" },
      client_missions: [{ id: 42, service: "service_nettoyage", commune: "Limete", status: "confirmed", payment_status: "paid_escrow", currency: "CDF", provider_name: "Patrick K." }],
    };
  }
  return base;
}

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});

// Réponses plausibles aux actions : rien n'est enregistré, la page affiche
// simplement ce qu'elle afficherait après une vraie réponse du backend.
async function action(path, request) {
  const body = request.headers.get("Content-Type")?.includes("json") ? await request.json().catch(() => ({})) : {};
  const mission = (id, changes) => ({ ...demoMissions().find((item) => item.id === Number(id)), ...changes });
  let match;
  if ((match = path.match(/missions\/(\d+)\/arrived$/))) return json({ status: "ok", mission: mission(match[1], {}), presence: { confirmed: false } });
  if ((match = path.match(/missions\/(\d+)\/presence-code$/))) {
    if (body.code !== "1234") return json({ detail: { code: "wrong_presence_code", attempts_left: 2 } }, 400);
    return json({ status: "ok", mission: mission(match[1], { status: "in_progress" }) });
  }
  if ((match = path.match(/missions\/(\d+)\/finish$/))) return json({ status: "ok", mission: mission(match[1], { status: "awaiting_confirmation" }) });
  if (path.endsWith("/status")) return json({ status: "ok", provider: demoProvider(undefined, undefined, body.status) });
  if (path.endsWith("/services")) return json({ status: "ok", provider: demoProvider(body.services) });
  if (path.endsWith("/communes")) return json({ status: "ok", provider: demoProvider(undefined, body.communes) });
  if (path.endsWith("/photos")) return json({ status: "ok", photo_id: crypto.randomUUID().replaceAll("-", "") });
  if (path.endsWith("/service-additions")) {
    return json({ status: "ok", provider: demoProvider(), service_additions: [
      { id: 6, service_key: body.service_key, status: "pending", created_at: new Date().toISOString(), admin_note: null },
    ] });
  }
  if (/service-additions\/\d+\/cancel$/.test(path)) return json({ status: "ok", provider: demoProvider(), service_additions: [] });
  if (path.endsWith("/service-requests")) {
    return json({ status: "ok", service_requests: [{ service_name: body.service_name, status: "pending", created_at: new Date().toISOString() }] });
  }
  if (path.endsWith("/register")) return json({ status: "ok", provider: { ...demoProvider(body.services, body.communes, "pending_verification"), full_name: body.full_name, is_verified: false, badge: "pending" } });
  return json({ detail: { code: "refused" } }, 400);
}

const BANNER_TEXT = {
  fr: "Aperçu · données fictives, rien n'est enregistré",
  ln: "Bomoni · makambo ya solo te, eloko ebombami te",
  en: "Preview · sample data, nothing is saved",
};

function telegramStub(lang) {
  // Juste ce que la page utilise de Telegram.WebApp.
  return `window.Telegram = { WebApp: {
    initData: "apercu",
    initDataUnsafe: { user: { id: 42, first_name: "Patrick", language_code: ${JSON.stringify(lang)} } },
    colorScheme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    ready() {}, expand() {}, onEvent() {}, setHeaderColor() {}, setBackgroundColor() {},
    showConfirm(text, done) { done(window.confirm(text)); },
    BackButton: { show() {}, hide() {}, onClick() {}, offClick() {} },
    HapticFeedback: { notificationOccurred() {}, impactOccurred() {}, selectionChanged() {} },
  } };`;
}

async function page(env, url) {
  const lang = LANGS.includes(url.searchParams.get("langue")) ? url.searchParams.get("langue") : "fr";
  const asset = await env.ASSETS.fetch(new URL("/index.html", url));
  const rewritten = new HTMLRewriter()
    .on('script[src^="https://telegram.org/"]', {
      element(element) {
        element.replace(`<script>${telegramStub(lang)}</script>`, { html: true });
      },
    })
    .on("body", {
      element(element) {
        element.prepend(
          `<div style="position:sticky;top:0;z-index:50;background:#021937;color:#fff;font:600 12px/1.4 system-ui,sans-serif;text-align:center;padding:6px 12px">${BANNER_TEXT[lang]}</div>`,
          { html: true },
        );
      },
    })
    .transform(asset);
  return new Response(rewritten.body, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/index.html") return page(env, url);
    if (url.pathname.startsWith("/static/")) {
      const response = await env.ASSETS.fetch(new URL(url.pathname.slice("/static".length), url));
      const headers = new Headers(response.headers);
      headers.set("Cache-Control", "no-store");
      return new Response(response.body, { status: response.status, headers });
    }
    if (url.pathname.startsWith("/api/profile/")) {
      const referer = new URL(request.headers.get("Referer") || url.href);
      const lang = LANGS.includes(referer.searchParams.get("langue")) ? referer.searchParams.get("langue") : "fr";
      return json(profile(referer.searchParams.get("vue") || "prestataire", lang));
    }
    if (url.pathname.startsWith("/api/") && request.method === "POST") return action(url.pathname, request);
    return new Response("Introuvable", { status: 404 });
  },
};
