"use strict";

// Mini App Nexis Hub, côté prestataire (mosali). La page n'invente aucun
// chiffre : profils, missions, soldes et refus viennent du backend, seule
// source de vérité, à travers mini_app/app.py. Tout texte affiché passe par
// textContent (jamais innerHTML avec des données) et par NEXIS_TEXTS.

const tg = window.Telegram?.WebApp;
const telegramUser = tg?.initDataUnsafe?.user || null;

const SERVICE_ICONS = {
  service_plomberie: ["f-plomberie", "#0350E6"],
  service_electricite: ["f-electricite", "#C98200"],
  service_climatisation: ["f-clim", "#0A84D6"],
  service_informatique: ["f-info", "#021937"],
  service_graphisme: ["f-graph", "#494C95"],
  service_coiffure: ["f-coiffure", "#C2416B"],
  service_nettoyage: ["f-nettoyage", "#1E8A4C"],
  service_jardinage: ["f-jardin", "#4F8A10"],
  service_autre: ["f-autre", "#5B667A"],
};
const ACTIVE_STATUSES = ["pending", "quoted", "confirmed", "in_progress", "awaiting_confirmation"];
const DONE_STATUSES = ["completed", "cancelled", "disputed"];
const LOCALES = { fr: "fr-FR", ln: "fr-FR", en: "en-US" };

const CURRENCY_KEY = "nexis.devise";

const state = {
  data: null,
  lang: "fr",
  tab: "home",
  sub: null, // sous-écran : { name: "mission" | "propose" | "register", missionId }
  missionFilter: "active",
  // Espace affiché quand la personne est aussi prestataire : "provider" ou
  // "client" (un seul compte, un seul portefeuille, deux rôles).
  space: null,
  currency: savedCurrency(),
  walletHidden: false,
  walletInfo: false,
};

function savedCurrency() {
  try {
    return window.localStorage.getItem(CURRENCY_KEY) === "USD" ? "USD" : "CDF";
  } catch (error) {
    return "CDF";
  }
}

function setCurrency(currency) {
  state.currency = currency;
  try {
    window.localStorage.setItem(CURRENCY_KEY, currency);
  } catch (error) {
    // Le choix reste actif pour cette ouverture si le stockage est indisponible.
  }
}

const SPACE_KEY = "nexis.espace";

function savedSpace() {
  try {
    const value = window.localStorage.getItem(SPACE_KEY);
    return value === "client" || value === "provider" ? value : null;
  } catch (error) {
    return null; // stockage bloqué : on retombe sur le choix par défaut
  }
}

function setSpace(space) {
  state.space = space;
  state.tab = "home";
  state.sub = null;
  try {
    window.localStorage.setItem(SPACE_KEY, space);
  } catch (error) {
    // stockage bloqué : le choix vaut pour cette ouverture seulement
  }
  render();
  window.scrollTo(0, 0);
}

// Prestataire vérifié : son espace d'abord. Prestataire encore en
// vérification mais déjà client : l'espace client, pour ne pas le bloquer
// sur l'attente. Le dernier choix de la personne prime.
function defaultSpace() {
  const me = provider();
  if (!me) return "client";
  return savedSpace() || (me.is_verified || !state.data?.client ? "provider" : "client");
}

function inClientSpace() {
  return !provider() || state.space === "client";
}

// Bascule « Prestataire | Client », en haut de l'accueil des deux espaces.
function spaceSwitch() {
  if (!provider()) return null;
  return el("div", { class: "seg role", style: "--n:2", role: "group", "aria-label": t("space_switch") },
    ["provider", "client"].map((space) => el("button", {
      type: "button",
      "aria-pressed": state.space === space ? "true" : "false",
      text: t(`space_${space}`),
      onclick: () => { if (state.space !== space) setSpace(space); },
    })));
}

// --- Langue et textes --------------------------------------------------------

function pickLanguage(profileLanguage) {
  if (NEXIS_TEXTS[profileLanguage]) return profileLanguage;
  const telegramLanguage = (telegramUser?.language_code || "").slice(0, 2);
  return NEXIS_TEXTS[telegramLanguage] ? telegramLanguage : "fr";
}

function lookup(texts, key) {
  return key.split(".").reduce((node, part) => (node == null ? undefined : node[part]), texts);
}

function t(key, vars = {}) {
  let text = lookup(NEXIS_TEXTS[state.lang], key);
  if (typeof text !== "string") text = lookup(NEXIS_TEXTS.fr, key);
  if (typeof text !== "string") return key;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match));
}

function serviceName(key) {
  const names = state.data?.service_names?.[key];
  return names?.[state.lang] || names?.fr || state.data?.available_services?.[key] || key;
}

function missionRef(id) {
  return `NXH-${String(id).padStart(4, "0")}`;
}

// Montants : jamais calculés ici, seulement mis en forme. USD avec deux
// décimales, francs congolais sans décimales.
function formatWalletMoney(value, currency) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const usd = currency === "USD";
  const locale = LOCALES[state.lang] || "fr-FR";
  const parts = new Intl.NumberFormat(locale, {
    minimumFractionDigits: usd ? 2 : 0,
    maximumFractionDigits: usd ? 2 : 0,
  }).formatToParts(value);
  const number = parts.map((part) => part.type === "group" ? "\u202F" : part.value).join("");
  return `${number} ${usd ? "USD" : "FC"}`;
}

function formatMoney(value, currency) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const isUsd = currency === "USD";
  const digits = isUsd ? 2 : 0;
  const number = new Intl.NumberFormat(LOCALES[state.lang] || "fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
  return `${number} ${isUsd ? "USD" : "FC"}`;
}

function formatDate(iso) {
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALES[state.lang] || "fr-FR", { day: "numeric", month: "long" }).format(date);
}

// --- Construction du DOM -----------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";

function icon(id) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#${id}`);
  svg.appendChild(use);
  return svg;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style") node.setAttribute("style", value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node && typeof value !== "string") node[key] = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function serviceIcon(key, size) {
  const [symbol, color] = SERVICE_ICONS[key] || SERVICE_ICONS.service_autre;
  return el("span", { class: "svc", style: `--c:${color}${size ? `;width:${size}px;height:${size}px` : ""}` }, icon(symbol));
}

function button(label, onclick, { cls = "btn", iconId = null, type = "button" } = {}) {
  return el("button", { class: cls, type, onclick }, iconId ? icon(iconId) : null, el("span", { text: label }));
}

let toastTimer = null;
function toast(message, isError = false) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.className = isError ? "toast error" : "toast";
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 4500);
  try {
    tg?.HapticFeedback?.notificationOccurred(isError ? "error" : "success");
  } catch (error) {
    // Ancienne version de Telegram : pas de vibration.
  }
}

// --- Échanges avec le serveur de la Mini App --------------------------------

