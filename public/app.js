(() => {
"use strict";
/* ========================================================================= utilitaires */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => Number(n).toLocaleString("fr-FR");
const money = l => "$" + fmt(l.price) + (l.deal === "location" ? " / mois" : "");
const short = l => l.price >= 1000 && l.deal === "vente" ? "$" + (l.price >= 1e6 ? (l.price / 1e6).toFixed(1).replace(".0", "") + " M" : Math.round(l.price / 1000) + " k") : "$" + fmt(l.price);
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : "";
const when = ts => new Date(ts * 1000).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const hour = ts => new Date(ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const safeUrl = u => (typeof u === "string" && /^(\/(media|uploads)\/|https:\/\/[a-z0-9.-]+\.(public\.blob\.vercel-storage\.com|googleusercontent\.com)\/)/i.test(u)) ? u : "";
const initials = n => esc((n || "?").trim()[0]?.toUpperCase() || "?");
const avatar = (url, name, cls = "") => safeUrl(url) ? `<img class="avatar ${cls}" src="${esc(safeUrl(url))}" alt="">` : `<span class="avatar on ${cls}">${initials(name)}</span>`;

const I = {
  search: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  heart: '<svg viewBox="0 0 32 32"><path d="M16 28C7 22 2 16.5 2 11a7 7 0 0 1 14-2 7 7 0 0 1 14 2c0 5.5-5 11-14 17z"/></svg>',
  star: '<svg class="star" viewBox="0 0 24 24"><path d="m12 2 3 7 7.5.6-5.7 5 1.8 7.4L12 18l-6.6 4 1.8-7.4-5.7-5L9 9z"/></svg>',
  check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 5 5L20 6"/></svg>',
  filter: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg>',
  burger: '<svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
  chat: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z"/></svg>',
  map: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/></svg>',
  list: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  flag: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22V4M4 4h12l-2 4 2 4H4"/></svg>',
};
const CATS = [
  ["", "Tout", '<path d="M4 11 12 4l8 7M6 10v10h12V10"/>'],
  ["maison", "Maisons", '<path d="M3 12 12 4l9 8M5 10.5V20h5v-5h4v5h5v-9.5"/>'],
  ["appartement", "Appartements", '<path d="M5 21V4h14v17M9 8h2M13 8h2M9 12h2M13 12h2M10 21v-4h4v4"/>'],
  ["villa", "Villas", '<path d="M2 21h20M4 21V10l8-6 8 6v11M9 21v-6h6v6M8 11h2M14 11h2"/>'],
  ["studio", "Studios", '<path d="M4 8h16v12H4zM4 8l8-5 8 5M10 20v-6h4v6"/>'],
  ["terrain", "Terrains", '<path d="M3 20h18M5 20l5-9 3 5 2-3 4 7M16 6a2 2 0 1 0 .1 0"/>'],
];
const TABS = [
  ["#/", "Explorer", '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>'],
  ["#/favorites", "Favoris", '<path d="M12 21C5 16 2 12 2 8.5a5 5 0 0 1 10-1.5 5 5 0 0 1 10 1.5C22 12 19 16 12 21z"/>'],
  ["#/messages", "Messages", '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z"/>'],
  ["#/profile", "Profil", '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'],
];
const PLACE_LEVELS = [["province_id", "Province"], ["city_id", "Ville"], ["commune_id", "Commune"], ["quartier_id", "Quartier"], ["avenue_id", "Avenue"]];
const FILTER_KEYS = ["province_id", "city_id", "commune_id", "quartier_id", "avenue_id", "deal", "ptype", "max_price", "min_price", "bedrooms", "furnished", "sort", "q", "bbox"];
const DRC = { center: [-2.9, 23.6], zoom: 5 };

const state = { user: null, meta: null, auth: {}, f: {}, favs: new Set(), placeName: "" };

async function api(path, opts = {}) {
  const o = { method: "GET", headers: { "X-Ndaku": "1" }, ...opts };
  if (opts.json) { o.method = o.method === "GET" ? "POST" : o.method; o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opts.json); }
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.error || "Erreur réseau, réessayez."), { status: r.status, data });
  return data;
}
let tt;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("show"), 3400); }
const errPage = msg => `<div class="wrap empty"><h3>${esc(msg)}</h3><p><a class="btn" href="#/">Retour à l'accueil</a></p></div>`;

/* ------------------------------------------------------------------ skeleton screens */
const SK = {
  cards: n => `<div class="grid">${'<div><div class="sk ph"></div><div class="sk l"></div><div class="sk l s"></div><div class="sk l xs"></div></div>'.repeat(n)}</div>`,
  detail: () => `<div class="wrap"><div class="sk h"></div><div class="sk l s"></div><div class="sk gal" style="margin-top:16px"></div><div class="dt-body"><div>${'<div class="sk l"></div>'.repeat(6)}</div><div class="sk box"></div></div></div>`,
  rows: n => '<div class="sk-row"><div class="sk av"></div><div><div class="sk l s"></div><div class="sk l xs"></div></div></div>'.repeat(n),
  chat: () => `<div class="msgs">${[60, 40, 70, 35].map((w, i) => `<div class="sk" style="height:42px;width:${w}%;border-radius:18px;flex:none;align-self:${i % 2 ? "flex-end" : "flex-start"}"></div>`).join("")}</div>`,
};

/* ------------------------------------------------------------------------- modal */
function modal(title, html, cls = "") {
  closeModal();
  const ov = document.createElement("div");
  ov.className = "ov";
  ov.innerHTML = `<div class="mdl ${cls}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header><button class="x" data-act="close" aria-label="Fermer">✕</button>${esc(title)}</header><div class="bd">${html}</div></div>`;
  ov.addEventListener("mousedown", e => { if (e.target === ov) closeModal(); });
  $("#modal-root").append(ov);
  const first = ov.querySelector("input:not([type=hidden]):not([type=file]):not(.sr),select,textarea"); first && first.focus();
  return ov;
}
const closeModal = () => { $("#modal-root").innerHTML = ""; };
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeModal(); closePop(); } });

/* ============================================================ référentiel géographique */
const placeCache = new Map();
function children(parentId) {
  const k = parentId || "root";
  if (!placeCache.has(k)) placeCache.set(k, api("/api/places" + (parentId ? `?parent_id=${parentId}` : "")).then(r => r.items).catch(e => { placeCache.delete(k); throw e; }));
  return placeCache.get(k);
}
async function myPending(parentId) {
  if (state.user?.role !== "host" || !parentId) return [];
  return api(`/api/places/mine?parent_id=${parentId}`).then(r => r.items.map(p => ({ ...p, pending: true }))).catch(() => []);
}
const KINDS = ["province", "city", "commune", "quartier", "avenue"];
/**
 * Listes en cascade province → ville → commune → quartier → avenue.
 * mode "filter" : niveaux facultatifs. mode "host" : jusqu'à l'avenue, propositions de quartier/avenue possibles.
 */
function placePicker(box, { mode = "filter", value = {}, onChange = () => {} } = {}) {
  const host = mode === "host", v = {}, names = {}, proposed = { 3: [], 4: [] };
  PLACE_LEVELS.forEach(([k]) => { v[k] = value[k] ? +value[k] : null; });
  box.innerHTML = `<div class="place-steps">${PLACE_LEVELS.map(([k, label], i) => `<div class="field"><label for="pp-${k}">${label}${host && i !== 3 ? " *" : ""}</label>
      <select id="pp-${k}" data-k="${k}" disabled><option value="">—</option></select>
      ${host && i >= 3 ? `<button type="button" class="linkish add" data-suggest="${i}" hidden>${i === 3 ? "Mon quartier n'est pas listé" : "Mon avenue n'est pas listée"}</button>` : ""}</div>`).join("")}</div>`;
  const sel = i => box.querySelector(`select[data-k="${PLACE_LEVELS[i][0]}"]`);
  const sugg = i => box.querySelector(`[data-suggest="${i}"]`);
  const parentOf = i => i === 0 ? "root" : i === 4 ? (v.quartier_id || v.commune_id) : v[PLACE_LEVELS[i - 1][0]];
  async function options(i) {
    const parent = parentOf(i);
    if (!parent) return null;
    const pid = parent === "root" ? null : parent;
    let list = (await children(pid)).filter(p => p.kind === KINDS[i]);
    if (i === 4 && v.quartier_id) list = list.concat((await children(v.commune_id)).filter(p => p.kind === "avenue"));
    if (host && i >= 3) {
      const seen = new Set(list.map(p => p.id));
      list = list.concat(proposed[i].filter(p => p.parent === pid && !seen.has(p.id)));
      list = list.concat((await myPending(pid)).filter(p => p.kind === KINDS[i] && !list.some(x => x.id === p.id)));
      if (i === 4 && v.quartier_id) list = list.concat((await myPending(v.commune_id)).filter(p => p.kind === "avenue"));
    }
    return list;
  }
  async function load(i) {
    const s = sel(i), k = PLACE_LEVELS[i][0], all = mode === "filter" ? "Toutes" : "Choisir…";
    const list = await options(i);
    if (sugg(i)) sugg(i).hidden = !list;
    if (!list) { s.innerHTML = `<option value="">${all}</option>`; s.disabled = true; v[k] = null; names[k] = ""; return; }
    s.innerHTML = `<option value="">${list.length ? all : i === 3 ? "Aucun quartier connu" : i === 4 ? "Aucune avenue connue" : "—"}</option>`
      + list.map(p => `<option value="${p.id}">${esc(p.name)}${p.pending ? " (en attente de validation)" : ""}</option>`).join("");
    s.disabled = !list.length;
    const cur = list.find(p => p.id === v[k]);
    v[k] = cur ? cur.id : null; names[k] = cur ? cur.name : ""; if (cur) s.value = cur.id;
  }
  const value_ = () => {
    const deepest = [...PLACE_LEVELS].reverse().find(([k]) => v[k]);
    return { ...v, name: deepest ? names[deepest[0]] : "", names: { ...names } };
  };
  async function changed(i, val) {
    const k = PLACE_LEVELS[i][0];
    v[k] = val ? +val : null;
    names[k] = val ? sel(i).selectedOptions[0].textContent.replace(" (en attente de validation)", "") : "";
    for (let j = i + 1; j < PLACE_LEVELS.length; j++) { v[PLACE_LEVELS[j][0]] = null; await load(j); }
    onChange(value_());
  }
  box.addEventListener("change", e => { const i = PLACE_LEVELS.findIndex(([k]) => k === e.target.dataset.k); if (i >= 0) changed(i, e.target.value); });
  box.addEventListener("click", async e => {
    const b = e.target.closest("[data-suggest]"); if (!b) return;
    const i = +b.dataset.suggest, kind = KINDS[i];
    const parent = i === 3 ? v.commune_id : (v.quartier_id || v.commune_id);
    if (!parent) return toast("Choisissez d'abord la commune.");
    const name = prompt(`Nom ${i === 3 ? "du quartier" : "de l'avenue"} (il sera vérifié par la modération) :`);
    if (!name) return;
    try {
      const p = await api("/api/places", { json: { parent_id: parent, kind, name } });
      if (p.status !== "active") proposed[i].push({ ...p, parent, pending: true });
      placeCache.delete(parent);
      v[PLACE_LEVELS[i][0]] = p.id; await load(i);
      for (let j = i + 1; j < PLACE_LEVELS.length; j++) await load(j);
      names[PLACE_LEVELS[i][0]] = p.name; onChange(value_());
      toast(p.status === "pending" ? "Proposition enregistrée : utilisable pour votre annonce, visible par tous après validation." : "Ce lieu existe déjà : il a été sélectionné.");
    } catch (x) { toast(x.message); }
  });
  (async () => { for (let i = 0; i < PLACE_LEVELS.length; i++) await load(i); onChange(value_(), true); })().catch(e => toast(e.message));
  return { value: value_ };
}

