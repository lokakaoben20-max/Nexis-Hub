const tg = window.Telegram?.WebApp;
let telegramUser = null;
let missionFilter = "all";
let availableServices = {
  service_plomberie: "Plomberie",
  service_electricite: "Electricite",
  service_climatisation: "Climatisation",
  service_informatique: "Informatique",
  service_graphisme: "Graphisme",
  service_coiffure: "Coiffure",
  service_nettoyage: "Nettoyage",
  service_jardinage: "Jardinage",
  service_autre: "Autre service",
};
const defaultCommunes = ["Gombe", "Kinshasa", "Limete", "Ngaliema", "Lemba", "Kalamu", "Barumbu", "Lingwala", "Autre commune"];

if (tg) {
  tg.ready();
  tg.expand();

  telegramUser = tg.initDataUnsafe?.user;
  if (telegramUser?.first_name) {
    document.getElementById("hello").textContent = `Bonjour ${telegramUser.first_name}`;
  }
}

document.querySelectorAll("[data-role]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-role]").forEach((item) => item.classList.remove("primary"));
    button.classList.add("primary");
    renderRole(button.dataset.role, window.nexisProfile);
  });
});

document.querySelectorAll("[data-mission-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-mission-filter]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    missionFilter = button.dataset.missionFilter;
    renderRole(currentRole(), window.nexisProfile);
  });
});

function serviceLabel(key) {
  return availableServices[key] || key;
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function telegramHeaders(extraHeaders = {}) {
  return {
    ...extraHeaders,
    "X-Telegram-Init-Data": tg?.initData || "",
  };
}

function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: telegramHeaders(options.headers || {}),
  });
}

function renderRows(containerId, rows, emptyText) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (!rows.length) {
    container.innerHTML = `<div class="row"><strong>${emptyText}</strong><span>Les donnees apparaitront ici.</span></div>`;
    return;
  }

  rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `<strong>${row.title}</strong><span>${row.subtitle}</span>`;
    container.appendChild(item);
  });
}

function renderMissions(containerId, missions, emptyText, role) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (!missions.length) {
    container.innerHTML = `<div class="row"><strong>${emptyText}</strong><span>Les donnees apparaitront ici.</span></div>`;
    return;
  }

  missions.forEach((mission) => {
    const item = document.createElement("div");
    item.className = "row mission-row";
    const canStart = role === "provider" && mission.status === "confirmed" && mission.payment_status === "paid_escrow";
    const canFinish = role === "provider" && mission.status === "in_progress";
    const action = canStart
      ? `<button class="inline-button" type="button" data-mission-action="start" data-mission-id="${mission.id}">Demarrer</button>`
      : canFinish
        ? `<button class="inline-button" type="button" data-mission-action="finish" data-mission-id="${mission.id}">Terminer</button>`
        : "";

    item.innerHTML = `
      <div>
        <strong>NXH-${String(mission.id).padStart(4, "0")} | ${serviceLabel(mission.service)}</strong>
        <span>${mission.commune} | ${missionStatusLabel(mission.status)} | ${paymentStatusLabel(mission.payment_status)}</span>
      </div>
      ${action}
    `;
    container.appendChild(item);
  });
}

function currentRole() {
  return document.querySelector("[data-role].primary")?.dataset.role || "client";
}