class ApiError extends Error {
  constructor(code, attemptsLeft) {
    super(code || "generic");
    this.code = code;
    this.attemptsLeft = attemptsLeft;
  }
}

async function api(path, body) {
  let response;
  try {
    response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "X-Telegram-Init-Data": tg?.initData || "",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    throw new ApiError("backend_unavailable");
  }
  let result = null;
  try {
    result = await response.json();
  } catch (error) {
    result = null;
  }
  if (!response.ok) {
    const detail = result?.detail;
    const code = response.headers.get("X-Nexis-Code") || (detail && typeof detail === "object" ? detail.code : null);
    throw new ApiError(code, detail && typeof detail === "object" ? detail.attempts_left : undefined);
  }
  return result;
}

function errorText(error) {
  const code = error instanceof ApiError ? error.code : null;
  let text = code && typeof lookup(NEXIS_TEXTS.fr, `errors.${code}`) === "string" ? t(`errors.${code}`) : t("errors.generic");
  if (code === "wrong_presence_code" && typeof error.attemptsLeft === "number") {
    text += ` ${t("errors.attempts_left", { n: error.attemptsLeft })}`;
  }
  return text;
}

// Bouton occupé le temps d'une demande : un seul envoi à la fois.
async function busy(buttonNode, busyLabel, work) {
  if (buttonNode.disabled) return;
  const label = buttonNode.querySelector("span");
  const previous = label?.textContent;
  buttonNode.disabled = true;
  if (label && busyLabel) label.textContent = busyLabel;
  try {
    await work();
  } finally {
    if (buttonNode.isConnected) {
      buttonNode.disabled = false;
      if (label) label.textContent = previous;
    }
  }
}

// --- Navigation --------------------------------------------------------------

function provider() {
  return state.data?.provider || null;
}

function show(tab) {
  state.tab = tab;
  state.sub = null;
  render();
  window.scrollTo(0, 0);
}

function open(sub) {
  state.sub = sub;
  render();
  window.scrollTo(0, 0);
}

function goBack() {
  state.sub = null;
  render();
}

function updateChrome() {
  const nav = document.getElementById("nav");
  const tabs = !inClientSpace() && !state.sub;
  nav.hidden = !tabs;
  document.body.classList.toggle("with-nav", tabs);
  nav.querySelectorAll("[data-tab]").forEach((item) => {
    if (item.dataset.tab === state.tab) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  nav.querySelectorAll("[data-text]").forEach((item) => { item.textContent = t(item.dataset.text); });
  const count = todoCount();
  const badge = nav.querySelector("[data-tab=missions] .count");
  badge.hidden = count === 0;
  badge.textContent = count > 9 ? "9+" : String(count);
  nav.querySelector("[data-tab=missions]").setAttribute("aria-label", count ? `${t("nav_missions")}, ${t("todo_badge", { n: count })}` : t("nav_missions"));
  try {
    if (state.sub && (state.sub.name !== "register" || state.data?.client)) tg?.BackButton?.show();
    else tg?.BackButton?.hide();
  } catch (error) {
    // BackButton absent des très anciennes versions de Telegram.
  }
}

function render() {
  const view = document.getElementById("view");
  let screen;
  if (state.sub?.name === "mission") screen = missionScreen(state.sub.missionId);
  else if (state.sub?.name === "propose") screen = proposeScreen();
  else if (state.sub?.name === "history") screen = historyScreen();
  else if (state.sub?.name === "add_service") screen = addServiceScreen();
  else if (state.sub?.name === "request_service") screen = requestServiceScreen();
  else if (state.sub?.name === "add_commune") screen = addCommuneScreen();
  else if (state.sub?.name === "register") screen = registerScreen();
  else if (!provider()) screen = state.data?.client ? clientHomeScreen() : registerScreen();
  else if (state.space === "client") screen = clientHomeScreen();
  else if (state.tab === "missions") screen = missionsScreen();
  else if (state.tab === "services") screen = servicesScreen();
  else if (state.tab === "profile") screen = profileScreen();
  else screen = homeScreen();
  view.replaceChildren(...screen);
  updateChrome();
}

function subHeader(title, subtitle) {
  return el("div", { class: "top" },
    el("button", { class: "back", type: "button", "aria-label": t("back"), onclick: goBack }, icon("i-back")),
    el("div", {}, el("b", { text: title }), subtitle ? el("small", { text: subtitle }) : null),
    el("span"));
}

// --- Éléments communs --------------------------------------------------------

// Un seul portefeuille pour les deux rôles, mais la ligne du bas parle au
// rôle affiché : au prestataire, sa part encore sécurisée ; au client, la
// protection de ses paiements.
function walletCard() {
  const wallet = state.data?.wallet;
  const key = state.currency === "USD" ? "wallet_balance_usd" : "wallet_balance_cdf";
  const securedKey = state.currency === "USD" ? "secured_usd" : "secured_cdf";
  const amount = wallet ? formatWalletMoney(wallet[key], state.currency) : null;
  const secured = wallet ? formatWalletMoney(wallet[securedKey] || 0, state.currency) : formatWalletMoney(0, state.currency);
  const currencyLabel = state.currency === "USD" ? "USD" : "CDF";
  const card = el("section", {
    class: "wallet-card",
    "aria-label": t("wallet"),
  },
  el("div", { class: "wallet-card__head" },
    el("span", { class: "wallet-card__brand", text: "NEXIS HUB" }),
    el("div", { class: "wallet-card__currencies", role: "group", "aria-label": t("wallet_currency") },
      ["CDF", "USD"].map((currency) => el("button", {
        type: "button",
        class: "wallet-card__currency",
        "aria-pressed": state.currency === currency ? "true" : "false",
        text: currency,
        onclick: () => {
          if (state.currency !== currency) {
            setCurrency(currency);
            state.walletInfo = false;
            render();
          }
        },
      })))),
  el("div", { class: "wallet-card__label", text: t("available") }),
  el("div", { class: "wallet-card__amount-row", "aria-live": "polite" },
    el("span", { class: "wallet-card__amount", text: amount || t("balance_unknown") }),
    el("button", {
      type: "button",
      class: "wallet-card__eye",
      "aria-label": state.walletHidden ? t("wallet_show_amounts") : t("wallet_hide_amounts"),
      "aria-pressed": state.walletHidden ? "true" : "false",
      title: state.walletHidden ? t("wallet_show_amounts") : t("wallet_hide_amounts"),
      onclick: () => { state.walletHidden = !state.walletHidden; render(); },
    }, walletEye(state.walletHidden))),
  el("div", { class: "wallet-card__locked" },
    icon("i-shield"),
    el("span", { class: "wallet-card__locked-text", text: t("wallet_locked", { amount: state.walletHidden ? "•••••• " + (currencyLabel === "USD" ? "USD" : "FC") : secured }) }),
    el("button", {
      type: "button",
      class: "wallet-card__info",
      "aria-label": t("wallet_info_label"),
      "aria-expanded": state.walletInfo ? "true" : "false",
      title: t("wallet_explanation"),
      onclick: () => { state.walletInfo = !state.walletInfo; render(); },
    }, icon("i-info"))),
  state.walletInfo ? el("p", { class: "wallet-card__explanation", text: t("wallet_explanation") }) : null);
  return card;
}

function walletEye(hidden) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", hidden
    ? "M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.2A10.8 10.8 0 0112 5c5.2 0 8.8 5.2 8.8 7 0 .8-.7 1.8-1.8 2.8M6.2 6.2C3.9 7.7 3 10.3 3 12c0 1.8 3.8 7 9 7 1.2 0 2.3-.3 3.3-.8"
    : "M2.5 12s3.3-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.3 6.5-9.5 6.5S2.5 12 2.5 12zM15 12a3 3 0 11-6 0 3 3 0 016 0z");
  svg.appendChild(path);
  return svg;
}
// Part du prestataire encore en escrow (backend : provider_secured) : pas
// dans le solde, versée quand le client confirme.
function securedText(wallet) {
  const value = wallet?.[state.currency === "USD" ? "secured_usd" : "secured_cdf"];
  return typeof value === "number" && value > 0 ? t("secured_note", { amount: formatMoney(value, state.currency) }) : null;
}