/* ============================================================================ en-tête */
function renderHeader() {
  const f = state.f, u = state.user;
  $("#hdr").innerHTML = `
    <a class="logo" href="#/" aria-label="Ndaku, accueil"><img src="/logo.svg" alt=""><span>ndaku</span></a>
    <div class="search" role="search">
      <button class="seg" data-act="where"><b>Où</b><span>${esc(state.placeName || "Toute la RDC")}</span></button>
      <button class="seg opt" data-act="filters"><b>Offre</b><span>${f.deal === "location" ? "Louer" : f.deal === "vente" ? "Acheter" : "Louer ou acheter"}</span></button>
      <button class="seg opt" data-act="filters"><b>Budget</b><span>${f.max_price ? "≤ $" + fmt(f.max_price) : "Illimité"}</span></button>
      <button class="go" data-act="where" aria-label="Rechercher">${I.search}</button>
    </div>
    <div class="nav">
      ${!u || u.role === "host" ? `<a class="link host-cta" href="${u ? "#/new" : "#/host"}" data-need="host">Mettre ma maison sur Ndaku</a>` : ""}
      ${u ? `<a class="icon-btn msg-btn" href="#/messages" aria-label="Messages">${I.chat}${u.unread ? `<span class="dot">${u.unread}</span>` : ""}</a>` : ""}
      <button class="menu-btn" id="menuBtn" aria-haspopup="true" aria-label="Menu du compte">${I.burger}${u ? avatar(u.avatar, u.name) : '<span class="avatar">👤</span>'}</button>
    </div>`;
  $("#menuBtn").onclick = e => { e.stopPropagation(); togglePop(); };
  renderTabbar();
}
function renderTabbar() {
  const path = parse().path, u = state.user;
  $("#tabbar").innerHTML = TABS.map(([h, l, svg]) => {
    const on = h === "#/" ? path === "/" : path.startsWith(h.slice(1));
    return `<a href="${h}" class="${on ? "on" : ""}"><svg viewBox="0 0 24 24">${svg}</svg>${l}${h === "#/messages" && u?.unread ? `<span class="dot">${u.unread}</span>` : ""}</a>`;
  }).join("");
}
function closePop() { const p = $(".pop"); p && p.remove(); }
function togglePop() {
  if ($(".pop")) return closePop();
  const u = state.user, p = document.createElement("div");
  p.className = "pop";
  p.innerHTML = u ? `<div class="who">${esc(u.name)} · ${u.role === "host" ? "Hôte" : u.role === "admin" ? "Admin" : "Client"}${u.verified ? " · ✓ vérifié" : ""}</div>
      <a href="#/messages">Messages${u.unread ? ` (${u.unread})` : ""}</a><a href="#/favorites">Favoris</a>
      ${u.role === "host" ? `<a href="#/host">Mes annonces</a><a href="#/new">Publier une annonce</a>` : ""}
      ${u.role === "admin" ? `<a href="#/admin">Modération</a>` : ""}<a href="#/profile">Mon profil</a><hr><button data-act="logout">Se déconnecter</button>`
    : `<button data-act="login">Se connecter</button><button data-act="signup">S'inscrire</button><hr><button data-act="signup-host">Devenir hôte</button>`;
  document.body.append(p);
}
document.addEventListener("click", e => { if (!e.target.closest(".pop,#menuBtn")) closePop(); });

/* ===================================================================== authentification */
const loadScript = src => new Promise((ok, ko) => {
  if (document.querySelector(`script[src="${src}"]`)) return ok();
  const s = document.createElement("script"); s.src = src; s.async = true; s.onload = ok; s.onerror = ko; document.head.append(s);
});
async function afterLogin(user, msg) {
  state.user = user; closeModal(); await loadFavs(); renderHeader(); route();
  toast(msg || `Bienvenue ${user.name} !`);
  if (!user.avatar) setTimeout(() => avatarModal(true), 500);
}
async function oauthDone(provider, payload, role) {
  try { const r = await api(`/api/auth/oauth/${provider}`, { json: { ...payload, role } }); await afterLogin(r.user); return true; }
  catch (err) { const e = $("#authErr"); if (e) e.textContent = err.message; else toast(err.message); return false; }
}
async function mountSocial(box, getRole) {
  const c = state.auth, gDiv = box.querySelector("#g-btn"), aBtn = box.querySelector("#apple-btn");
  if (!c.google_client_id && !c.apple_client_id) { box.remove(); return; }
  const mountGoogle = async () => {
    try {
      const { nonce } = await api("/api/auth/nonce");
      await loadScript("https://accounts.google.com/gsi/client");
      gDiv.innerHTML = "";
      google.accounts.id.initialize({ client_id: c.google_client_id, nonce, ux_mode: "popup", use_fedcm_for_button: true,
        callback: async r => { if (!await oauthDone("google", { credential: r.credential, nonce }, getRole()) && box.isConnected) mountGoogle(); } });
      google.accounts.id.renderButton(gDiv, { theme: "outline", size: "large", shape: "pill", text: "continue_with", width: Math.min(gDiv.clientWidth || 360, 400), locale: "fr" });
    } catch { gDiv.textContent = "Connexion Google indisponible pour le moment."; }
  };
  if (c.google_client_id) mountGoogle(); else gDiv.remove();
  if (c.apple_client_id) {
    aBtn.onclick = async () => {
      try {
        const { nonce } = await api("/api/auth/nonce");
        await loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/fr_FR/appleid.auth.js");
        AppleID.auth.init({ clientId: c.apple_client_id, scope: "name email", redirectURI: c.apple_redirect_uri, usePopup: true, nonce });
        const r = await AppleID.auth.signIn();
        const n = r.user?.name; const name = n ? `${n.firstName || ""} ${n.lastName || ""}`.trim() : "";
        oauthDone("apple", { id_token: r.authorization.id_token, nonce, name }, getRole());
      } catch (err) { if (err?.error !== "popup_closed_by_user") toast("Connexion iCloud annulée ou indisponible."); }
    };
  } else aBtn.remove();
}
const avatarField = (id = "a-photo") => `<div class="av-pick"><label for="${id}" class="avatar" id="${id}-pv" title="Choisir une photo">📷</label>
    <div><b>Photo de profil *</b><br><span class="hint">Un vrai visage rassure : obligatoire pour publier, écrire ou noter.</span><br>
    <input id="${id}" type="file" accept="image/jpeg,image/png,image/webp" class="sr"><label for="${id}" class="linkish">Choisir une photo</label></div></div>`;