function renderRole(role, data) {
  if (!data) return;

  const isProvider = role === "provider";
  const profile = isProvider ? data.provider : data.client;
  const missions = isProvider ? data.provider_missions : data.client_missions;
  const services = data.provider?.services || [];
  const hasProvider = Boolean(data.provider);

  setText("profile-type", profile ? (isProvider ? "Prestataire" : "Client") : "Non enregistre");
  setText("missions-count", String(missions.length));
  setText("services-count", isProvider ? String(services.length) : "-");
  document.querySelectorAll(".provider-only").forEach((panel) => {
    panel.hidden = !isProvider;
  });
  document.querySelectorAll("#provider-overview, #provider-wallet, #provider-tools, #missing-service-panel").forEach((panel) => {
    panel.hidden = !isProvider || !hasProvider;
  });
  document.getElementById("provider-registration").hidden = !isProvider || hasProvider;
  document.querySelectorAll(".client-only").forEach((panel) => {
    panel.hidden = isProvider;
  });

  if (!profile) {
    renderRows("profile-details", [{ title: "Profil introuvable", subtitle: "L'inscription se fait encore dans le bot Telegram." }], "");
  } else if (isProvider) {
    renderRows("profile-details", [
      { title: profile.full_name || "Prestataire", subtitle: `Statut: ${profile.status} | Badge: ${profile.badge}` },
      { title: "Services", subtitle: services.map(serviceLabel).join(", ") || "Aucun service" },
      { title: "Communes", subtitle: (profile.communes || []).join(", ") || "Aucune commune" },
    ], "Aucune information");
  } else {
    renderRows("profile-details", [
      { title: profile.first_name || "Client", subtitle: `Telephone: ${profile.phone_number || "Non renseigne"}` },
      { title: "Wallet", subtitle: `${profile.wallet_balance_usd || 0} USD | ${profile.wallet_balance_cdf || 0} CDF` },
    ], "Aucune information");
  }

  const visibleMissions = filteredMissions(missions, role);
  updateMissionFilterStatus(role, missions.length, visibleMissions.length);

  renderMissions(
    "missions-list",
    visibleMissions,
    "Aucune mission recente",
    role
  );

  if (isProvider && hasProvider) {
    renderProviderOverview(data);
    renderServicesEditor(data);
    renderServiceRequests(data.service_requests || []);
  } else if (isProvider) {
    renderProviderRegistration(data);
  }
}