function historyLink() {
  return el("button", { class: "linkcard", type: "button", onclick: () => open({ name: "history" }) },
    el("span", { text: t("history_link") }), icon("i-chev"));
}

function todoCount() {
  return (state.data?.provider_missions || []).filter((mission) => canArrive(mission) || canFinish(mission)).length;
}

// `words` : l'état en mots (le montant est déjà affiché à côté, en grand).
function paymentPill(mission, words = false) {
  const amount = words ? null : formatMoney(mission.net_provider, mission.currency);
  if (mission.payment_status === "paid_escrow") {
    return el("span", { class: "pill p-sec" }, icon("i-shield"), el("span", { text: amount || t("payment_secured") }));
  }
  if (mission.payment_status === "released") {
    return el("span", { class: "pill p-ok" }, icon("i-check"), el("span", { text: amount || t("payment_released") }));
  }
  if (mission.payment_status === "refunded") return el("span", { class: "pill p-wait", text: t("payment_refunded") });
  return el("span", { class: "pill p-wait" }, icon("i-clock"), el("span", { text: t("payment_unpaid") }));
}

function statusText(status) {
  return t(`mission_status.${status}`) === `mission_status.${status}` ? status : t(`mission_status.${status}`);
}

function canArrive(mission) {
  return mission.status === "confirmed" && mission.payment_status === "paid_escrow";
}

function canFinish(mission) {
  return mission.status === "in_progress";
}

function missionCard(mission, asProvider) {
  const other = asProvider ? mission.client_name : mission.provider_name;
  const card = el("div", { class: "card" },
    el("button", {
      class: "row open",
      type: "button",
      "aria-label": `${t("open_mission")} ${missionRef(mission.id)}`,
      onclick: () => open({ name: "mission", missionId: mission.id, role: asProvider ? "provider" : "client" }),
    },
    serviceIcon(mission.service),
    // Le service et la commune d'abord (jamais coupés), puis où en est la
    // mission, puis la référence et l'autre personne, plus discrètes.
    el("div", { class: "mcard" },
      el("b", { class: "wrap", text: [serviceName(mission.service), mission.commune].filter(Boolean).join(" · ") }),
      el("span", { class: `mstate s-${mission.status}`, text: statusText(mission.status) }),
      el("small", { text: [missionRef(mission.id), other].filter(Boolean).join(" · ") })),
    asProvider ? paymentPill(mission) : null,
    icon("i-chev")));
  if (asProvider && canArrive(mission)) {
    card.appendChild(button(t("btn_arrived"), (event) => declareArrival(event.currentTarget, mission.id), { cls: "btn sm wide", iconId: "i-arrived" }));
  } else if (asProvider && canFinish(mission)) {
    card.appendChild(button(t("btn_finish"), (event) => finishMission(event.currentTarget, mission.id), { cls: "btn sm wide", iconId: "i-check" }));
  }
  return card;
}

function replaceMission(updated) {
  const missions = state.data.provider_missions || [];
  state.data.provider_missions = missions.map((mission) => (mission.id === updated.id ? { ...mission, ...updated } : mission));
}

// --- Actions sur les missions (le backend décide, la page affiche) ----------

async function declareArrival(buttonNode, missionId) {
  await busy(buttonNode, null, async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/missions/${missionId}/arrived`, {});
      replaceMission(result.mission);
      if (result.presence?.confirmed) {
        toast(t("started"));
        render();
      } else {
        open({ name: "mission", missionId, role: "provider", arrived: true });
      }
    } catch (error) {
      toast(errorText(error), true);
    }
  });
}

async function finishMission(buttonNode, missionId) {
  await busy(buttonNode, null, async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/missions/${missionId}/finish`, {});
      replaceMission(result.mission);
      toast(t("finished_ok"));
      render();
    } catch (error) {
      toast(errorText(error), true);
    }
  });
}

// --- Écrans du prestataire ---------------------------------------------------