function bindAvatarField(root, id = "a-photo") {
  const input = root.querySelector("#" + id), pv = root.querySelector(`#${id}-pv`);
  input.onchange = () => { const f = input.files[0]; if (f) pv.innerHTML = `<img src="${URL.createObjectURL(f)}" alt="">`; };
  return () => input.files[0];
}
async function uploadAvatar(file) {
  const fd = new FormData(); fd.append("image", await shrink(file, 800));
  const r = await api("/api/auth/me/avatar", { method: "POST", body: fd });
  if (state.user) state.user.avatar = r.avatar;
  return r.avatar;
}
function authModal(mode = "login", role = "client") {
  const reg = mode === "signup";
  const m = modal(reg ? "Inscription" : "Connexion", `
    <div class="tabs"><button class="${reg ? "" : "on"}" data-act="login">Connexion</button><button class="${reg ? "on" : ""}" data-act="signup">Inscription</button></div>
    <h2>Bienvenue sur Ndaku</h2>
    ${reg ? `<div class="seg-pick"><label><input type="radio" name="role" value="client" ${role === "client" ? "checked" : ""}><b>Client</b><span>Je cherche à louer ou acheter</span></label>
      <label><input type="radio" name="role" value="host" ${role === "host" ? "checked" : ""}><b>Hôte</b><span>Je propose un bien</span></label></div>` : ""}
    <div class="social" id="social"><div id="g-btn" class="g-btn"></div>
      <button type="button" class="btn apple block" id="apple-btn"><svg width="16" height="18" viewBox="0 0 17 20" fill="currentColor" aria-hidden="true"><path d="M14.1 10.6c0-2.6 2.1-3.8 2.2-3.9-1.2-1.8-3.1-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-.9-3.4-.9C3.5 4.7 1.8 5.8.9 7.4c-1.9 3.3-.5 8.1 1.3 10.7.9 1.3 2 2.7 3.3 2.7 1.3-.1 1.8-.9 3.4-.9s2 .9 3.4.8c1.4 0 2.3-1.3 3.2-2.6 1-1.5 1.4-2.9 1.4-3-.1 0-2.8-1-2.8-4.1zM11.6 3c.7-.9 1.2-2 1.1-3.2-1 0-2.3.7-3 1.6-.7.7-1.2 2-1.1 3.1 1.1.1 2.3-.6 3-1.5z"/></svg> Continuer avec Apple (iCloud)</button>
      <div class="or"><span>ou avec votre e-mail</span></div></div>
    <form id="authForm" novalidate>
      ${reg ? avatarField() + `<div class="field"><label for="a-name">Nom complet *</label><input id="a-name" name="name" autocomplete="name" required maxlength="80"></div>` : ""}
      <div class="field"><label for="a-mail">E-mail *</label><input id="a-mail" name="email" type="email" autocomplete="email" required maxlength="120"></div>
      ${reg ? `<div class="field"><label for="a-tel">Téléphone (partagé uniquement si vous le décidez dans une discussion)</label><input id="a-tel" name="phone" type="tel" autocomplete="tel" maxlength="30" placeholder="+243 …"></div>` : ""}
      <div class="field"><label for="a-pw">Mot de passe *</label><input id="a-pw" name="password" type="password" autocomplete="${reg ? "new" : "current"}-password" required maxlength="128">${reg ? '<span class="hint">10 caractères min., majuscule, minuscule et chiffre.</span>' : '<button type="button" class="linkish" data-act="forgot">Mot de passe oublié ?</button>'}</div>
      <div class="err" id="authErr" role="alert"></div>
      <button class="btn block">${reg ? "Créer mon compte" : "Continuer"}</button>
    </form>`);
  const getRole = () => m.querySelector('input[name="role"]:checked')?.value || "client";
  const getPhoto = reg ? bindAvatarField(m) : null;
  mountSocial(m.querySelector("#social"), getRole);
  m.querySelector("#authForm").onsubmit = async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    if (reg) { d.role = getRole(); if (!getPhoto()) { $("#authErr").textContent = "Ajoutez votre photo de profil."; return; } }
    const btn = e.target.querySelector(".btn"); btn.disabled = true;
    try {
      const r = await api(reg ? "/api/auth/register" : "/api/auth/login", { json: d });
      if (reg) { try { r.user.avatar = await uploadAvatar(getPhoto()); } catch (x) { toast("Compte créé, mais la photo n'a pas pu être envoyée : " + x.message); } }
      await afterLogin(r.user, reg && !r.user.email_verified && state.auth.email_verification ? "Compte créé ! Confirmez votre e-mail via le lien reçu." : null);
    } catch (err) { $("#authErr").textContent = err.message; btn.disabled = false; }
  };
}
function avatarModal(required) {
  const m = modal("Photo de profil", `<form id="avf"><p>${required ? "Dernière étape : ajoutez une photo de profil. Elle est obligatoire pour publier, contacter un hôte ou laisser un avis." : "Choisissez une nouvelle photo de profil."}</p>
    ${avatarField("av2")}<div class="err" id="avErr" role="alert"></div><div class="row-actions"><button class="btn">Enregistrer</button>${required ? '<button type="button" class="btn soft" data-act="close">Plus tard</button>' : ""}</div></form>`);
  const getPhoto = bindAvatarField(m, "av2");
  m.querySelector("#avf").onsubmit = async e => {
    e.preventDefault(); if (!getPhoto()) { $("#avErr").textContent = "Choisissez une photo."; return; }
    const b = e.target.querySelector(".btn"); b.disabled = true;
    try { await uploadAvatar(getPhoto()); closeModal(); renderHeader(); route(); toast("Photo de profil enregistrée ✓"); }
    catch (x) { $("#avErr").textContent = x.message; b.disabled = false; }
  };
}
const needLogin = (role = "client") => { if (!state.user) { authModal("signup", role); return true; } return false; };
const needAvatar = () => { if (state.user && !state.user.avatar) { avatarModal(true); return true; } return false; };
function forgotModal() {
  const m = modal("Mot de passe oublié", `<form id="fg"><p>Saisissez votre e-mail : si un compte existe, vous recevrez un lien de réinitialisation.</p>
    <div class="field"><label for="f-mail">E-mail</label><input id="f-mail" name="email" type="email" required></div><button class="btn block">Envoyer le lien</button></form>`);
  m.querySelector("#fg").onsubmit = async e => { e.preventDefault(); try { const r = await api("/api/auth/password/forgot", { json: Object.fromEntries(new FormData(e.target)) }); closeModal(); toast(r.message); } catch (x) { toast(x.message); } };
}
async function verifyPage(params) {
  try { await api("/api/auth/verify-email", { json: { token: params.token } }); state.user = (await api("/api/auth/me")).user; renderHeader();
    $("#view").innerHTML = `<div class="wrap empty"><h3>Adresse e-mail confirmée ✓</h3><a class="btn" href="#/">Continuer</a></div>`; }
  catch (x) { $("#view").innerHTML = errPage(x.message); }
}
function resetPage(params) {
  $("#view").innerHTML = `<div class="wrap page"><form class="form" id="rs" style="max-width:420px"><h1>Nouveau mot de passe</h1>
    <div class="field"><label for="r-pw">Mot de passe</label><input id="r-pw" name="password" type="password" autocomplete="new-password" required maxlength="128"><span class="hint">10 caractères min., majuscule, minuscule et chiffre.</span></div>
    <div class="err" id="rsErr" role="alert"></div><button class="btn block">Enregistrer</button></form></div>`;
  $("#rs").onsubmit = async e => { e.preventDefault(); try { await api("/api/auth/password/reset", { json: { token: params.token, password: e.target.password.value } }); toast("Mot de passe modifié. Connectez-vous."); go("#/"); authModal("login"); } catch (x) { $("#rsErr").textContent = x.message; } };
}

/* ============================================================================= routage */
const qs = f => { const p = new URLSearchParams(); for (const k of FILTER_KEYS) if (f[k]) p.set(k, f[k]); const s = p.toString(); return s ? "?" + s : ""; };
const go = h => { if (location.hash === h) route(); else location.hash = h; };
function parse() { const [path, q] = (location.hash.slice(1) || "/").split("?"); return { path, params: Object.fromEntries(new URLSearchParams(q || "")) }; }
let cleanup = [];
async function route() {
  closePop(); cleanup.forEach(fn => { try { fn(); } catch { /* ignore */ } }); cleanup = [];
  const { path, params } = parse(), view = $("#view");
  if (!path.startsWith("/messages")) window.scrollTo(0, 0);
  $("#cats").style.display = path === "/" ? "" : "none";
  $(".ftr").style.display = path.startsWith("/messages") || path === "/" ? "none" : "";
  try {
    if (path === "/") {
      state.f = Object.fromEntries(FILTER_KEYS.filter(k => params[k]).map(k => [k, params[k]]));
      if (!PLACE_LEVELS.some(([k]) => state.f[k])) state.placeName = "";
      renderHeader(); renderCats(); return await home();
    }
    renderHeader();
    let m;
    if ((m = path.match(/^\/listing\/(\d+)$/))) return await detail(+m[1]);
    if ((m = path.match(/^\/messages(?:\/(\d+))?$/))) return await messages(m[1] ? +m[1] : null);
    if (path === "/host") return await dashboard();
    if (path === "/new") return await newListing();
    if (path === "/favorites") return await favorites();
    if (path === "/profile") return await profile();
    if (path === "/admin") return await admin(params.tab || "queue");
    if (path === "/verify") return await verifyPage(params);
    if (path === "/reset") return resetPage(params);
    view.innerHTML = errPage("Page introuvable");
  } catch (e) {
    if (e.status === 401) view.innerHTML = `<div class="wrap empty"><h3>Connexion requise</h3><p>Connectez-vous pour continuer.</p><button class="btn" data-act="login">Se connecter</button></div>`;
    else view.innerHTML = errPage(e.message);
  }
}
async function loadFavs() { state.favs = new Set(state.user ? (await api("/api/favorites/ids").catch(() => ({ ids: [] }))).ids : []); }