function money(value, currency) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} ${currency}`;
}

function statusLabel(status) {
  const labels = {
    available: "Disponible",
    paused: "En pause",
    offline: "Indisponible",
  };
  return labels[status] || status || "Statut inconnu";
}

function badgeLabel(badge) {
  const labels = {
    pending: "En attente",
    verified: "Verifie",
    premium: "Premium",
    expert: "Expert",
    partner: "Partner",
  };
  return labels[badge] || badge || "En attente";
}

function missionStatusLabel(status) {
  const labels = {
    pending: "En attente",
    quoted: "Devis recu",
    confirmed: "Confirmee",
    in_progress: "En cours",
    awaiting_confirmation: "Attente client",
    completed: "Terminee",
    cancelled: "Annulee",
    disputed: "Litige",
  };
  return labels[status] || status || "Statut inconnu";
}

function paymentStatusLabel(status) {
  const labels = {
    unpaid: "Non paye",
    paid_escrow: "Paiement securise",
    released: "Paiement libere",
    refunded: "Rembourse",
  };
  return labels[status] || status || "Paiement inconnu";
}

function filteredMissions(missions, role) {
  if (role !== "provider" || missionFilter === "all") return missions;
  if (missionFilter === "active") {
    return missions.filter((mission) => ["pending", "quoted", "confirmed", "in_progress", "awaiting_confirmation"].includes(mission.status));
  }
  if (missionFilter === "done") {
    return missions.filter((mission) => ["completed", "cancelled", "disputed"].includes(mission.status));
  }
  return missions;
}

function updateMissionFilterStatus(role, total, visible) {
  if (role !== "provider") {
    setText("missions-filter-status", "Toutes les missions visibles.");
    return;
  }
  const label = {
    all: "Toutes les missions visibles.",
    active: "Missions en attente ou en cours.",
    done: "Missions terminees, annulees ou en litige.",
  }[missionFilter];
  setText("missions-filter-status", `${label} ${visible}/${total}`);
}

function renderProviderOverview(data) {
  const provider = data.provider;
  const statusButton = document.getElementById("toggle-provider-status");
  if (!provider) {
    setText("provider-name", "Profil prestataire introuvable");
    setText("provider-meta", "Inscris-toi comme prestataire dans le bot Telegram.");
    setText("provider-status-pill", "Non inscrit");
    statusButton.disabled = true;
    statusButton.textContent = "Inscription requise";
    return;
  }

  setText("provider-name", provider.full_name || "Prestataire");
  setText("provider-meta", `Badge: ${badgeLabel(provider.badge)} | Module ${provider.module || "A"}`);
  setText("provider-status-pill", statusLabel(provider.status));
  setText("provider-missions-total", String(provider.total_missions || 0));
  setText("provider-rating", Number(provider.rating || 0).toFixed(1));
  setText("provider-success-rate", `${Number(provider.success_rate || 0).toFixed(0)}%`);
  setText("provider-wallet-usd", money(provider.wallet_balance_usd, "USD"));
  setText("provider-wallet-cdf", money(provider.wallet_balance_cdf, "CDF"));
  statusButton.disabled = false;
  statusButton.textContent = provider.status === "available" ? "Me rendre indisponible" : "Me rendre disponible";
}

function renderServicesEditor(data) {
  const container = document.getElementById("services-editor");
  const selected = new Set(data.provider?.services || []);
  const services = data.available_services || availableServices;
  container.innerHTML = "";

  Object.entries(services).forEach(([key, label]) => {
    const row = document.createElement("label");
    row.className = "check-row";
    row.innerHTML = `<input type="checkbox" value="${key}" ${selected.has(key) ? "checked" : ""} /><span>${label}</span>`;
    container.appendChild(row);
  });
}

function renderCheckList(containerId, items, selectedValues = []) {
  const container = document.getElementById(containerId);
  const selected = new Set(selectedValues);
  container.innerHTML = "";

  Object.entries(items).forEach(([key, label]) => {
    const row = document.createElement("label");
    row.className = "check-row";
    row.innerHTML = `<input type="checkbox" value="${key}" ${selected.has(key) ? "checked" : ""} /><span>${label}</span>`;
    container.appendChild(row);
  });
}

function renderProviderRegistration(data) {
  renderCheckList("provider-register-services", data.available_services || availableServices);
  const communes = data.available_communes || defaultCommunes;
  const communeItems = Object.fromEntries(communes.map((commune) => [commune, commune]));
  renderCheckList("provider-register-communes", communeItems);
}

function selectedServices() {
  return Array.from(document.querySelectorAll("#services-editor input:checked")).map((input) => input.value);
}

function renderServiceRequests(requests) {
  renderRows(
    "service-requests-list",
    requests.map((request) => ({
      title: request.service_name,
      subtitle: `Statut: ${request.status}${request.admin_note ? ` | Note: ${request.admin_note}` : ""}`,
    })),
    "Aucune proposition envoyee"
  );
}

async function saveServices() {
  if (!telegramUser?.id) {
    setText("services-status", "Ouvre la Mini App depuis Telegram pour enregistrer.");
    return;
  }

  const services = selectedServices();
  if (!services.length) {
    setText("services-status", "Choisis au moins un service.");
    return;
  }

  const button = document.getElementById("save-services");
  button.disabled = true;
  setText("services-status", "Enregistrement...");

  try {
    const response = await apiFetch(`/api/provider/${telegramUser.id}/services`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ services }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Erreur");

    window.nexisProfile.provider = result.provider;
    setText("services-status", "Services enregistres.");
    renderRole("provider", window.nexisProfile);
  } catch (error) {
    setText("services-status", error.message || "Impossible d'enregistrer.");
  } finally {
    button.disabled = false;
  }
}

async function sendMissingService() {
  if (!telegramUser?.id) {
    setText("missing-service-status", "Ouvre la Mini App depuis Telegram pour envoyer.");
    return;
  }

  const serviceName = document.getElementById("missing-service-name").value.trim();
  const description = document.getElementById("missing-service-description").value.trim();
  const button = document.getElementById("send-missing-service");

  button.disabled = true;
  setText("missing-service-status", "Envoi...");

  try {
    const response = await apiFetch(`/api/provider/${telegramUser.id}/service-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_name: serviceName, description }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Erreur");

    window.nexisProfile.service_requests = result.service_requests;
    document.getElementById("missing-service-name").value = "";
    document.getElementById("missing-service-description").value = "";
    setText("missing-service-status", "Proposition envoyee a Nexis Hub.");
    renderServiceRequests(result.service_requests);
  } catch (error) {
    setText("missing-service-status", error.message || "Impossible d'envoyer.");
  } finally {
    button.disabled = false;
  }
}