function homeScreen() {
  const me = provider();
  const verified = Boolean(me.is_verified);
  const hello = el("div", { class: "hello" },
    el("div", {}, el("small", { text: t("hello") }), el("b", { text: me.full_name || telegramUser?.first_name || "" })),
    verified ? el("span", { class: "badge" }, icon("i-check"), el("span", { text: t("verified") })) : null);

  if (!verified) return [spaceSwitch(), hello, ...pendingBlock(me)].filter(Boolean);

  const available = me.status === "available";
  const locked = Boolean(me.is_suspended);
  const communes = (me.communes || []).join(", ");
  const hint = locked ? t("suspended_hint") : available ? t("available_hint", { communes }) : t("unavailable_hint");
  const toggle = el("button", {
    class: "toggle",
    type: "button",
    role: "switch",
    "aria-checked": available ? "true" : "false",
    "aria-label": t("available"),
    disabled: locked,
    onclick: (event) => toggleAvailability(event.currentTarget),
  });
  const availability = el("div", { class: "switch" },
    el("span", { class: available && !locked ? "dot on" : "dot" }),
    el("div", {}, el("b", { text: available && !locked ? t("available") : t("unavailable") }), el("small", { text: hint })),
    toggle);

  const rating = Number(me.rating || 0).toLocaleString(LOCALES[state.lang], { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const stats = el("div", { class: "stats" },
    el("div", {}, el("b", { text: String(me.total_missions || 0) }), el("small", { text: t("stat_missions") })),
    el("div", {}, el("b", { text: rating }), el("small", { text: t("stat_rating") })),
    el("div", {}, el("b", { text: `${Math.round(Number(me.success_rate || 0))} %` }), el("small", { text: t("stat_success") })));

  const missions = state.data.provider_missions;
  const todo = (missions || []).filter((mission) => canArrive(mission) || canFinish(mission));
  const todoLabel = el("div", { class: "lbl" }, el("span", { text: t("todo") }),
    el("button", { class: "link", type: "button", text: t("see_all"), onclick: () => show("missions") }));
  const todoList = missions == null
    ? [el("p", { class: "empty", text: t("missions_unavailable") })]
    : todo.length
      ? todo.slice(0, 3).map((mission) => missionCard(mission, true))
      : [el("p", { class: "empty", text: t("todo_empty") })];

  return [spaceSwitch(), hello, availability, walletCard(), historyLink(), stats, todoLabel, ...todoList].filter(Boolean);
}

function pendingBlock(me) {
  const docs = Boolean(me.has_documents);
  const step = (cls, title, sub) => el("div", { class: `step ${cls}` },
    el("span", { class: "d" }, cls === "done" ? icon("i-check") : null),
    el("div", {}, el("b", { text: title }), sub ? el("small", { text: sub }) : null));
  return [
    el("div", { class: "wait" },
      el("span", { class: "bigic" }, icon("i-clock")),
      el("h1", { class: "h1", text: t("pending_title") }),
      el("p", { class: "note", text: t("pending_intro") })),
    el("div", { class: "card" }, el("div", { class: "steps" },
      step("done", t("step_created")),
      docs ? step("done", t("step_docs")) : step("now", t("step_docs_todo"), t("step_docs_todo_sub")),
      step(docs ? "now" : "", t("step_review")),
      step("", t("step_first")))),
    me.is_suspended ? el("p", { class: "msg error", text: t("suspended_hint") }) : null,
  ].filter(Boolean);
}

async function toggleAvailability(toggle) {
  const me = provider();
  const next = me.status === "available" ? "offline" : "available";
  await busy(toggle, null, async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/status`, { status: next });
      state.data.provider = result.provider;
      render();
    } catch (error) {
      toast(errorText(error), true);
    }
  });
}

// Missions du prestataire. Ses demandes comme client sont dans l'espace
// client (bascule en haut de l'accueil).
function missionsScreen() {
  const all = state.data.provider_missions;
  const nodes = [el("h1", { class: "h1", text: t("missions_title") })];

  const active = (all || []).filter((mission) => ACTIVE_STATUSES.includes(mission.status));
  const done = (all || []).filter((mission) => DONE_STATUSES.includes(mission.status));
  const tabs = [["active", t("tab_active"), active], ["done", t("tab_done"), done], ["all", t("tab_all"), all || []]];
  nodes.push(el("div", { class: "seg" }, tabs.map(([key, label, list]) => el("button", {
    type: "button",
    "aria-pressed": state.missionFilter === key ? "true" : "false",
    text: key === "all" ? label : `${label} · ${list.length}`,
    onclick: () => { state.missionFilter = key; render(); },
  }))));

  if (all == null) {
    nodes.push(el("p", { class: "empty", text: t("missions_unavailable") }));
  } else {
    const shown = tabs.find(([key]) => key === state.missionFilter)[2];
    nodes.push(...(shown.length ? shown.map((mission) => missionCard(mission, true)) : [el("p", { class: "empty", text: t("missions_empty") })]));
  }
  return nodes;
}

function step(cls, title, sub) {
  return el("div", { class: `step ${cls}` },
    el("span", { class: "d" }, cls === "done" ? icon("i-check") : null),
    el("div", {}, el("b", { text: title }), sub ? el("small", { text: sub }) : null));
}

const PAID_STATUSES = ["paid_escrow", "released", "split"];
const STARTED_STATUSES = ["in_progress", "awaiting_confirmation", "completed"];

// Chemin de la mission vu par le prestataire : chaque étape est « faite »,
// « en cours » ou à venir, d'après l'état renvoyé par le backend.
function providerSteps(mission, arrivalDeclared) {
  const paid = PAID_STATUSES.includes(mission.payment_status);
  const started = STARTED_STATUSES.includes(mission.status);
  const finished = ["awaiting_confirmation", "completed"].includes(mission.status);
  const paidOut = mission.payment_status === "released";
  const arrived = started || arrivalDeclared;
  const releaseDate = formatDate(mission.release_after);
  const now = (done, current) => (done ? "done" : current ? "now" : "");
  return el("div", { class: "card" }, el("div", { class: "steps" },
    step(now(paid, !paid), t("step_paid"), paid ? formatMoney(mission.net_provider, mission.currency) || t("step_paid_sub") : null),
    step(now(arrived, paid && !arrived), t("step_arrived"), arrived ? t("step_arrived_sub") : null),
    step(now(started, arrived && !started), t("step_code"), t("step_code_sub")),
    step(now(finished, mission.status === "in_progress"), t("step_finish")),
    step(now(paidOut, mission.status === "awaiting_confirmation"), t("step_paid_out"),
      mission.status === "awaiting_confirmation" && releaseDate ? t("release_on", { date: releaseDate }) : t("step_client_confirms"))));
}

function missionScreen(missionId) {
  const asProvider = state.sub.role !== "client";
  const list = asProvider ? state.data.provider_missions : state.data.client_missions;
  const mission = (list || []).find((item) => item.id === missionId);
  if (!mission) {
    state.sub = null;
    return provider() ? missionsScreen() : clientHomeScreen();
  }
  const row = (label, value) => (value ? el("div", { class: "row" }, el("div", {}, el("small", { text: label }), el("b", { class: "wrap", text: value }))) : null);
  const nodes = [
    subHeader(t("mission_title", { ref: missionRef(mission.id) }), `${serviceName(mission.service)} · ${mission.commune || ""}`),
    el("div", { class: "pills" },
      el("span", { class: `mstate s-${mission.status}`, text: statusText(mission.status) }),
      mission.urgent ? el("span", { class: "pill p-bad", text: t("urgent") }) : null),
    // Ta part en premier, en grand : c'est ce que le prestataire cherche.
    asProvider && formatMoney(mission.net_provider, mission.currency)
      ? el("div", { class: "card part" },
        el("small", { text: t("amount_label") }),
        el("b", { text: formatMoney(mission.net_provider, mission.currency) }),
        paymentPill(mission, true))
      : null,
    el("div", { class: "card list" },
      row(asProvider ? t("client_label") : t("provider_label"), asProvider ? mission.client_name : mission.provider_name),
      row(t("description_label"), mission.description)),
  ];
  if (!asProvider) return nodes;

  const arrivalDeclared = Boolean(state.sub.arrived);
  nodes.push(el("div", { class: "lbl" }, el("span", { text: t("details") })), providerSteps(mission, arrivalDeclared));

  if (canFinish(mission)) {
    nodes.push(button(t("btn_finish"), (event) => finishMission(event.currentTarget, mission.id), { iconId: "i-check" }));
  } else if (canArrive(mission) && !arrivalDeclared) {
    nodes.push(button(t("btn_arrived"), (event) => declareArrival(event.currentTarget, mission.id), { iconId: "i-arrived" }));
  } else if (canArrive(mission)) {
    nodes.push(...codeEntry(mission));
  }
  return nodes;
}

function codeEntry(mission) {
  const input = el("input", {
    type: "text",
    inputmode: "numeric",
    autocomplete: "one-time-code",
    maxlength: "4",
    pattern: "[0-9]*",
    "aria-label": t("code_label"),
  });
  const boxes = [0, 1, 2, 3].map(() => el("span", { "aria-hidden": "true" }));
  const otp = el("div", { class: "otp" }, boxes, input);
  const message = el("p", { class: "msg error", role: "alert" });
  const validate = button(t("btn_validate"), () => submitCode(validate, input, message, otp, mission.id));
  validate.disabled = true;

  const paint = () => {
    input.value = input.value.replace(/\D/g, "").slice(0, 4);
    boxes.forEach((box, index) => {
      box.textContent = input.value[index] || "";
      box.className = index < input.value.length ? "f" : index === input.value.length ? "cur" : "";
    });
    validate.disabled = input.value.length !== 4 || otp.classList.contains("locked");
  };
  input.addEventListener("input", () => { message.textContent = ""; paint(); });
  input.addEventListener("focus", () => otp.classList.add("focus"));
  input.addEventListener("blur", () => otp.classList.remove("focus"));
  input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !validate.disabled) validate.click(); });
  paint();

  return [el("div", { class: "lbl" }, el("span", { text: t("code_label") })), otp,
    el("p", { class: "note", text: t("code_note") }), message, validate];
}

// Mouvements du wallet lus dans le registre : le montant est signé par le
// backend, la page ne fait que le mettre en forme.
function historyScreen() {
  const entries = state.data.wallet_history;
  const nodes = [subHeader(t("history_title"))];
  if (entries == null) return [...nodes, el("p", { class: "empty", text: t("history_unavailable") })];
  if (!entries.length) return [...nodes, el("p", { class: "empty", text: t("history_empty") })];
  nodes.push(el("div", { class: "card list" }, entries.map((entry) => {
    const value = Number(entry.amount);
    const credit = value > 0;
    const label = t(`history_kind.${entry.kind}`);
    const amount = formatMoney(Math.abs(value), entry.currency);
    return el("div", { class: "row" },
      el("span", { class: credit ? "mv in" : "mv out", "aria-hidden": "true" }, icon(credit ? "i-check" : "i-wallet")),
      el("div", {},
        el("b", { text: label.startsWith("history_kind.") ? t("history_kind.other") : label }),
        el("small", { text: [formatDate(entry.created_at), entry.mission_id ? missionRef(entry.mission_id) : ""].filter(Boolean).join(" · ") })),
      el("span", { class: credit ? "amt in" : "amt out", text: `${credit ? "+" : "−"} ${amount || ""}` }));
  })));
  return nodes;
}

async function submitCode(buttonNode, input, message, otp, missionId) {
  await busy(buttonNode, null, async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/missions/${missionId}/presence-code`, { code: input.value });
      replaceMission(result.mission);
      toast(t("started"));
      render();
    } catch (error) {
      input.value = "";
      input.dispatchEvent(new Event("input")); // vide les cases
      const locked = error.code === "presence_code_locked";
      if (locked) {
        otp.classList.add("locked");
        input.disabled = true;
      }
      message.textContent = locked ? `${errorText(error)} ${t("code_locked_note")}` : errorText(error);
    }
  });
  if (otp.classList.contains("locked") || input.value.length !== 4) buttonNode.disabled = true;
}