/* ===================================================================== accueil : liste + carte */
function renderCats() {
  $("#cats").innerHTML = CATS.map(([v, l, svg]) => `<button class="cat ${(state.f.ptype || "") === v ? "on" : ""}" data-cat="${v}"><svg viewBox="0 0 24 24">${svg}</svg>${l}</button>`).join("")
    + `<button class="chip-btn first" data-act="where">📍 ${esc(state.placeName || "Lieu")}</button><button class="chip-btn" data-act="filters">${I.filter} Filtres</button>`;
}
function cardHtml(l, top) {
  const loc = [l.quartier, l.commune, l.city].filter(Boolean).slice(0, 2).join(", ");
  const fav = state.favs.has(l.id);
  return `<a class="card" href="#/listing/${l.id}" data-id="${l.id}">
    <div class="ph">${safeUrl(l.cover) ? `<img loading="lazy" decoding="async" src="${esc(safeUrl(l.cover))}" alt="${esc(l.title)}">` : ""}
      <button class="heart ${fav ? "on" : ""}" data-fav="${l.id}" aria-label="${fav ? "Retirer des" : "Ajouter aux"} favoris" aria-pressed="${fav}">${I.heart}</button>
      ${l.is_demo ? '<span class="badge demo">Démo</span>' : top ? '<span class="badge">Coup de cœur</span>' : `<span class="badge deal">${l.deal === "location" ? "À louer" : "À vendre"}</span>`}</div>
    <div class="row"><b>${esc(loc)}</b><span class="rt">${l.rating ? I.star + Number(l.rating).toFixed(1) : "Nouveau"}</span></div>
    <div class="m">${esc(l.title)}</div>
    <div class="m">${l.ptype === "terrain" ? "Terrain" : cap(l.ptype) + " · " + l.bedrooms + " ch."} · ${l.surface} m²</div>
    <div class="price"><b>${money(l)}</b></div></a>`;
}
const pinHtml = p => `<div class="price-pin" data-pin="${p.id}">${esc(short(p))}</div>`;
function makeMap(el, center = DRC.center, zoom = DRC.zoom) {
  const t = state.meta.tiles;
  const map = L.map(el, { zoomControl: true, scrollWheelZoom: true }).setView(center, zoom);
  L.tileLayer(t.url, { attribution: t.attribution, maxZoom: 19 }).addTo(map);
  cleanup.push(() => map.remove());
  return map;
}
async function home() {
  const f = state.f, view = $("#view");
  const filtered = FILTER_KEYS.some(k => f[k] && k !== "sort");
  view.innerHTML = `<div class="split" id="split">
      <section class="list"><h2 class="sec-title" id="ht">${filtered ? "Recherche" : "Les meilleures maisons du moment"}</h2>
        <p class="sec-sub" id="hs">${filtered ? "&nbsp;" : "Classées par avis vérifiés, favoris et fiabilité de l'hôte."}</p>
        <div id="grid">${SK.cards(8)}</div><div class="more" id="more"></div></section>
      <aside class="mapcol" aria-label="Carte des annonces"><div id="map"></div><button class="map-search" id="mapSearch">Rechercher dans cette zone</button></aside>
    </div><button class="map-toggle" id="mapToggle">${I.map} Carte</button>`;
  const grid = $("#grid"), more = $("#more"), split = $("#split");
  let offset = 0, total = 0, loading = false;
  const listQs = extra => { const s = qs(f); return "/api/listings" + (s || "?") + (s ? "&" : "") + extra; };
  async function page(first) {
    if (loading) return; loading = true;
    if (!first) more.innerHTML = SK.cards(4);
    try {
      const r = await api(listQs(`limit=24&offset=${offset}`));
      total = r.total;
      const html = r.items.map((l, i) => cardHtml(l, !filtered && offset + i < 3 && l.rating >= 4)).join("");
      if (first) grid.innerHTML = r.items.length ? `<div class="grid">${html}</div>` : `<div class="empty"><h3>Aucun résultat</h3><p>Élargissez la zone ou retirez des filtres.</p><a class="btn ghost" href="#/">Réinitialiser</a></div>`;
      else grid.querySelector(".grid").insertAdjacentHTML("beforeend", html);
      offset += r.items.length;
      if (filtered) { $("#ht").textContent = `${fmt(total)} bien${total > 1 ? "s" : ""}${state.placeName ? " à " + state.placeName : ""}`; $("#hs").textContent = f.bbox ? "Dans la zone affichée sur la carte." : ""; }
      more.innerHTML = offset < total ? `<button class="btn ghost" id="moreBtn">Afficher plus</button>` : "";
    } catch (e) { grid.innerHTML = errPage(e.message); } finally { loading = false; }
  }
  await page(true);
  more.addEventListener("click", e => { if (e.target.id === "moreBtn") page(false); });
  const io = new IntersectionObserver(es => { if (es[0].isIntersecting && offset < total) page(false); }, { rootMargin: "600px" });
  io.observe(more); cleanup.push(() => io.disconnect());

  // ------------------------------------------------------------------ carte
  const map = makeMap($("#map"));
  const cluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 48,
    iconCreateFunction: c => L.divIcon({ html: `<div class="cluster" style="width:40px;height:40px">${c.getChildCount()}</div>`, className: "pin-wrap", iconSize: [40, 40] }) });
  map.addLayer(cluster);
  let fitted = false, armed = false;
  const arm = () => setTimeout(() => { armed = true; }, 900);
  async function loadPins() {
    const r = await api("/api/listings/map" + qs(f));
    cluster.clearLayers();
    const pts = r.items.map(p => {
      const mk = L.marker([p.lat, p.lng], { icon: L.divIcon({ className: "pin-wrap", html: pinHtml(p), iconSize: null }), title: p.title });
      mk.bindPopup(`<a class="map-card" href="#/listing/${p.id}">${safeUrl(p.cover) ? `<img src="${esc(safeUrl(p.cover))}" alt="">` : ""}<div><b>${esc(p.title)}</b><br>${esc(money(p))}</div></a>`, { closeButton: false });
      return mk;
    });
    cluster.addLayers(pts);
    if (!f.bbox && pts.length && !fitted) { map.fitBounds(L.featureGroup(pts).getBounds().pad(0.2), { maxZoom: 14 }); fitted = true; }
    if (f.bbox && !fitted) { const [s_, w_, n_, e_] = f.bbox.split(",").map(Number); map.fitBounds([[s_, w_], [n_, e_]]); fitted = true; }
    arm();
  }
  loadPins().catch(() => {});
  const ms = $("#mapSearch");
  map.on("moveend", () => { if (armed) ms.classList.add("show"); });
  ms.onclick = () => { const b = map.getBounds(); go("#/" + qs({ ...f, bbox: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map(x => x.toFixed(4)).join(",") })); };
  // survol carte ↔ liste
  grid.addEventListener("mouseover", e => { const c = e.target.closest(".card"); document.querySelectorAll(".price-pin.on").forEach(p => p.classList.remove("on")); if (c) document.querySelector(`[data-pin="${c.dataset.id}"]`)?.classList.add("on"); });
  const tg = $("#mapToggle");
  tg.onclick = () => { const open = split.classList.toggle("mapopen"); tg.innerHTML = open ? `${I.list} Liste` : `${I.map} Carte`; armed = false; setTimeout(() => { map.invalidateSize(); arm(); }, 50); };
}
function whereModal() {
  const m = modal("Où cherchez-vous ?", `<p class="hint">Province, ville, commune, quartier puis avenue : précisez autant que vous voulez.</p><div id="wp"></div>
    <div class="row-actions" style="margin-top:8px"><button type="button" class="btn ghost" data-act="where-reset">Toute la RDC</button><button class="btn" id="wgo">Rechercher</button></div>`, "wide");
  let val = {};
  placePicker(m.querySelector("#wp"), { value: state.f, onChange: v => { val = v; } });
  m.querySelector("#wgo").onclick = () => {
    const f = { ...state.f, bbox: "" };
    PLACE_LEVELS.forEach(([k]) => { f[k] = val[k] || ""; });
    state.placeName = val.name || ""; closeModal(); go("#/" + qs(f));
  };
}
function filtersModal() {
  const f = state.f;
  const m = modal("Filtres", `<form id="ff">
    <div class="seg-pick"><label><input type="radio" name="deal" value="location" ${f.deal === "location" ? "checked" : ""}><b>Louer</b><span>Loyer mensuel</span></label><label><input type="radio" name="deal" value="vente" ${f.deal === "vente" ? "checked" : ""}><b>Acheter</b><span>Prix de vente</span></label></div>
    <div class="field"><label>Trier par</label><select name="sort"><option value="">Meilleurs d'abord</option>
      ${[["new", "Plus récents"], ["price_asc", "Prix croissant"], ["price_desc", "Prix décroissant"]].map(([v, l]) => `<option value="${v}" ${f.sort === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
    <div class="cols"><div class="field"><label>Prix min ($)</label><input name="min_price" type="number" min="0" inputmode="numeric" value="${esc(f.min_price || "")}"></div>
    <div class="field"><label>Prix max ($)</label><input name="max_price" type="number" min="0" inputmode="numeric" value="${esc(f.max_price || "")}"></div></div>
    <div class="field"><label>Chambres (minimum)</label><select name="bedrooms"><option value="">Indifférent</option>${[1, 2, 3, 4, 5].map(n => `<option ${+f.bedrooms === n ? "selected" : ""}>${n}</option>`).join("")}</select></div>
    <div class="field"><label>Mot-clé</label><input name="q" value="${esc(f.q || "")}" maxlength="60" placeholder="piscine, jardin, nom d'avenue…"></div>
    <label class="chk" style="margin-bottom:20px"><input type="checkbox" name="furnished" value="1" ${f.furnished ? "checked" : ""}> Meublé uniquement</label>
    <div class="row-actions"><button type="button" class="btn ghost" data-act="reset">Tout effacer</button><button class="btn">Afficher les biens</button></div></form>`);
  m.querySelector("#ff").onsubmit = e => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.target)); closeModal(); go("#/" + qs({ ...state.f, deal: "", sort: "", min_price: "", max_price: "", bedrooms: "", q: "", furnished: "", ...d })); };
}

/* =========================================================================== fiche annonce */
async function detail(id) {
  const view = $("#view");
  view.innerHTML = SK.detail();
  const l = await api("/api/listings/" + id), u = state.user;
  const imgs = l.images.map(safeUrl).filter(Boolean), n = Math.min(imgs.length, 5);
  const isOwner = u && u.id === l.host.id, isAdmin = u?.role === "admin";
  const fav = state.favs.has(l.id);
  view.innerHTML = `<div class="wrap dt">
    ${l.status !== "active" ? `<div class="notice warn" style="margin-top:16px">Statut : <b>${esc(l.status)}</b> — visible uniquement par vous${l.status === "pending" ? " (vérification en cours par la modération)" : ""}.</div>` : ""}
    ${l.risk_reasons?.length ? `<div class="risk"><b>Signaux anti-fraude (score ${l.risk_score})</b><ul>${l.risk_reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
    <h1>${esc(l.title)}</h1>
    <div class="meta"><span class="rt">${l.rating ? I.star + " <b style='color:var(--ink)'>" + Number(l.rating).toFixed(1) + "</b> · " + l.reviews_count + " avis" : "Pas encore d'avis"}</span>
      <span>· ${esc(l.street)}</span>
      <span style="margin-left:auto" class="row-actions"><button class="btn ghost sm" data-fav="${l.id}" aria-pressed="${fav}">${fav ? "♥ Enregistré" : "♡ Enregistrer"}</button>
      ${u && !isOwner ? `<button class="btn ghost sm" data-report="${l.id}">${I.flag} Signaler</button>` : ""}</span></div>
    <div class="gal n${n}" data-act="lightbox">${imgs.slice(0, 5).map((s, i) => `<img src="${esc(s)}" alt="Photo ${i + 1} : ${esc(l.title)}" data-i="${i}" ${i ? 'loading="lazy"' : ""}>`).join("")}</div>
    <div class="dt-body"><div>
      ${l.is_demo ? '<div class="notice warn" style="margin-top:16px">Annonce de <b>démonstration</b> : le bien n\'est pas réellement disponible.</div>' : ""}
      <div class="block-sec"><div class="hostrow">${avatar(l.host.avatar, l.host.name, "lg")}<div><h2 style="margin:0;font-size:18px">${cap(l.ptype)} ${l.deal === "location" ? "à louer" : "à vendre"} · hôte : ${esc(l.host.name)}</h2>
        ${l.host.verified ? `<span class="verif">${I.check} Hôte vérifié par Ndaku</span>` : '<span class="unverif">Hôte non encore vérifié : ne payez rien avant la visite.</span>'}</div></div>
        <div class="specs" style="margin-top:14px"><span>${l.bedrooms} chambre${l.bedrooms > 1 ? "s" : ""}</span><span>· ${l.bathrooms} salle${l.bathrooms > 1 ? "s" : ""} de bain</span><span>· ${l.surface} m²</span>${l.furnished ? "<span>· Meublé</span>" : ""}</div></div>
      <div class="block-sec"><h2>À propos de ce bien</h2><div class="desc">${esc(l.description)}</div>
        ${l.credits?.length ? `<p class="hint">Photos : ${l.credits.map(c => `${/^https:\/\/commons\.wikimedia\.org\//.test(c.page || "") ? `<a href="${esc(c.page)}" target="_blank" rel="noopener noreferrer">${esc(c.author)}</a>` : esc(c.author)} (${esc(c.license)})`).join(" · ")}, via Wikimedia Commons</p>` : ""}</div>
      ${l.amenities.length ? `<div class="block-sec"><h2>Équipements</h2><div class="am-grid">${l.amenities.map(a => `<div>${I.check} ${esc(a)}</div>`).join("")}</div></div>` : ""}
      <div class="block-sec"><h2>Où se situe le bien</h2><p>${esc(l.street)}${l.address ? ` — <b>${esc(l.address)}</b>` : ""}</p>
        ${l.exact_location ? "" : '<p class="hint">Emplacement approximatif. L\'adresse exacte (numéro) est communiquée dès que vous contactez l\'hôte.</p>'}
        ${l.lat != null ? '<div class="mini-map" id="dmap"></div>' : ""}</div>
      <div class="block-sec"><h2>${l.reviews_count ? `${I.star} ${Number(l.rating).toFixed(1)} · ${l.reviews_count} avis vérifiés` : "Avis"}</h2>
        ${l.reviews.map(r => `<div class="rev">${avatar(r.avatar, r.name)}<div><div class="who">${esc(r.name)} <span class="stars">${"★".repeat(r.rating)}${"☆".repeat(5 - r.rating)}</span></div><time>${when(r.created_at)}</time><div>${esc(r.comment)}</div></div></div>`).join("") || '<p class="hint">Aucun avis pour le moment.</p>'}
        ${l.can_review ? `<form id="revForm"><div class="field"><label>Votre note</label><select name="rating">${[5, 4, 3, 2, 1].map(n => `<option value="${n}">${"★".repeat(n)}</option>`).join("")}</select></div><div class="field"><label>Votre avis</label><textarea name="comment" minlength="10" maxlength="800" required style="min-height:80px"></textarea></div><button class="btn sm">Publier l'avis</button></form>` : '<p class="hint">Seuls les clients ayant échangé avec l\'hôte via Ndaku peuvent laisser un avis.</p>'}</div>
    </div>
    <aside><div class="panel"><div><div class="big">${esc("$" + fmt(l.price))}${l.deal === "location" ? " <small>/ mois</small>" : ""}</div>
        <p class="hint hide-m" style="margin:6px 0 0">${esc(l.commune)}, ${esc(l.city)}</p></div>
      ${isOwner || isAdmin ? `<div class="hide-m"><p class="hint" style="margin-top:12px">Vous gérez cette annonce.</p>${isOwner && l.status === "active" ? `<button class="btn ghost block" data-close="${l.id}">Marquer comme ${l.deal === "location" ? "loué" : "vendu"}</button>` : ""}</div>`
        : l.conversation_id ? `<a class="btn" href="#/messages/${l.conversation_id}">Ouvrir la discussion</a>` : `<button class="btn" data-visit="${l.id}">Demander une visite</button>`}
      <div class="safe hide-m"><b>🛡 Restez protégé</b><br>Ne versez jamais d'argent avant d'avoir visité. Chaque photo et chaque adresse sont uniques sur Ndaku.</div></div></aside></div></div>`;
  state.gallery = imgs;
  if (l.lat != null) {
    const map = makeMap($("#dmap"), [l.lat, l.lng], 15);
    if (l.exact_location) L.marker([l.lat, l.lng], { icon: L.divIcon({ className: "pin-wrap", html: pinHtml(l), iconSize: null }) }).addTo(map);
    else L.circle([l.lat, l.lng], { radius: 250, color: "#F26122", fillColor: "#F26122", fillOpacity: .2, weight: 2 }).addTo(map);
  }
  const rf = $("#revForm");
  if (rf) rf.onsubmit = async e => { e.preventDefault(); if (needAvatar()) return; try { await api(`/api/listings/${id}/reviews`, { json: Object.fromEntries(new FormData(rf)) }); toast("Merci pour votre avis !"); detail(id); } catch (x) { toast(x.message); } };
}
function visitModal(lid) {
  if (needLogin() || needAvatar()) return;
  const m = modal("Demander une visite", `<form id="vf"><p>Votre message ouvre une discussion privée avec l'hôte : vous pourrez y convenir de la visite et, si vous le souhaitez, échanger vos coordonnées.</p>
    <div class="field"><label for="v-date">Date de visite souhaitée</label><input id="v-date" type="date" name="date" min="${new Date().toISOString().slice(0, 10)}"></div>
    <div class="field"><label for="v-msg">Message</label><textarea id="v-msg" name="message" required maxlength="2000">Bonjour, ce bien est-il toujours disponible ? Je souhaiterais le visiter.</textarea></div>
    <div class="err" id="vErr" role="alert"></div><button class="btn block">Envoyer et ouvrir la discussion</button></form>`);
  m.querySelector("#vf").onsubmit = async e => {
    e.preventDefault(); const b = e.target.querySelector(".btn"); b.disabled = true;
    try { const r = await api(`/api/listings/${lid}/conversation`, { json: Object.fromEntries(new FormData(e.target)) }); closeModal(); go(`#/messages/${r.id}`); }
    catch (x) { $("#vErr").textContent = x.message; b.disabled = false; }
  };
}
function reportModal(lid) {
  if (needLogin()) return;
  const cats = state.meta.report_categories;
  const m = modal("Signaler cette annonce", `<form id="rp"><p class="hint">Les signalements sont anonymes pour l'hôte. Après 3 signalements, l'annonce est masquée en attendant la modération.</p>
    <div class="radio-list">${Object.entries(cats).map(([k, v], i) => `<label><input type="radio" name="category" value="${k}" ${i ? "" : "checked"}><span>${esc(v)}</span></label>`).join("")}</div>
    <div class="field"><label for="rp-t">Détails (facultatif, obligatoire pour « Autre »)</label><textarea id="rp-t" name="reason" maxlength="500" style="min-height:80px"></textarea></div>
    <div class="err" id="rpErr" role="alert"></div><button class="btn block">Envoyer le signalement</button></form>`);
  m.querySelector("#rp").onsubmit = async e => {
    e.preventDefault();
    try { await api(`/api/listings/${lid}/report`, { json: Object.fromEntries(new FormData(e.target)) }); closeModal(); toast("Signalement envoyé, merci. La modération va vérifier."); }
    catch (x) { $("#rpErr").textContent = x.message; }
  };
}
function lightbox(i) {
  const imgs = state.gallery; if (!imgs?.length) return;
  let k = +i || 0;
  const m = modal(`Photo ${k + 1} / ${imgs.length}`, `<img src="${esc(imgs[k])}" alt="">`, "lightbox");
  m.querySelector(".mdl").onclick = e => { if (e.target.closest(".x")) return; k = (k + 1) % imgs.length; m.querySelector("img").src = imgs[k]; m.querySelector("header").lastChild.textContent = `Photo ${k + 1} / ${imgs.length}`; };
}

/* ============================================================================= messagerie */
async function messages(cid) {
  if (!state.user) throw Object.assign(new Error("Connexion requise"), { status: 401 });
  const view = $("#view");
  if (!$("#chat")) view.innerHTML = `<div class="chat" id="chat"><div class="inbox"><h1>Messages</h1><div id="convs">${SK.rows(6)}</div></div><section class="thread" id="thread"><div class="chat-empty"><div><h3>Vos discussions</h3><p>Demandez une visite depuis une annonce pour démarrer une discussion avec l'hôte.</p></div></div></section></div>`;
  const chat = $("#chat");
  chat.classList.toggle("has-thread", !!cid);
  const drawInbox = async () => {
    const r = await api("/api/conversations");
    $("#convs").innerHTML = r.items.length ? r.items.map(c => `<a class="conv ${c.id === cid ? "on" : ""} ${c.unread ? "unread" : ""}" href="#/messages/${c.id}">
      ${avatar(c.other_avatar, c.other_name, "lg")}<div class="t"><b>${esc(c.other_name)}${c.other_verified ? " ✓" : ""}</b><span>${esc(c.title)}</span>
      <span>${c.last_mine ? "Vous : " : ""}${esc(c.last_kind === "contact" ? "📇 Coordonnées partagées" : (c.last_body || "").slice(0, 80))}</span></div>
      ${c.unread ? '<span class="u" aria-label="non lu"></span>' : ""}</a>`).join("")
      : '<p class="hint" style="padding:0 20px">Aucune discussion pour le moment.</p>';
  };
  drawInbox().catch(e => toast(e.message));
  if (!cid) return;
  const th = $("#thread");
  th.innerHTML = `<div class="thread-h"><div class="sk av"></div><div class="t"><div class="sk l s"></div></div></div>${SK.chat()}`;
  let t = await api(`/api/conversations/${cid}`), lastId = 0;
  const bubble = m => {
    const meta = m.meta || {};
    const kind = m.kind === "visit" ? `<span class="k">Demande de visite${meta.date ? " · " + esc(new Date(meta.date + "T12:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })) : ""}</span>`
      : m.kind === "contact" ? '<span class="k">📇 Coordonnées partagées</span>' : "";
    return `${m.warn ? '<div class="warn">⚠️ Ce message parle d\'argent. Ne payez jamais d\'acompte, de caution ou de « frais de visite » avant d\'avoir visité le bien et vérifié les documents.</div>' : ""}
      <div class="bubble ${m.mine ? "mine" : ""} ${m.kind !== "text" ? m.kind : ""}">${kind}${esc(m.body)}<time>${hour(m.created_at)} · ${when(m.created_at)}</time></div>`;
  };
  th.innerHTML = `<div class="thread-h"><a class="icon-btn" href="#/messages" aria-label="Retour">←</a>${avatar(t.other.avatar, t.other.name)}
      <div class="t"><b>${esc(t.other.name)}${t.other.verified ? " ✓" : ""}</b><a href="#/listing/${t.listing_id}">${esc(t.title)}</a></div>
      <button class="btn soft sm" data-share="${cid}" aria-label="Partager mes coordonnées">📇<span class="hide-sm"> Mes coordonnées</span></button><button class="icon-btn" data-convmenu="${cid}" aria-label="Plus d'options">⋯</button></div>
    <div class="msgs" id="msgs"></div>
    ${t.blocked ? `<div class="notice warn" style="margin:12px">Discussion bloquée${t.blocked_by_me ? ` · <button class="linkish" data-unblock="${cid}">Débloquer</button>` : ""}.</div>`
      : `<form class="composer" id="cmp"><textarea name="body" rows="1" maxlength="2000" placeholder="Écrire un message…" aria-label="Message" required></textarea><button class="btn">Envoyer</button></form>`}`;
  const box = $("#msgs");
  const append = list => { if (!list.length) return; box.insertAdjacentHTML("beforeend", list.map(bubble).join("")); lastId = list[list.length - 1].id; box.scrollTop = box.scrollHeight; };
  append(t.messages);
  const me = state.user; if (me.unread) { me.unread = Math.max(0, me.unread - 1); renderTabbar(); }
  const cmp = $("#cmp");
  if (cmp) {
    const ta = cmp.querySelector("textarea");
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 140) + "px"; });
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !matchMedia("(max-width:760px)").matches) { e.preventDefault(); cmp.requestSubmit(); } });
    cmp.onsubmit = async e => {
      e.preventDefault(); const body = ta.value.trim(); if (!body) return;
      if (needAvatar()) return;
      ta.value = ""; ta.style.height = "auto";
      try { await api(`/api/conversations/${cid}/messages`, { json: { body } }); await poll(); drawInbox(); } catch (x) { ta.value = body; toast(x.message); }
    };
  }
  const poll = async () => { const r = await api(`/api/conversations/${cid}?after=${lastId}`); append(r.messages); };
  const iv = setInterval(() => { if (!document.hidden) poll().catch(() => {}); }, 5000);
  cleanup.push(() => clearInterval(iv));
}
function shareModal(cid) {
  const u = state.user;
  const m = modal("Partager mes coordonnées", `<form id="sh"><p>Choisissez ce que l'autre personne pourra voir. Ne partagez vos coordonnées qu'avec quelqu'un en qui vous avez confiance.</p>
    <label class="chk"><input type="checkbox" name="phone" ${u.phone ? "checked" : "disabled"}> Téléphone ${u.phone ? esc(u.phone) : '<span class="hint">(ajoutez-le dans <a href="#/profile">votre profil</a>)</span>'}</label>
    <label class="chk" style="margin:10px 0 18px"><input type="checkbox" name="email"> E-mail ${esc(u.email)}</label>
    <div class="err" id="shErr" role="alert"></div><button class="btn block">Partager dans la discussion</button></form>`);
  m.querySelector("#sh").onsubmit = async e => {
    e.preventDefault(); const fd = new FormData(e.target);
    try { await api(`/api/conversations/${cid}/share-contact`, { json: { phone: fd.has("phone"), email: fd.has("email") } }); closeModal(); route(); }
    catch (x) { $("#shErr").textContent = x.message; }
  };
}
function convMenu(cid) {
  const m = modal("Options de la discussion", `<div class="radio-list"><button class="btn ghost block" data-block="${cid}">🚫 Bloquer cette personne</button></div>
    <form id="ur"><h3 style="margin:8px 0">Signaler cette personne</h3><div class="radio-list">
      ${[["arnaque", "Demande d'argent / arnaque"], ["harcelement", "Harcèlement ou propos déplacés"], ["faux_profil", "Faux profil"], ["autre", "Autre"]].map(([k, v], i) => `<label><input type="radio" name="category" value="${k}" ${i ? "" : "checked"}><span>${v}</span></label>`).join("")}</div>
      <div class="field"><textarea name="reason" maxlength="500" placeholder="Détails (facultatif)" style="min-height:70px"></textarea></div>
      <div class="err" id="urErr"></div><button class="btn danger block">Signaler et bloquer</button></form>`);
  m.querySelector("#ur").onsubmit = async e => {
    e.preventDefault();
    try { await api(`/api/conversations/${cid}/report`, { json: Object.fromEntries(new FormData(e.target)) }); closeModal(); toast("Signalement envoyé. La discussion est bloquée."); route(); }
    catch (x) { $("#urErr").textContent = x.message; }
  };
}