async function toggleProviderStatus() {
  if (!telegramUser?.id || !window.nexisProfile?.provider) return;

  const currentStatus = window.nexisProfile.provider.status;
  const nextStatus = currentStatus === "available" ? "offline" : "available";
  const button = document.getElementById("toggle-provider-status");

  button.disabled = true;
  button.textContent = "Mise a jour...";

  try {
    const response = await apiFetch(`/api/provider/${telegramUser.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Erreur");

    window.nexisProfile.provider = result.provider;
    renderRole("provider", window.nexisProfile);
  } catch (error) {
    button.disabled = false;
    button.textContent = currentStatus === "available" ? "Me rendre indisponible" : "Me rendre disponible";
  }
}

function replaceProviderMission(updatedMission) {
  const missions = window.nexisProfile?.provider_missions || [];
  window.nexisProfile.provider_missions = missions.map((mission) => (
    mission.id === updatedMission.id ? { ...mission, ...updatedMission } : mission
  ));
}

async function updateMissionAction(action, missionId) {
  if (!telegramUser?.id) return;

  const endpoint = action === "start" ? "start" : "finish";
  const response = await apiFetch(`/api/provider/${telegramUser.id}/missions/${missionId}/${endpoint}`, {
    method: "POST",
  });
  const result = await response.json();
  if (!response.ok) {
    alert(result.detail || "Action impossible");
    return;
  }
  replaceProviderMission(result.mission);
  renderRole("provider", window.nexisProfile);
}

function checkedValues(containerId) {
  return Array.from(document.querySelectorAll(`#${containerId} input:checked`)).map((input) => input.value);
}

async function registerProvider() {
  if (!telegramUser?.id) {
    setText("provider-registration-status", "Ouvre la Mini App depuis Telegram pour t'inscrire.");
    return;
  }

  const fullName = document.getElementById("provider-register-name").value.trim();
  const phoneNumber = document.getElementById("provider-register-phone").value.trim();
  const services = checkedValues("provider-register-services");
  const communes = checkedValues("provider-register-communes");
  const button = document.getElementById("register-provider");

  button.disabled = true;
  setText("provider-registration-status", "Creation du profil...");

  try {
    const response = await apiFetch(`/api/provider/${telegramUser.id}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        phone_number: phoneNumber,
        services,
        communes,
        language: "fr",
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Erreur");

    window.nexisProfile.provider = result.provider;
    window.nexisProfile.provider_missions = [];
    window.nexisProfile.service_requests = [];
    setText("provider-registration-status", "Profil prestataire cree.");
    renderRole("provider", window.nexisProfile);
  } catch (error) {
    setText("provider-registration-status", error.message || "Impossible de creer le profil.");
  } finally {
    button.disabled = false;
  }
}

async function loadProfile() {
  if (!telegramUser?.id) {
    setText("profile-status", "Mode test local : ouvre la Mini App depuis Telegram pour voir tes vraies donnees.");
    renderRole("client", {
      client: null,
      provider: null,
      client_missions: [],
      provider_missions: [],
    });
    return;
  }

  const response = await apiFetch(`/api/profile/${telegramUser.id}`);
  const data = await response.json();
  availableServices = data.available_services || availableServices;
  window.nexisProfile = data;
  setText("profile-status", "Donnees connectees a Nexis Hub.");
  renderRole(currentRole(), data);
}

loadProfile().catch(() => {
  setText("profile-status", "Impossible de charger les donnees pour le moment.");
});

document.getElementById("save-services").addEventListener("click", saveServices);
document.getElementById("send-missing-service").addEventListener("click", sendMissingService);
document.getElementById("toggle-provider-status").addEventListener("click", toggleProviderStatus);
document.getElementById("register-provider").addEventListener("click", registerProvider);
document.getElementById("missions-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-mission-action]");
  if (!button) return;
  updateMissionAction(button.dataset.missionAction, Number(button.dataset.missionId));
});