function serviceKeys() {
  const names = state.data.service_names || {};
  const keys = Object.keys(names).length ? Object.keys(names) : Object.keys(state.data.available_services || {});
  return keys;
}

// Services qu'un prestataire peut prendre (le backend refuse les autres).
function providerServiceKeys() {
  const excluded = state.data.provider_excluded_services || [];
  return serviceKeys().filter((key) => !excluded.includes(key));
}

// Mes services et mes communes : chaque ajout ou retrait est enregistré tout
// de suite par le backend, qui vérifie le catalogue (et la limite de
// services) ; la page affiche ce qu'il renvoie.
async function saveProfileList(kind, values, okText) {
  const result = await api(`/api/provider/${telegramUser.id}/${kind}`, { [kind]: values });
  state.data.provider = result.provider;
  if (okText) toast(okText);
}

function removable(label, iconNode, onRemove) {
  return el("div", { class: "row" },
    iconNode,
    el("div", {}, el("b", { text: label })),
    el("button", { class: "remove", type: "button", "aria-label": t("remove_item", { name: label }), onclick: onRemove }, icon("i-close")));
}

// Retrait : toujours après une confirmation, pour qu'un toucher par erreur
// ne retire rien. Fenêtre native de Telegram, sinon celle du navigateur.
function confirmAction(message) {
  return new Promise((resolve) => {
    if (tg?.showConfirm) {
      try {
        tg.showConfirm(message, (ok) => resolve(Boolean(ok)));
        return;
      } catch (error) {
        // Telegram trop ancien : on retombe sur la fenêtre du navigateur.
      }
    }
    resolve(window.confirm(message));
  });
}

async function removeFrom(kind, value, label, buttonNode) {
  const me = provider();
  const remaining = (me[kind] || []).filter((item) => item !== value);
  if (!remaining.length) {
    toast(t(kind === "services" ? "errors.services_required" : "errors.communes_required"), true);
    return;
  }
  const question = t(kind === "services" ? "confirm_remove_service" : "confirm_remove_commune", { name: label });
  if (!(await confirmAction(question))) return;
  await busy(buttonNode, null, async () => {
    try {
      await saveProfileList(kind, remaining, t(kind === "services" ? "service_removed" : "commune_removed"));
      render();
    } catch (error) {
      toast(errorText(error), true);
    }
  });
}

// Demandes d'ajout de service (le backend les garde) : en attente de
// l'équipe, ou dernier refus d'un service sans nouvelle demande.
function pendingAdditions() {
  return (state.data.service_additions || []).filter((item) => item.status === "pending");
}

function lastRejections() {
  const pending = new Set(pendingAdditions().map((item) => item.service_key));
  const seen = new Set();
  const result = [];
  for (const item of state.data.service_additions || []) { // plus récentes d'abord
    if (seen.has(item.service_key)) continue;
    seen.add(item.service_key);
    if (item.status === "rejected" && !pending.has(item.service_key)) result.push(item);
  }
  return result;
}