/* ======================================================================= favoris & profil */
async function favorites() {
  if (!state.user) throw Object.assign(new Error("Connexion requise"), { status: 401 });
  $("#view").innerHTML = `<div class="wrap page"><h1>Mes favoris</h1><div id="fv">${SK.cards(4)}</div></div>`;
  const r = await api("/api/favorites");
  state.favs = new Set(r.items.map(l => l.id));
  $("#fv").innerHTML = r.items.length ? `<p class="sec-sub">${r.items.length} bien${r.items.length > 1 ? "s" : ""} enregistré${r.items.length > 1 ? "s" : ""}.</p><div class="grid">${r.items.map(l => cardHtml(l)).join("")}</div>`
    : '<div class="empty"><h3>Aucun favori</h3><p>Touchez le ♡ d\'une annonce pour la retrouver ici, sur tous vos appareils.</p><a class="btn" href="#/">Explorer</a></div>';
}
async function profile() {
  const u = state.user;
  if (!u) { $("#view").innerHTML = `<div class="wrap empty"><h3>Bienvenue sur Ndaku</h3><p>Connectez-vous pour gérer vos favoris, vos messages et vos annonces.</p><div class="row-actions" style="justify-content:center"><button class="btn" data-act="login">Se connecter</button><button class="btn ghost" data-act="signup">S'inscrire</button></div></div>`; return; }
  $("#view").innerHTML = `<div class="wrap page" style="max-width:640px"><div class="profile-head">${avatar(u.avatar, u.name, "xl")}<div><h1 style="margin:0">${esc(u.name)}</h1>
      <p class="hint">${u.role === "host" ? "Hôte" : u.role === "admin" ? "Administrateur" : "Client"}${u.verified ? " · ✓ vérifié" : ""} · ${esc(u.email)}</p><button class="btn soft sm" data-act="avatar">Changer de photo</button></div></div>
    <form id="pf" class="form"><div class="field"><label for="p-n">Nom</label><input id="p-n" name="name" value="${esc(u.name)}" maxlength="80" required></div>
      <div class="field"><label for="p-t">Téléphone</label><input id="p-t" name="phone" type="tel" value="${esc(u.phone || "")}" maxlength="30" placeholder="+243 …"><span class="hint">Jamais affiché publiquement : vous le partagez vous-même dans une discussion.</span></div>
      <div class="err" id="pfErr"></div><button class="btn">Enregistrer</button></form>
    <div class="block-sec"><h2 style="font-size:18px">Sécurité</h2><p class="hint">Connexion : ${u.providers.length ? u.providers.map(p => p === "apple" ? "Apple (iCloud)" : "Google").join(", ") : ""}${u.providers.length && u.has_password ? " + " : ""}${u.has_password ? "mot de passe" : ""}</p>
      <div class="row-actions">${u.role === "host" ? '<a class="btn ghost sm" href="#/host">Mes annonces</a>' : ""}<button class="btn ghost sm" data-act="logout-all">Se déconnecter de tous les appareils</button><button class="btn ghost sm" data-act="logout">Se déconnecter</button></div></div></div>`;
  $("#pf").onsubmit = async e => {
    e.preventDefault();
    try { state.user = (await api("/api/auth/me", { method: "PATCH", json: Object.fromEntries(new FormData(e.target)) })).user; renderHeader(); toast("Profil enregistré ✓"); }
    catch (x) { $("#pfErr").textContent = x.message; }
  };
}

