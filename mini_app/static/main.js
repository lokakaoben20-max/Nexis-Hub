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

const state = {
  data: null,
  lang: "fr",
  tab: "home",
  sub: null, // sous-écran : { name: "mission" | "propose" | "register", missionId }
  missionFilter: "active",
  missionRole: "provider",
  currency: "CDF",
};

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
  const tabs = Boolean(provider()) && !state.sub;
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
  else if (state.sub?.name === "add_commune") screen = addCommuneScreen();
  else if (state.sub?.name === "register") screen = registerScreen();
  else if (!provider()) screen = state.data?.client ? clientHomeScreen() : registerScreen();
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

function walletCard() {
  const wallet = state.data?.wallet;
  const key = state.currency === "USD" ? "wallet_balance_usd" : "wallet_balance_cdf";
  const amount = wallet ? formatMoney(wallet[key], state.currency) : null;
  const currencyLabel = state.currency === "USD" ? "USD" : "FC";
  return el("button", {
    class: "wallet",
    type: "button",
    "aria-label": `${t("wallet")} · ${currencyLabel}. ${t("wallet_switch")}`,
    onclick: () => { state.currency = state.currency === "USD" ? "CDF" : "USD"; render(); },
  },
  el("small", { text: `${t("wallet")} · ${currencyLabel}` }),
  el("span", { class: "big", text: amount || t("balance_unknown") }),
  el("span", { class: "row2" }, icon("i-shield"), el("span", { text: securedText(wallet) || t("wallet_note") })),
  el("span", { class: "dots", "aria-hidden": "true" },
    el("i", { class: state.currency === "CDF" ? "on" : "" }),
    el("i", { class: state.currency === "USD" ? "on" : "" })));
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

function paymentPill(mission) {
  const amount = formatMoney(mission.net_provider, mission.currency);
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
    el("div", {},
      el("b", { text: `${serviceName(mission.service)} · ${mission.commune || ""}` }),
      el("small", { class: "wrap", text: [missionRef(mission.id), statusText(mission.status), other].filter(Boolean).join(" · ") })),
    asProvider ? paymentPill(mission) : el("span", { class: "pill p-wait", text: statusText(mission.status) }),
    icon("i-chev")));
  if (asProvider && canArrive(mission)) {
    card.appendChild(button(t("btn_arrived"), (event) => declareArrival(event.currentTarget, mission.id), { cls: "btn sm", iconId: "i-arrived" }));
  } else if (asProvider && canFinish(mission)) {
    card.appendChild(button(t("btn_finish"), (event) => finishMission(event.currentTarget, mission.id), { cls: "btn sm", iconId: "i-check" }));
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

  if (!verified) return [hello, ...pendingBlock(me)];

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

  return [hello, availability, walletCard(), historyLink(), stats, todoLabel, ...todoList];
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

function missionsScreen() {
  const clientMissions = state.data.client_missions || [];
  const both = clientMissions.length > 0;
  const asProvider = !both || state.missionRole === "provider";
  const all = asProvider ? state.data.provider_missions : state.data.client_missions;
  const nodes = [el("h1", { class: "h1", text: t("missions_title") })];

  if (both) {
    nodes.push(el("div", { class: "seg role", style: "--n:2" },
      ["provider", "client"].map((role) => el("button", {
        type: "button",
        "aria-pressed": state.missionRole === role ? "true" : "false",
        text: t(`role_${role}`),
        onclick: () => { state.missionRole = role; render(); },
      }))));
  }

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
    nodes.push(...(shown.length ? shown.map((mission) => missionCard(mission, asProvider)) : [el("p", { class: "empty", text: t("missions_empty") })]));
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
      el("span", { class: "pill p-wait", text: statusText(mission.status) }),
      asProvider ? paymentPill(mission) : null,
      mission.urgent ? el("span", { class: "pill p-bad", text: t("urgent") }) : null),
    el("div", { class: "card list" },
      row(asProvider ? t("client_label") : t("provider_label"), asProvider ? mission.client_name : mission.provider_name),
      row(t("commune_label"), mission.commune),
      row(t("description_label"), mission.description),
      asProvider ? row(t("amount_label"), formatMoney(mission.net_provider, mission.currency)) : null),
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

function servicesScreen() {
  const me = provider();
  const services = me.services || [];
  const communes = me.communes || [];
  const limit = state.data.max_services;
  // Profil créé avant la limite : il garde ses services, sans « 4 sur 3 ».
  const countKey = typeof limit === "number" && services.length > limit ? "services_count_over" : "services_count";
  return [
    el("h1", { class: "h1", text: t("services_title") }),
    typeof limit === "number" ? el("p", { class: "h1s", text: t(countKey, { n: services.length, max: limit }) }) : null,
    el("div", { class: "card list" },
      services.map((key) => removable(serviceName(key), serviceIcon(key, 36), (event) => removeFrom("services", key, serviceName(key), event.currentTarget)))),
    button(t("add_service"), () => open({ name: "add_service" }), { cls: "btn ghost", iconId: "i-plus" }),
    el("div", { class: "lbl" }, el("span", { text: t("communes_label") })),
    el("div", { class: "card list" },
      communes.map((commune) => removable(commune, el("span", { class: "mv out" }, icon("i-arrived")), (event) => removeFrom("communes", commune, commune, event.currentTarget)))),
    button(t("add_commune"), () => open({ name: "add_commune" }), { cls: "btn ghost", iconId: "i-plus" }),
    el("button", { class: "linkcard", type: "button", onclick: () => open({ name: "propose" }) },
      el("span", { text: t("missing_link") }), el("b", { text: t("missing_cta") })),
  ].filter(Boolean);
}

function addServiceScreen() {
  const mine = new Set(provider().services || []);
  const choices = providerServiceKeys().filter((key) => !mine.has(key));
  const limit = state.data.max_services;
  if (typeof limit === "number" && mine.size >= limit) {
    // Limite atteinte : on le dit ici, là où la personne cherche à ajouter.
    return [
      subHeader(t("add_service")),
      el("div", { class: "card notice" },
        el("b", { text: t("services_limit_title") }),
        el("p", { text: t("services_full", { max: limit }) })),
      button(t("back_to_services"), () => goBack(), { cls: "btn ghost" }),
    ];
  }
  const nodes = [subHeader(t("add_service")), el("p", { class: "note", text: t("add_service_intro") })];
  if (!choices.length) return [...nodes, el("p", { class: "empty", text: t("nothing_to_add") })];
  nodes.push(el("div", { class: "sgrid" }, choices.map((key) => el("button", {
    type: "button",
    onclick: (event) => busy(event.currentTarget, null, async () => {
      try {
        await saveProfileList("services", [...mine, key], t("service_added", { name: serviceName(key) }));
        goBack();
      } catch (error) {
        toast(errorText(error), true);
      }
    }),
  }, serviceIcon(key, 40), el("span", { text: serviceName(key) })))));
  nodes.push(el("button", { class: "linkcard", type: "button", onclick: () => open({ name: "propose" }) },
    el("span", { text: t("missing_link") }), el("b", { text: t("missing_cta") })));
  return nodes;
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
      row(t("phone"), me.phone_number),
      row(t("services"), (me.services || []).map(serviceName).join(", ")),
      row(t("communes"), (me.communes || []).join(", ")),
      row(t("language"), LANGUAGE_NAMES[state.lang], t("language_note"))),
    el("div", { class: "info" }, icon("i-shield"), el("span", { text: t("id_note") })),
  ];
}