function servicesScreen() {
  const me = provider();
  const services = me.services || [];
  const communes = me.communes || [];
  const limit = state.data.max_services;
  const pending = pendingAdditions();
  const rejected = lastRejections();
  // Profil créé avant la limite : il garde ses services, sans « 4 sur 3 ».
  const countKey = typeof limit === "number" && services.length > limit ? "services_count_over" : "services_count";
  return [
    el("h1", { class: "h1", text: t("services_title") }),
    typeof limit === "number" ? el("p", { class: "h1s", text: t(countKey, { n: services.length, max: limit }) }) : null,
    el("div", { class: "card list" },
      services.map((key) => removable(serviceName(key), serviceIcon(key, 36), (event) => removeFrom("services", key, serviceName(key), event.currentTarget)))),
    pending.length || rejected.length
      ? el("div", { class: "lbl" }, el("span", { text: t("pending_additions_label") }))
      : null,
    pending.length || rejected.length
      ? el("div", { class: "card list" },
        pending.map((item) => additionRow(item)),
        rejected.map((item) => additionRow(item)))
      : null,
    button(t("add_service"), () => open({ name: "add_service" }), { cls: "btn ghost", iconId: "i-plus" }),
    el("div", { class: "lbl" }, el("span", { text: t("communes_label") })),
    el("div", { class: "card list" },
      communes.map((commune) => removable(commune, el("span", { class: "mv out" }, icon("i-arrived")), (event) => removeFrom("communes", commune, commune, event.currentTarget)))),
    button(t("add_commune"), () => open({ name: "add_commune" }), { cls: "btn ghost", iconId: "i-plus" }),
    el("button", { class: "linkcard", type: "button", onclick: () => open({ name: "propose" }) },
      el("span", { text: t("missing_link") }), el("b", { text: t("missing_cta") })),
  ].filter(Boolean);
}

function additionRow(item) {
  const isPending = item.status === "pending";
  const detail = isPending
    ? t("addition_waiting", { date: formatDate(item.created_at) })
    : [t("addition_rejected"), item.admin_note || ""].filter(Boolean).join(" · ");
  return el("div", { class: "row" },
    serviceIcon(item.service_key, 36),
    el("div", {}, el("b", { text: serviceName(item.service_key) }), el("small", { class: "wrap", text: detail })),
    isPending
      ? el("button", { class: "textbtn", type: "button", onclick: (event) => cancelAddition(item, event.currentTarget) }, el("span", { text: t("addition_cancel") }))
      : el("span", { class: "pill p-bad" }, el("span", { text: t("addition_rejected_pill") })));
}