/* ============================================================================ espace hôte */
async function dashboard() {
  const u = state.user;
  if (!u) { $("#view").innerHTML = `<div class="wrap empty"><h3>Devenez hôte sur Ndaku</h3><p>Publiez vos maisons à louer ou à vendre en quelques minutes.</p><button class="btn" data-act="signup-host">Créer un compte hôte</button></div>`; return; }
  if (u.role !== "host") throw new Error("Espace réservé aux hôtes.");
  $("#view").innerHTML = `<div class="wrap page"><div class="row-actions" style="justify-content:space-between;margin-bottom:12px"><h1 style="margin:0">Mes annonces</h1><a class="btn" href="#/new">+ Nouvelle annonce</a></div><div id="mine">${SK.rows(4)}</div></div>`;
  const r = await api("/api/my/listings");
  $("#mine").innerHTML = `${state.auth.email_verification && !u.email_verified ? '<div class="notice warn">Confirmez votre adresse e-mail pour publier. <button type="button" class="linkish" data-act="resend">Renvoyer l\'e-mail</button></div>' : ""}
    ${u.avatar ? "" : '<div class="notice warn">Ajoutez une photo de profil pour publier. <button type="button" class="linkish" data-act="avatar">Ajouter</button></div>'}
    ${r.items.length ? `<div class="table-wrap"><table class="tbl"><thead><tr><th></th><th>Annonce</th><th>Prix</th><th>Statut</th><th>Discussions</th><th></th></tr></thead><tbody>
      ${r.items.map(l => `<tr><td>${safeUrl(l.cover) ? `<img class="thumb" src="${esc(safeUrl(l.cover))}" alt="">` : ""}</td><td><a href="#/listing/${l.id}"><b>${esc(l.title)}</b></a><br><span class="hint">${esc(l.address || "")} · ${esc(l.commune)}, ${esc(l.city)}</span>${l.status === "pending" ? `<br><span class="hint">En vérification : ${esc(l.risk_reasons.join(" · "))}</span>` : ""}</td>
        <td>${money(l)}</td><td><span class="pill ${l.status}">${{ active: "En ligne", pending: "En vérification", rejected: "Rejetée", closed: l.deal === "location" ? "Loué" : "Vendu" }[l.status]}</span></td><td><a href="#/messages">${l.conversations}</a></td>
        <td>${l.status === "active" || l.status === "closed" ? `<button class="btn danger sm" data-del="${l.id}">Supprimer</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
      : '<div class="empty"><h3>Aucune annonce</h3><p>Publiez votre première maison.</p><a class="btn" href="#/new">Publier</a></div>'}`;
}

/* ======================================================================== publier un bien */
async function shrink(file, max = 2000) {
  // Réduction côté navigateur : envoi rapide sur réseau mobile, sous la limite de 4,5 Mo.
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
    if (k === 1 && file.size < 3_500_000) return file;
    const c = document.createElement("canvas"); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    const blob = await new Promise(r => c.toBlob(r, "image/jpeg", 0.9));
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch { return file; }
}
let photos = [], uploadQueue = Promise.resolve();
function uploadPhoto(p) {
  uploadQueue = uploadQueue.then(async () => {
    if (!photos.includes(p)) return;
    try {
      const fd = new FormData(); fd.append("image", await shrink(p.file));
      const r = await api("/api/uploads", { method: "POST", body: fd });
      p.id = r.id; p.state = "ok";
      if (!photos.includes(p)) api("/api/uploads/" + r.id, { method: "DELETE" }).catch(() => {});
    } catch (x) { p.state = "bad"; p.reason = x.message; }
    drawPv();
  });
}
function drawPv() {
  const box = $("#pvs"); if (!box) return;
  box.innerHTML = photos.map((p, i) => `<div class="pv ${p.state === "bad" ? "bad" : ""} ${i === 0 ? "first" : ""}"><img src="${p.url}" alt="">
    <button type="button" data-rm="${i}" aria-label="Retirer">✕</button>
    ${p.state === "up" ? '<div class="st">Vérification…</div>' : p.state === "ok" ? '<div class="st ok">✓ Unique</div>' : `<div class="why">${esc(p.reason)}</div>`}</div>`).join("");
}
async function newListing() {
  const u = state.user;
  if (!u) throw Object.assign(new Error("Connexion requise"), { status: 401 });
  if (u.role !== "host") throw new Error("Seuls les hôtes peuvent publier des annonces.");
  photos = [];
  const M = state.meta;
  $("#view").innerHTML = `<div class="wrap page"><form class="form" id="nf" novalidate><h1>Publier un bien</h1>
    ${u.avatar ? "" : '<div class="notice warn">Ajoutez d\'abord une photo de profil. <button type="button" class="linkish" data-act="avatar">Ajouter</button></div>'}
    ${state.auth.email_verification && !u.email_verified ? '<div class="notice warn">Confirmez votre adresse e-mail pour publier. <button type="button" class="linkish" data-act="resend">Renvoyer l\'e-mail</button></div>' : ""}
    <div class="seg-pick"><label><input type="radio" name="deal" value="location" checked><b>Location</b><span>Prix par mois</span></label><label><input type="radio" name="deal" value="vente"><b>Vente</b><span>Prix de vente total</span></label></div>
    <div class="field"><label for="n-title">Titre *</label><input id="n-title" name="title" maxlength="120" required placeholder="Ex. Villa 4 chambres avec jardin à Ngaliema"></div>
    <div class="cols"><div class="field"><label for="n-type">Type de bien</label><select id="n-type" name="ptype">${M.ptypes.map(p => `<option value="${p}">${cap(p)}</option>`).join("")}</select></div>
    <div class="field"><label id="pl" for="n-price">Loyer mensuel (USD) *</label><input id="n-price" name="price" type="number" min="1" inputmode="numeric" required></div></div>
    <h2 style="font-size:18px;margin:18px 0 8px">Adresse du bien</h2>
    <p class="hint" style="margin-top:0">Une même adresse (avenue + numéro) ne peut figurer que dans une seule annonce. Le numéro n'est montré qu'aux personnes qui vous contactent.</p>
    <div id="npp"></div>
    <div class="cols"><div class="field"><label for="n-no">Numéro de la maison *</label><input id="n-no" name="house_number" maxlength="12" required placeholder="Ex. 12, 12 bis, 45/B"></div>
    <div class="field" id="unitF"><label for="n-unit">Appartement / étage (si immeuble)</label><input id="n-unit" name="unit" maxlength="30" placeholder="Ex. Appt 3B, 2e étage"></div></div>
    <div class="field"><span class="lbl">Position exacte sur la carte *</span><div class="pin-map" id="pinMap"></div><span class="hint" id="pinHint">Choisissez la commune puis cliquez sur la carte à l'emplacement exact du bien (vous pouvez déplacer l'épingle).</span></div>
    <div class="cols3"><div class="field"><label for="n-bed">Chambres</label><input id="n-bed" name="bedrooms" type="number" min="0" max="20" value="2" required></div>
    <div class="field"><label for="n-bath">Salles de bain</label><input id="n-bath" name="bathrooms" type="number" min="0" max="20" value="1" required></div>
    <div class="field"><label for="n-surf">Surface (m²) *</label><input id="n-surf" name="surface" type="number" min="9" required></div></div>
    <div class="field"><label for="n-desc">Description *</label><textarea id="n-desc" name="description" required minlength="60" maxlength="3000" placeholder="Décrivez le bien, le quartier, l'état, les conditions (60 caractères minimum)."></textarea>
      <span class="hint">Pas de numéro, e-mail ni lien ici : vous échangerez vos coordonnées dans la messagerie Ndaku.</span></div>
    <label class="chk" style="margin-bottom:14px"><input type="checkbox" name="furnished" value="1"> Meublé</label>
    <div class="field"><span class="lbl">Équipements</span><div class="tags">${M.amenities.map(a => `<label class="tag"><input type="checkbox" name="amenities" value="${esc(a)}">${esc(a)}</label>`).join("")}</div></div>
    <div class="field"><span class="lbl">Photos (${M.min_images} à ${M.max_images}) — uniques, prises par vous</span>
      <label class="drop" id="drop" for="n-files">Glissez vos photos ici ou <u>parcourez</u><br><span class="hint">JPEG, PNG ou WebP · min. 480×320 · chaque photo est comparée à toutes les annonces existantes</span></label>
      <input id="n-files" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden><div class="previews" id="pvs"></div></div>
    <div class="err" id="nerr" role="alert"></div><button class="btn" id="nsub">Publier l'annonce</button></form></div>`;
  // -------- localisation + épingle
  let loc = {}, pin = null;
  const map = makeMap($("#pinMap"));
  const setPin = ll => {
    if (pin) pin.setLatLng(ll); else { pin = L.marker(ll, { draggable: true }).addTo(map); pin.on("dragend", () => { $("#pinHint").textContent = "Position enregistrée ✓"; }); }
    $("#pinHint").textContent = "Position enregistrée ✓ (déplacez l'épingle si besoin)";
  };
  map.on("click", e => setPin(e.latlng));
  placePicker($("#npp"), { mode: "host", onChange: async v => {
    loc = v;
    const deepest = ["avenue_id", "quartier_id", "commune_id", "city_id", "province_id"].find(k => v[k]);
    if (!deepest) return;
    const parent = { avenue_id: v.quartier_id || v.commune_id, quartier_id: v.commune_id, commune_id: v.city_id, city_id: v.province_id, province_id: null }[deepest];
    const p = (await children(parent)).find(x => x.id === v[deepest]);
    if (p?.lat != null) map.setView([p.lat, p.lng], { avenue_id: 17, quartier_id: 15, commune_id: 14, city_id: 12, province_id: 7 }[deepest], { animate: false });
  } });
  $("#nf").addEventListener("change", e => {
    if (e.target.name === "deal") $("#pl").textContent = e.target.value === "vente" ? "Prix de vente (USD) *" : "Loyer mensuel (USD) *";
    if (e.target.closest(".tag")) e.target.closest(".tag").classList.toggle("on", e.target.checked);
  });
  // -------- photos
  const add = list => {
    if (needAvatar()) return;
    for (const f of list) {
      if (!f.type.startsWith("image/") || photos.filter(p => p.state !== "bad").length >= M.max_images) continue;
      if (photos.some(p => p.file.name === f.name && p.file.size === f.size)) continue;
      const p = { file: f, url: URL.createObjectURL(f), state: "up" }; photos.push(p); uploadPhoto(p);
    }
    drawPv();
  };
  $("#n-files").onchange = e => { add([...e.target.files]); e.target.value = ""; };
  const drop = $("#drop");
  ["dragover", "dragenter"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => add([...e.dataTransfer.files]));
  $("#pvs").onclick = e => {
    const b = e.target.closest("[data-rm]"); if (!b) return;
    const [p] = photos.splice(+b.dataset.rm, 1); URL.revokeObjectURL(p.url);
    if (p.id) api("/api/uploads/" + p.id, { method: "DELETE" }).catch(() => {});
    drawPv();
  };
  // -------- envoi
  $("#nf").onsubmit = async e => {
    e.preventDefault();
    const err = $("#nerr"); err.textContent = "";
    if (needAvatar()) return;
    if (!loc.commune_id || !loc.avenue_id) { err.textContent = "Choisissez la commune et l'avenue (ou proposez-la si elle manque)."; return; }
    if (!pin) { err.textContent = "Placez le bien sur la carte."; return; }
    if (photos.some(p => p.state === "up")) { err.textContent = "Patientez : des photos sont encore en cours de vérification."; return; }
    if (photos.some(p => p.state === "bad")) { err.textContent = "Retirez les photos refusées (en rouge) avant de publier."; return; }
    const ok = photos.filter(p => p.state === "ok");
    if (ok.length < M.min_images) { err.textContent = `Ajoutez au moins ${M.min_images} photos.`; return; }
    const fd = new FormData(e.target), d = Object.fromEntries(fd);
    const ll = pin.getLatLng();
    Object.assign(d, { amenities: fd.getAll("amenities"), furnished: fd.has("furnished"), image_ids: ok.map(p => p.id),
      commune_id: loc.commune_id, quartier_id: loc.quartier_id || null, avenue_id: loc.avenue_id, lat: ll.lat, lng: ll.lng });
    const btn = $("#nsub"); btn.disabled = true; btn.textContent = "Contrôle anti-fraude en cours…";
    try {
      const r = await api("/api/listings", { json: d });
      photos = [];
      toast(r.status === "active" ? "Annonce publiée ✓" : "Annonce reçue : vérification par la modération");
      go("#/host");
    } catch (x) { err.textContent = x.message; btn.disabled = false; btn.textContent = "Publier l'annonce"; }
  };
}