// --- Inscription d'un nouveau prestataire -----------------------------------

function registerScreen() {
  const client = state.data?.client;
  const fullName = el("input", { type: "text", autocomplete: "name", maxlength: "80", value: client?.first_name || "" });
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
    },
  });
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
      show("home");
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
    el("div", { class: "lbl" }, el("span", { text: t("your_services") })),
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
  const missions = state.data.client_missions;
  const list = missions == null
    ? [el("p", { class: "empty", text: t("missions_unavailable") })]
    : missions.length
      ? missions.map((mission) => missionCard(mission, false))
      : [el("p", { class: "empty", text: t("missions_empty") })];
  return [
    el("div", { class: "hello" }, el("div", {}, el("small", { text: t("hello") }), el("b", { text: client.first_name || telegramUser?.first_name || "" }))),
    walletCard(),
    historyLink(),
    el("div", { class: "lbl" }, el("span", { text: t("client_requests") })),
    ...list,
    el("div", { class: "info" }, icon("i-info"), el("span", { text: t("client_note") })),
    el("button", { class: "pick", type: "button", onclick: () => open({ name: "register" }) },
      el("span", { class: "pi" }, icon("i-toolbox")),
      el("div", {}, el("b", { text: t("become_provider") }), el("small", { text: t("become_provider_sub") })),
      icon("i-chev")),
  ];
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