async function cancelAddition(item, buttonNode) {
  if (!(await confirmAction(t("confirm_cancel_addition", { name: serviceName(item.service_key) })))) return;
  await busy(buttonNode, null, async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/service-additions/${item.id}/cancel`, {});
      state.data.provider = result.provider;
      state.data.service_additions = result.service_additions;
      toast(t("addition_cancelled"));
      render();
    } catch (error) {
      toast(errorText(error), true);
    }
  });
}

function addServiceScreen() {
  const mine = new Set(provider().services || []);
  const waiting = new Set(pendingAdditions().map((item) => item.service_key));
  const used = mine.size + waiting.size; // les demandes en attente comptent
  const choices = providerServiceKeys().filter((key) => !mine.has(key) && !waiting.has(key));
  const limit = state.data.max_services;
  if (typeof limit === "number" && used >= limit) {
    // Limite atteinte : on le dit ici, là où la personne cherche à ajouter.
    let text = t("services_full", { max: limit });
    if (mine.size > limit) text = t("services_over", { n: mine.size, max: limit, k: mine.size - limit + 1 });
    else if (waiting.size) text = t("services_full_pending", { max: limit });
    return [
      subHeader(t("add_service")),
      el("div", { class: "card notice" }, el("b", { text: t("services_limit_title") }), el("p", { text })),
      button(t("back_to_services"), () => goBack(), { cls: "btn ghost" }),
    ];
  }
  const nodes = [subHeader(t("add_service")), el("p", { class: "note", text: t("add_service_review_intro") })];
  if (!choices.length) return [...nodes, el("p", { class: "empty", text: t("nothing_to_add") })];
  nodes.push(el("div", { class: "sgrid" }, choices.map((key) => el("button", {
    type: "button",
    onclick: () => open({ name: "request_service", key, photos: [], description: "" }),
  }, serviceIcon(key, 40), el("span", { text: serviceName(key) })))));
  nodes.push(el("button", { class: "linkcard", type: "button", onclick: () => open({ name: "propose" }) },
    el("span", { text: t("missing_link") }), el("b", { text: t("missing_cta") })));
  return nodes;
}

// --- Demande d'un nouveau service, avec photos -------------------------------
// Les photos sont réduites ici (côté le plus long MAX_PHOTO_SIDE, JPEG) : plus
// légères à envoyer, et sans leurs métadonnées (position GPS de la photo).
// Le serveur revérifie de toute façon le type réel et la taille.

const MAX_PHOTO_SIDE = 1600;
const MAX_PHOTOS = 10;

async function decodeImage(file) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (error) {
      // Navigateur sans cette option : on passe par une balise image.
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function shrinkPhoto(file) {
  let image;
  try {
    image = await decodeImage(file);
  } catch (error) {
    throw new ApiError("unsupported_file_type");
  }
  const width = image.width || image.naturalWidth;
  const height = image.height || image.naturalHeight;
  const scale = Math.min(1, MAX_PHOTO_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
  if (image.close) image.close();
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  if (!blob) throw new ApiError("unsupported_file_type");
  return blob;
}

async function uploadPhoto(blob) {
  let response;
  try {
    response = await fetch(`/api/provider/${telegramUser.id}/photos`, {
      method: "POST",
      headers: { "X-Telegram-Init-Data": tg?.initData || "", "Content-Type": "image/jpeg" },
      body: blob,
    });
  } catch (error) {
    throw new ApiError("backend_unavailable");
  }
  let result = null;
  try {
    result = await response.json();
  } catch (error) {
    result = null;
  }
  if (!response.ok || typeof result?.photo_id !== "string") {
    throw new ApiError(response.headers.get("X-Nexis-Code") || result?.detail?.code || null);
  }
  return result.photo_id;
}

async function addPhotos(files) {
  const sub = state.sub;
  for (const file of Array.from(files)) {
    if (sub.photos.length >= MAX_PHOTOS) {
      toast(t("photos_max", { max: MAX_PHOTOS }), true);
      break;
    }
    const photo = { url: URL.createObjectURL(file), status: "uploading", id: null };
    sub.photos.push(photo);
    if (state.sub === sub) render();
    try {
      photo.id = await uploadPhoto(await shrinkPhoto(file));
      photo.status = "ok";
    } catch (error) {
      photo.status = "error";
      toast(errorText(error), true);
    }
    if (state.sub === sub) render();
  }
}

function removePhoto(photo) {
  const sub = state.sub;
  sub.photos = sub.photos.filter((item) => item !== photo);
  URL.revokeObjectURL(photo.url);
  render();
}

function requestServiceScreen() {
  const sub = state.sub;
  const key = sub.key;
  const picker = el("input", {
    type: "file",
    accept: "image/*",
    multiple: true,
    hidden: true,
    onchange: (event) => { addPhotos(event.target.files); event.target.value = ""; },
  });
  const description = el("textarea", {
    rows: "3",
    maxlength: "500",
    placeholder: t("addition_desc_hint"),
    oninput: (event) => { sub.description = event.target.value; },
  });
  description.value = sub.description || "";
  const uploading = sub.photos.some((photo) => photo.status === "uploading");
  const status = el("p", { class: "msg", role: "status" });
  const send = button(t("addition_send"), () => busy(send, t("sending"), async () => {
    if (sub.photos.some((photo) => photo.status === "uploading")) return;
    try {
      const result = await api(`/api/provider/${telegramUser.id}/service-additions`, {
        service_key: key,
        description: (sub.description || "").trim(),
        photo_ids: sub.photos.filter((photo) => photo.status === "ok").map((photo) => photo.id),
      });
      state.data.provider = result.provider;
      state.data.service_additions = result.service_additions;
      sub.photos.forEach((photo) => URL.revokeObjectURL(photo.url));
      state.tab = "services";
      state.sub = null;
      render();
      toast(t("addition_sent"));
    } catch (error) {
      status.className = "msg error";
      status.textContent = errorText(error);
    }
  }));
  send.disabled = uploading;

  const thumbs = sub.photos.map((photo) => el("div", { class: `thumb ${photo.status}` },
    el("img", { src: photo.url, alt: "" }),
    photo.status === "uploading" ? el("span", { class: "thumb-state", text: t("photo_uploading") }) : null,
    photo.status === "error" ? el("span", { class: "thumb-state", text: t("photo_failed") }) : null,
    el("button", { class: "thumb-x", type: "button", "aria-label": t("photo_remove"), onclick: () => removePhoto(photo) }, icon("i-close"))));

  return [
    subHeader(t("addition_title"), serviceName(key)),
    el("p", { class: "note", text: t("addition_intro") }),
    el("div", { class: "lbl" }, el("span", { text: t("photos_label", { n: sub.photos.length, max: MAX_PHOTOS }) })),
    el("div", { class: "thumbs" },
      thumbs,
      sub.photos.length < MAX_PHOTOS
        ? el("button", { class: "thumb add", type: "button", "aria-label": t("photos_add"), onclick: () => picker.click() }, icon("i-plus"), el("span", { text: t("photos_add") }))
        : null),
    picker,
    el("label", { class: "field" }, el("span", { text: t("addition_desc") }), description),
    status,
    send,
  ];
}

function addCommuneScreen() {
  const mine = new Set(provider().communes || []);
  const choices = (state.data.available_communes || []).filter((commune) => !mine.has(commune));
  const nodes = [subHeader(t("add_commune"))];
  if (!choices.length) return [...nodes, el("p", { class: "empty", text: t("nothing_to_add") })];
  nodes.push(el("div", { class: "chips" }, choices.map((commune) => el("button", {
    type: "button",
    text: commune,
    onclick: (event) => busy(event.currentTarget, null, async () => {
      try {
        await saveProfileList("communes", [...mine, commune], t("commune_added", { name: commune }));
        goBack();
      } catch (error) {
        toast(errorText(error), true);
      }
    }),
  }))));
  return nodes;
}

function proposeScreen() {
  const name = el("input", { type: "text", maxlength: "80", autocomplete: "off" });
  const description = el("textarea", { rows: "3", maxlength: "500" });
  const status = el("p", { class: "msg", role: "status" });
  const send = button(t("propose_send"), () => busy(send, t("sending"), async () => {
    try {
      const result = await api(`/api/provider/${telegramUser.id}/service-requests`, {
        service_name: name.value.trim(),
        description: description.value.trim(),
      });
      state.data.service_requests = result.service_requests;
      render();
      toast(t("propose_sent"));
    } catch (error) {
      status.className = "msg error";
      status.textContent = errorText(error);
    }
  }));

  const requests = state.data.service_requests || [];
  const pillFor = (requestStatus) => {
    const cls = requestStatus === "accepted" ? "p-ok" : requestStatus === "rejected" ? "p-bad" : "p-wait";
    const iconId = requestStatus === "accepted" ? "i-check" : requestStatus === "pending" ? "i-clock" : null;
    const label = t(`request_status.${requestStatus}`);
    return el("span", { class: `pill ${cls}` }, iconId ? icon(iconId) : null, el("span", { text: label.startsWith("request_status.") ? requestStatus : label }));
  };
  const list = requests.length
    ? el("div", { class: "card list" }, requests.map((request) => el("div", { class: "row" },
      el("div", {},
        el("b", { text: request.service_name }),
        el("small", { class: "wrap", text: [formatDate(request.created_at) ? t("sent_on", { date: formatDate(request.created_at) }) : "", request.admin_note || ""].filter(Boolean).join(" · ") })),
      pillFor(request.status))))
    : el("p", { class: "empty", text: t("requests_empty") });

  return [
    subHeader(t("propose_title")),
    el("p", { class: "note", text: t("propose_intro") }),
    el("label", { class: "field" }, el("span", { text: t("propose_name") }), name),
    el("label", { class: "field" }, el("span", { text: t("propose_desc") }), description),
    status,
    send,
    el("div", { class: "lbl" }, el("span", { text: t("my_requests") })),
    list,
  ];
}

// Affichage seulement : +243 812 345 678 (groupes de 3), le numéro enregistré
// ne change pas. Un numéro qui n'est pas congolais reste tel quel.
function formatPhone(value) {
  const digits = String(value || "").replace(/\s+/g, "");
  const match = /^\+243(\d{3})(\d{3})(\d{3})$/.exec(digits);
  return match ? `+243 ${match[1]} ${match[2]} ${match[3]}` : value;
}

function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  return (parts.slice(0, 2).map((part) => part[0]).join("") || "N").toUpperCase();
}

function profileScreen() {
  const me = provider();
  const badgeKey = me.is_verified ? (me.badge && me.badge !== "pending" ? me.badge : "verified") : "pending";
  const badgeText = t(`badge.${badgeKey}`);
  const row = (label, value, note) => el("div", { class: "row" },
    el("div", {}, el("small", { text: label }), el("b", { class: "wrap", text: value || "–" }), note ? el("small", { class: "wrap", text: note }) : null));
  return [
    el("div", { class: "prof" },
      el("span", { class: "avatar", "aria-hidden": "true", text: initials(me.full_name) }),
      el("b", { text: me.full_name || "" }),
      el("span", { class: me.is_verified ? "badge" : "badge wait" }, icon(me.is_verified ? "i-check" : "i-clock"), el("span", { text: badgeText }))),
    el("div", { class: "card list" },
      row(t("phone"), formatPhone(me.phone_number)),
      row(t("services"), (me.services || []).map(serviceName).join(", ")),
      row(t("communes"), (me.communes || []).join(", ")),
      row(t("language"), LANGUAGE_NAMES[state.lang], t("language_note"))),
    el("div", { class: "info" }, icon("i-shield"), el("span", { text: t("id_note") })),
  ];
}

// --- Inscription d'un nouveau prestataire -----------------------------------

function registerScreen() {
  const client = state.data?.client;
  const fullName = el("input", { type: "text", autocomplete: "name", maxlength: "80", placeholder: t("full_name_hint"), value: client?.first_name || "" });
  const phone = el("input", { type: "tel", autocomplete: "tel", inputmode: "tel", maxlength: "20", placeholder: "+243…", value: client?.phone_number || "" });
  const services = new Set();
  const communes = new Set();
  const limit = state.data.max_services;
  const chip = (set, value, label, max = null) => el("button", {
    type: "button",
    "aria-pressed": "false",
    text: label,
    onclick: (event) => {
      if (set.has(value)) set.delete(value);
      else if (typeof max === "number" && set.size >= max) {
        toast(t("services_full", { max }), true);
        return;
      } else set.add(value);
      event.currentTarget.setAttribute("aria-pressed", set.has(value) ? "true" : "false");
      if (set === services && servicesCount) servicesCount.textContent = `${services.size}/${limit}`;
    },
  });
  // Compteur « 1/3 » à côté du titre : la limite se voit avant d'être atteinte.
  const servicesCount = typeof limit === "number" ? el("span", { class: "count", text: `0/${limit}` }) : null;
  const status = el("p", { class: "msg error", role: "alert" });
  const create = button(t("create"), () => busy(create, t("creating"), async () => {
    status.textContent = "";
    try {
      const result = await api(`/api/provider/${telegramUser.id}/register`, {
        full_name: fullName.value.trim(),
        phone_number: phone.value.trim(),
        services: [...services],
        communes: [...communes],
        language: state.lang,
      });
      state.data.provider = result.provider;
      state.data.provider_missions = [];
      state.data.service_requests = [];
      setSpace("provider");
    } catch (error) {
      status.textContent = errorText(error);
    }
  }));

  return [
    state.data?.client ? subHeader(t("become_provider")) : null,
    el("h1", { class: "h1", text: t("register_title") }),
    el("p", { class: "h1s", text: t("register_intro") }),
    el("label", { class: "field" }, el("span", { text: t("full_name") }), fullName),
    el("label", { class: "field" }, el("span", { text: t("phone_label") }), phone),
    el("div", { class: "lbl" }, el("span", { text: t("your_services") }), servicesCount),
    typeof limit === "number" ? el("p", { class: "note", text: t("services_pick_max", { max: limit }) }) : null,
    el("div", { class: "chips" }, providerServiceKeys().map((key) => chip(services, key, serviceName(key), limit))),
    el("div", { class: "lbl" }, el("span", { text: t("your_communes") })),
    el("div", { class: "chips" }, (state.data?.available_communes || []).map((commune) => chip(communes, commune, commune))),
    status,
    create,
  ].filter(Boolean);
}

// --- Personne seulement cliente ---------------------------------------------

function clientHomeScreen() {
  const client = state.data.client;
  const me = provider();
  const missions = state.data.client_missions;
  const list = missions == null
    ? [el("p", { class: "empty", text: t("missions_unavailable") })]
    : missions.length
      ? missions.map((mission) => missionCard(mission, false))
      : [el("p", { class: "empty", text: t("missions_empty") })];
  const name = client?.first_name || (me?.full_name || "").split(/\s+/)[0] || telegramUser?.first_name || "";
  return [
    spaceSwitch(),
    el("div", { class: "hello" }, el("div", {}, el("small", { text: t("hello") }), el("b", { text: name }))),
    me && !me.is_verified
      ? el("button", { class: "info act", type: "button", onclick: () => setSpace("provider") },
        icon("i-clock"), el("span", { text: t("provider_pending_note") }), icon("i-chev"))
      : null,
    walletCard(),
    historyLink(),
    el("div", { class: "lbl" }, el("span", { text: t("client_requests") })),
    ...list,
    el("div", { class: "info" }, icon("i-info"), el("span", { text: t("client_note") })),
    me ? null : el("button", { class: "pick", type: "button", onclick: () => open({ name: "register" }) },
      el("span", { class: "pi" }, icon("i-toolbox")),
      el("div", {}, el("b", { text: t("become_provider") }), el("small", { text: t("become_provider_sub") })),
      icon("i-chev")),
  ].filter(Boolean);
}

// --- Démarrage ---------------------------------------------------------------

function applyTheme() {
  const dark = tg?.colorScheme ? tg.colorScheme === "dark" : window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  try {
    const background = dark ? "#0B1424" : "#F6F8FB";
    tg?.setBackgroundColor?.(background);
    tg?.setHeaderColor?.(background);
  } catch (error) {
    // Couleurs d'en-tête non prises en charge par cette version de Telegram.
  }
}

function messageScreen(text, withRetry) {
  document.getElementById("view").replaceChildren(el("div", { class: "center" },
    el("span", { class: "bigic" }, icon("i-info")),
    el("p", { class: "note", text }),
    withRetry ? button(t("retry"), () => load(), { cls: "btn sm" }) : null));
  updateChrome();
}

async function load() {
  document.getElementById("view").replaceChildren(el("div", { class: "center" },
    el("span", { class: "spin", "aria-hidden": "true" }), el("p", { class: "note", text: t("loading") })));
  try {
    const data = await api(`/api/profile/${telegramUser.id}`);
    state.data = data;
    state.space = defaultSpace();
    state.lang = pickLanguage(data.language);
    document.documentElement.lang = state.lang;
    render();
  } catch (error) {
    messageScreen(errorText(error), true);
  }
}

function start() {
  state.lang = pickLanguage(null);
  document.documentElement.lang = state.lang;
  applyTheme();
  document.querySelectorAll("#nav [data-tab]").forEach((item) => {
    item.addEventListener("click", () => show(item.dataset.tab));
  });
  if (tg) {
    tg.ready();
    tg.expand();
    tg.onEvent?.("themeChanged", applyTheme);
    tg.BackButton?.onClick?.(goBack);
  }
  if (!telegramUser?.id || !tg?.initData) {
    messageScreen(t("outside_telegram"), false);
    return;
  }
  load();
}

start();