/* ============================================================================= modération */
const ADMIN_TABS = [["queue", "Annonces en attente"], ["reports", "Signalements"], ["users", "Utilisateurs signalés"], ["places", "Lieux proposés"], ["osm", "Référentiel (OSM)"]];
async function admin(tab) {
  if (state.user?.role !== "admin") throw new Error("Espace réservé à la modération.");
  $("#view").innerHTML = `<div class="wrap page"><h1>Modération</h1><div class="tabs">${ADMIN_TABS.map(([k, l]) => `<button class="${k === tab ? "on" : ""}" data-tab="${k}">${l}</button>`).join("")}</div><div id="adm">${SK.rows(5)}</div></div>`;
  const box = $("#adm");
  if (tab === "queue") {
    const r = await api("/api/admin/queue");
    box.innerHTML = `<div class="notice ok"><b>Annonces de démonstration</b> — importe des annonces illustrées par de vraies photos de maisons de RDC (Wikimedia Commons, licences libres, crédits affichés). Elles arrivent ici : vérifiez chaque photo avant d'approuver.
      <div class="row-actions" style="margin-top:10px"><button class="btn sm" data-demo="commons">Importer (photos réelles)</button><span class="hint" id="demoSt"></span></div></div>
      ${r.items.map(l => `<div class="block-sec"><div class="row-actions" style="align-items:flex-start;justify-content:space-between"><div style="display:flex;gap:14px">${safeUrl(l.cover) ? `<img class="thumb" src="${esc(safeUrl(l.cover))}" alt="">` : ""}<div><a href="#/listing/${l.id}"><b>${esc(l.title)}</b></a>${l.is_demo ? ' <span class="pill">Démo</span>' : ""}<br><span class="hint">Hôte : ${esc(l.host)} ${l.host_verified ? "✓" : `<button class="linkish" data-verify="${l.host_id}">vérifier l'hôte</button>`} · ${money(l)} · ${esc(l.commune)}</span>
        ${l.risk_reasons.length || l.reports.length ? `<div class="risk" style="margin-top:8px"><b>Risque ${l.risk_score}</b><ul style="margin:4px 0 0">${l.risk_reasons.map(x => `<li>${esc(x)}</li>`).join("")}${l.reports.map(x => `<li>Signalement : ${esc(x)}</li>`).join("")}</ul></div>` : ""}</div></div>
        <div class="row-actions"><button class="btn sm" data-decide="approve" data-id="${l.id}">Approuver</button><button class="btn danger sm" data-decide="reject" data-id="${l.id}">Rejeter</button></div></div></div>`).join("") || '<div class="empty"><h3>File vide 🎉</h3></div>'}`;
  } else if (tab === "reports") {
    const r = await api("/api/admin/reports");
    box.innerHTML = r.items.map(g => `<div class="block-sec"><div class="row-actions" style="justify-content:space-between;align-items:flex-start"><div><a href="#/listing/${g.listing_id}"><b>${esc(g.title)}</b></a> <span class="pill ${esc(g.status)}">${esc(g.status)}</span><br><span class="hint">Hôte : ${esc(g.host)} · ${g.n} signalement${g.n > 1 ? "s" : ""}</span>
        <ul>${g.items.map(i => `<li><b>${esc(r.categories[i.category] || i.category)}</b> — ${esc(i.reason)}</li>`).join("")}</ul></div>
      <div class="row-actions"><button class="btn soft sm" data-rclose="dismiss" data-id="${g.listing_id}">Classer sans suite</button><button class="btn danger sm" data-rclose="hide" data-id="${g.listing_id}">Retirer l'annonce</button><button class="btn danger sm" data-suspend="${g.owner_id}">Suspendre l'hôte</button></div></div></div>`).join("") || '<div class="empty"><h3>Aucun signalement ouvert</h3></div>';
  } else if (tab === "users") {
    const r = await api("/api/admin/user-reports");
    box.innerHTML = r.items.map(x => `<div class="block-sec"><b>${esc(x.target)}</b> signalé par ${esc(x.reporter)} — ${esc(x.category)} : ${esc(x.reason)} ${x.suspended ? '<span class="pill rejected">suspendu</span>' : ""}
      ${x.messages.length ? `<details><summary>Voir les derniers messages de la discussion signalée</summary><ul>${x.messages.map(m => `<li><b>${esc(m.sender)}</b> : ${esc(m.body)}</li>`).join("")}</ul></details>` : ""}
      <div class="row-actions" style="margin-top:8px"><button class="btn soft sm" data-udismiss="${x.id}">Classer sans suite</button>${x.suspended ? "" : `<button class="btn danger sm" data-suspend="${x.target_id}">Suspendre le compte</button>`}</div></div>`).join("") || '<div class="empty"><h3>Aucun utilisateur signalé</h3></div>';
  } else if (tab === "places") {
    const r = await api("/api/admin/places/pending");
    box.innerHTML = r.items.length ? `<div class="table-wrap"><table class="tbl"><thead><tr><th>Lieu proposé</th><th>Dans</th><th>Par</th><th>Annonces</th><th></th></tr></thead><tbody>${r.items.map(p => `<tr><td><b>${esc(p.name)}</b> <span class="hint">(${esc(p.kind)})</span></td><td>${esc(p.parent)}</td><td>${esc(p.author || "—")}</td><td>${p.uses}</td>
      <td class="row-actions"><button class="btn sm" data-place="approve" data-id="${p.id}">Valider</button><button class="btn danger sm" data-place="reject" data-id="${p.id}">Refuser</button></td></tr>`).join("")}</tbody></table></div>` : '<div class="empty"><h3>Aucune proposition</h3></div>';
  } else if (tab === "osm") {
    box.innerHTML = `<p>Importe depuis OpenStreetMap les quartiers et avenues de chaque commune (données ODbL). À relancer de temps en temps : les doublons sont ignorés.</p>
      <div id="osmPick"></div><div id="osmCov"></div>`;
    let city = null;
    const showCov = async () => {
      if (!city) { $("#osmCov").innerHTML = ""; return; }
      const r = await api(`/api/admin/osm/coverage?city_id=${city}`);
      $("#osmCov").innerHTML = `<div class="row-actions" style="margin:12px 0"><button class="btn sm" data-osmall="1">Importer toutes les communes</button><span class="hint" id="osmSt"></span></div>
        <div class="table-wrap"><table class="tbl"><thead><tr><th>Commune</th><th>Quartiers</th><th>Avenues</th><th></th></tr></thead><tbody>${r.items.map(c => `<tr><td>${esc(c.name)}</td><td>${c.quartiers}</td><td>${c.avenues}</td><td><button class="btn soft sm" data-osm="${c.id}">Importer</button></td></tr>`).join("")}</tbody></table></div>`;
      $("#osmCov").onclick = async e => {
        const one_ = e.target.closest("[data-osm]"), all = e.target.closest("[data-osmall]");
        const ids = one_ ? [one_.dataset.osm] : all ? r.items.map(c => c.id) : [];
        for (const [i, cid] of ids.entries()) {
          $("#osmSt") && ($("#osmSt").textContent = `Import ${i + 1}/${ids.length}…`);
          try { const x = await api(`/api/admin/osm/${cid}`, { method: "POST" }); toast(`+${x.quartiers} quartiers, +${x.avenues} avenues`); } catch (x) { toast(x.message); }
        }
        placeCache.clear(); showCov();
      };
    };
    const host = $("#osmPick"); host.innerHTML = '<div class="cols"><div class="field"><label>Province</label><select id="op"></select></div><div class="field"><label>Ville</label><select id="oc" disabled></select></div></div>';
    const provs = await children(null);
    $("#op").innerHTML = '<option value="">Choisir…</option>' + provs.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
    $("#op").onchange = async e => { const cs = e.target.value ? (await children(+e.target.value)).filter(p => p.kind === "city") : []; $("#oc").innerHTML = '<option value="">Choisir…</option>' + cs.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join(""); $("#oc").disabled = !cs.length; city = null; showCov(); };
    $("#oc").onchange = e => { city = +e.target.value || null; showCov(); };
  }
}
async function runDemo(source, btn) {
  btn.disabled = true; const st = $("#demoSt"); let n = 0;
  try {
    for (let i = 0; i < 20; i++) {
      st.textContent = `Import en cours… ${n} annonce(s) créée(s)`;
      const r = await api("/api/admin/demo", { json: { source } });
      n += r.created.length;
      if (r.skipped.length) toast(r.skipped[0]);
      if (r.done) break;
    }
    toast(`${n} annonce(s) de démo importée(s).`); route();
  } catch (x) { toast(x.message); btn.disabled = false; st.textContent = ""; }
}

/* ================================================================================ événements */
const act = async (path, json, okMsg) => { try { await api(path, json === undefined ? { method: "POST" } : { json }); if (okMsg) toast(okMsg); route(); } catch (x) { toast(x.message); } };
document.addEventListener("click", async e => {
  const t = e.target, a = t.closest("[data-act]")?.dataset.act;
  if (a === "login") return authModal("login");
  if (a === "signup") return authModal("signup", "client");
  if (a === "signup-host") return authModal("signup", "host");
  if (a === "close") return closeModal();
  if (a === "forgot") return forgotModal();
  if (a === "avatar") return avatarModal(false);
  if (a === "where") return whereModal();
  if (a === "filters") return filtersModal();
  if (a === "reset") { closeModal(); state.placeName = ""; return go("#/"); }
  if (a === "where-reset") { closeModal(); state.placeName = ""; const f = { ...state.f }; PLACE_LEVELS.forEach(([k]) => { f[k] = ""; }); f.bbox = ""; return go("#/" + qs(f)); }
  if (a === "lightbox") return lightbox(t.dataset.i);
  if (a === "resend") return act("/api/auth/resend-verification", undefined, "E-mail de confirmation renvoyé.");
  if (a === "logout" || a === "logout-all") { await api(a === "logout" ? "/api/auth/logout" : "/api/auth/logout-all", { method: "POST" }).catch(() => {}); state.user = null; state.favs = new Set(); renderHeader(); go("#/"); return toast("À bientôt !"); }
  const tab = t.closest("[data-tab]"); if (tab) return go(`#/admin?tab=${tab.dataset.tab}`);
  const cat = t.closest("[data-cat]"); if (cat) return go("#/" + qs({ ...state.f, ptype: cat.dataset.cat }));
  const fav = t.closest("[data-fav]");
  if (fav) {
    e.preventDefault(); e.stopPropagation();
    if (needLogin()) return;
    try {
      const id = +fav.dataset.fav, r = await api(`/api/listings/${id}/favorite`, { method: "POST" });
      r.favorite ? state.favs.add(id) : state.favs.delete(id);
      document.querySelectorAll(`[data-fav="${id}"]`).forEach(el => { el.classList.toggle("on", r.favorite); el.setAttribute("aria-pressed", r.favorite); if (el.matches(".btn")) el.textContent = r.favorite ? "♥ Enregistré" : "♡ Enregistrer"; });
      toast(r.favorite ? "Ajouté à vos favoris" : "Retiré de vos favoris");
      if (parse().path === "/favorites" && !r.favorite) route();
    } catch (x) { toast(x.message); }
    return;
  }
  const visit = t.closest("[data-visit]"); if (visit) return visitModal(+visit.dataset.visit);
  const rep = t.closest("[data-report]"); if (rep) return reportModal(+rep.dataset.report);
  const share = t.closest("[data-share]"); if (share) return shareModal(+share.dataset.share);
  const cm = t.closest("[data-convmenu]"); if (cm) return convMenu(+cm.dataset.convmenu);
  const blk = t.closest("[data-block]"); if (blk) { closeModal(); return act(`/api/conversations/${blk.dataset.block}/block`, {}, "Personne bloquée."); }
  const ub = t.closest("[data-unblock]"); if (ub) return act(`/api/conversations/${ub.dataset.unblock}/block`, { unblock: true }, "Discussion débloquée.");
  const del = t.closest("[data-del]");
  if (del && confirm("Supprimer cette annonce ? Ses photos et son adresse seront libérées.")) { try { await api("/api/listings/" + del.dataset.del, { method: "DELETE" }); route(); } catch (x) { toast(x.message); } return; }
  const cl = t.closest("[data-close]"); if (cl) { try { await api("/api/listings/" + cl.dataset.close, { method: "PATCH", json: { status: "closed" } }); toast("Annonce clôturée"); route(); } catch (x) { toast(x.message); } return; }
  const demo = t.closest("[data-demo]"); if (demo) return runDemo(demo.dataset.demo, demo);
  const ver = t.closest("[data-verify]"); if (ver) return act(`/api/admin/users/${ver.dataset.verify}/verify`, undefined, "Hôte vérifié ✓");
  const dec = t.closest("[data-decide]"); if (dec) return act(`/api/admin/listings/${dec.dataset.id}/decision`, { action: dec.dataset.decide });
  const rc = t.closest("[data-rclose]"); if (rc) return act(`/api/admin/reports/${rc.dataset.id}/close`, { action: rc.dataset.rclose });
  const sus = t.closest("[data-suspend]"); if (sus && confirm("Suspendre ce compte ? Ses sessions sont coupées et ses annonces masquées.")) return act(`/api/admin/users/${sus.dataset.suspend}/suspend`, { suspend: true }, "Compte suspendu.");
  const ud = t.closest("[data-udismiss]"); if (ud) return act(`/api/admin/user-reports/${ud.dataset.udismiss}/dismiss`, undefined);
  const pl = t.closest("[data-place]"); if (pl) { placeCache.clear(); return act(`/api/admin/places/${pl.dataset.id}/decision`, { action: pl.dataset.place }); }
  if (t.closest("[data-need]") && !state.user) { e.preventDefault(); authModal("signup", "host"); }
});
window.addEventListener("hashchange", route);

/* ================================================================ messages non lus (pastille) */
setInterval(async () => {
  if (!state.user || document.hidden || parse().path.startsWith("/messages/")) return;
  try { const r = await api("/api/auth/me"); if (r.user && r.user.unread !== state.user.unread) { state.user.unread = r.user.unread; renderHeader(); } } catch { /* hors ligne */ }
}, 30000);

(async () => {
  try {
    [state.meta, { user: state.user }, state.auth] = await Promise.all([api("/api/meta"), api("/api/auth/me"), api("/api/auth/config")]);
    await loadFavs();
  } catch (e) { $("#view").innerHTML = errPage("Ndaku est momentanément indisponible. " + e.message); return; }
  route();
})();
})();
