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
const P = {
  pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  idcard: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.6-1.5 1.7-2 3-2s2.4.5 3 2M14 10h4M14 13h3"/>',
  shield: '<path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
  checkc: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  check2: '<path d="m1.5 12.5 4.5 4.5L16 7M11 16l1 1 10-10"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  dots: '<path d="M5 12h.01M12 12h.01M19 12h.01" stroke-width="3.2"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  heart: '<path d="M12 21C5 16 2 12 2 8.5a5 5 0 0 1 10-1.5 5 5 0 0 1 10 1.5C22 12 19 16 12 21z"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  drop: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  road: '<path d="M8 3 4 21M16 3l4 18M12 4v3M12 11v3M12 18v2"/>',
  rain: '<path d="M7 15a4 4 0 0 1-.5-8A6 6 0 0 1 18 8a3.5 3.5 0 0 1-.5 7z"/><path d="M8 18l-1 2M12 18l-1 2M16 18l-1 2"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z"/>',
  send: '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
  home: '<path d="M3 12 12 4l9 8M5 10.5V20h14v-9.5"/>',
  star: '<path d="m12 2 3 7 7.5.6-5.7 5 1.8 7.4L12 18l-6.6 4 1.8-7.4-5.7-5L9 9z"/>',
  bed: '<path d="M3 18V7M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="2"/>',
  bath: '<path d="M4 12h16v3a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4zM6 12V6a2 2 0 0 1 4 0M7 19l-1 2M17 19l1 2"/>',
  area: '<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M3 9h4M3 15h4M9 3v4M15 3v4"/>',
  sofa: '<path d="M5 11V8a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v3"/><path d="M3 13a2 2 0 0 1 4 0v2h10v-2a2 2 0 0 1 4 0v5H3zM5 18v2M19 18v2"/>',
  generator: '<rect x="3" y="7" width="18" height="12" rx="2"/><path d="M7 7V5h4v2M13 10l-2 3h3l-2 3"/>',
  parking: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M10 17V7h3a3 3 0 0 1 0 6h-3"/>',
  fence: '<path d="M5 21V6l2-2 2 2v15M15 21V6l2-2 2 2v15M3 10h18M3 16h18"/>',
  guard: '<path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6z"/><circle cx="12" cy="10" r="2"/><path d="M8.5 16c.7-1.6 2-2.3 3.5-2.3s2.8.7 3.5 2.3"/>',
  snow: '<path d="M12 2v20M4 7l16 10M20 7 4 17M9 4l3 2 3-2M9 20l3-2 3 2"/>',
  wifi: '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><path d="M12 19.5h.01" stroke-width="3"/>',
  wifioff: '<path d="M2 2l20 20M8.5 16a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 5.2-2.7M14 9.8a10 10 0 0 1 5 2.7M2 9a15 15 0 0 1 4.3-2.8M10.7 5A15 15 0 0 1 22 9"/>',
  tree: '<path d="M12 22v-6M12 2a6 6 0 0 0-5 9.3A4.5 4.5 0 0 0 9 18h6a4.5 4.5 0 0 0 2-6.7A6 6 0 0 0 12 2z"/>',
  tank: '<ellipse cx="12" cy="5" rx="7" ry="2.5"/><path d="M5 5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V5M5 11.5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
  pot: '<path d="M4 10h16v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4zM2 10h2M20 10h2M9 6c0-1 1-1 1-2M14 6c0-1 1-1 1-2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
};
const ic = (n, s = 18, cls = "") => `<svg class="ic ${cls}" width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || P.checkc}</svg>`;
const AMENITY_ICON = { "Eau courante": "drop", "Électricité": "bolt", "Groupe électrogène": "generator", "Parking": "parking", "Clôture": "fence",
  "Gardien": "guard", "Climatisation": "snow", "Internet": "wifi", "Jardin": "tree", "Citerne": "tank", "Cuisine équipée": "pot", "Panneaux solaires": "sun" };
const SCORE_WORD = n => n >= 10 ? "Excellent" : n >= 8 ? "Très bon" : n >= 6 ? "Bon" : n >= 4 ? "Moyen" : "Faible";
const RATING_WORD = { 5: "Excellent", 4: "Très bien", 3: "Correct", 2: "Décevant", 1: "Mauvais" };
const stars = n => `<span class="stars" aria-label="${n} sur 5">${[1, 2, 3, 4, 5].map(i => `<svg class="ic ${i <= n ? "full" : ""}" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">${P.star}</svg>`).join("")}</span>`;
const starPicker = (val = 0) => `<div class="star-pick" role="radiogroup" aria-label="Votre note">${[5, 4, 3, 2, 1].map(n =>
  `<input type="radio" name="rating" value="${n}" id="sp${n}" ${n === val ? "checked" : ""}><label for="sp${n}" title="${n} étoile${n > 1 ? "s" : ""} · ${RATING_WORD[n]}">${ic("star", 30)}</label>`).join("")}</div><span class="star-word hint">${val ? RATING_WORD[val] : "Touchez une étoile"}</span>`;
function reviewForm(mine, label) {
  return `<form id="revForm" class="rev-form"><h3>${mine ? `${ic("edit", 16)} Modifier votre avis` : `Votre avis ${label}`}</h3>${starPicker(mine?.rating || 0)}
    <div class="field"><label for="rv-c">Votre commentaire</label><textarea id="rv-c" name="comment" minlength="10" maxlength="800" required style="min-height:80px">${esc(mine?.comment || "")}</textarea></div>
    <div class="err" id="rvErr" role="alert"></div>
    <div class="row-actions"><button class="btn sm">${mine ? "Enregistrer les modifications" : "Publier l'avis"}</button>${mine ? `<button type="button" class="btn ghost sm" data-revdel="1">${ic("trash", 14)} Supprimer mon avis</button>` : ""}</div></form>`;
}
function bindReviewForm(endpoint, reload) {
  const f = $("#revForm"); if (!f) return;
  f.addEventListener("change", e => { if (e.target.name === "rating") f.querySelector(".star-word").textContent = RATING_WORD[e.target.value]; });
  f.onsubmit = async e => {
    e.preventDefault(); if (needAvatar()) return;
    const rating = +(new FormData(f).get("rating") || 0);
    if (!rating) { $("#rvErr").textContent = "Choisissez une note en touchant les étoiles."; return; }
    try { const r = await api(endpoint, { json: { rating, comment: f.comment.value } }); toast(r.created ? "Merci pour votre avis !" : "Avis modifié"); reload(); }
    catch (x) { $("#rvErr").textContent = x.message; }
  };
  const del = f.querySelector("[data-revdel]");
  if (del) del.onclick = async () => { if (!confirm("Supprimer votre avis ?")) return; try { await api(endpoint + "/mine", { method: "DELETE" }); toast("Avis supprimé"); reload(); } catch (x) { toast(x.message); } };
}
const favLabel = on => `${ic("heart", 16)} ${on ? "Enregistré" : "Enregistrer"}`;
const verifiedTick = `<span class="vtick" title="Identité vérifiée">${ic("checkc", 15)}</span>`;
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
const FILTER_KEYS = ["province_id", "city_id", "commune_id", "quartier_id", "avenue_id", "deal", "ptype", "max_price", "min_price", "bedrooms", "furnished", "min_elec", "min_water", "min_access", "sort", "q", "bbox"];
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
  ov.innerHTML = `<div class="mdl ${cls}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header><button class="x" data-act="close" aria-label="Fermer">${ic("x", 18)}</button>${esc(title)}</header><div class="bd">${html}</div></div>`;
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
      ${u ? `<a class="icon-btn bell-btn" href="#/notifications" aria-label="Notifications${u.notif_unread ? ` (${u.notif_unread} non lues)` : ""}">${ic("bell", 22)}${u.notif_unread ? `<span class="dot">${u.notif_unread > 9 ? "9+" : u.notif_unread}</span>` : ""}</a>` : ""}
      ${u ? `<a class="icon-btn msg-btn" href="#/messages" aria-label="Messages">${I.chat}${u.unread ? `<span class="dot">${u.unread}</span>` : ""}</a>` : ""}
      <button class="menu-btn" id="menuBtn" aria-haspopup="true" aria-label="Menu du compte">${I.burger}${u ? avatar(u.avatar, u.name) : `<span class="avatar">${ic("user", 18)}</span>`}</button>
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
  p.innerHTML = u ? `<div class="who">${esc(u.name)} · ${u.role === "host" ? "Hôte" : u.role === "admin" ? "Admin" : "Client"}${u.verified ? ` · ${verifiedTick} vérifié` : ""}</div>
      <a href="#/messages">Messages${u.unread ? ` (${u.unread})` : ""}</a><a href="#/notifications">Notifications${u.notif_unread ? ` (${u.notif_unread})` : ""}</a><a href="#/favorites">Favoris</a>
      ${u.role === "host" ? `<a href="#/host">Mes annonces et statistiques</a><a href="#/new">Publier une annonce</a>${u.verified ? "" : '<a href="#/verification">Vérifier mon identité</a>'}` : ""}
      <a href="#/prix">Prix du marché</a>
      ${u.role === "admin" ? `<a href="#/admin">Modération</a>` : ""}<a href="#/profile">Paramètres</a><hr><button data-act="logout">Se déconnecter</button>`
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
const avatarField = (id = "a-photo") => `<div class="av-pick"><label for="${id}" class="avatar" id="${id}-pv" title="Choisir une photo">${ic("camera", 26)}</label>
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
    try { await uploadAvatar(getPhoto()); closeModal(); renderHeader(); route(); toast("Photo de profil enregistrée"); }
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
    $("#view").innerHTML = `<div class="wrap empty"><h3>${ic("checkc", 22)} Adresse e-mail confirmée</h3><a class="btn" href="#/">Continuer</a></div>`; }
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
  document.body.classList.remove("in-thread");
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
    if ((m = path.match(/^\/hote\/(\d+)$/))) return await hostPage(+m[1]);
    if (path === "/notifications") return await notificationsPage();
    if (path === "/verification") return await kycPage();
    if (path === "/prix") return await pricesPage(params);
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
    + `<button class="chip-btn first" data-act="where">${ic("pin", 16)} ${esc(state.placeName || "Lieu")}</button><button class="chip-btn" data-act="filters">${I.filter} Filtres</button>`;
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
    ${l.elec_score ? `<div class="m q"><span title="Électricité : ${l.elec_score}/10">${ic("bolt", 14)} ${l.elec_score}/10</span><span title="Eau : ${l.water_score}/10">${ic("drop", 14)} ${l.water_score}/10</span></div>` : ""}
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
      <section class="list"><div class="sec-head"><h2 class="sec-title" id="ht">${filtered ? "Recherche" : "Les meilleures maisons du moment"}</h2>
        ${filtered ? `<button class="btn soft sm" data-act="alert">${ic("bell", 16)} Créer une alerte</button>` : ""}</div>
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
    <span class="lbl">Qualité minimale (notée par l'hôte)</span>
    <div class="cols3">${[["min_elec", "bolt", "Courant"], ["min_water", "drop", "Eau"], ["min_access", "road", "Accès"]].map(([k, i, lb]) => `<div class="field"><label>${ic(i, 15)} ${lb}</label><select name="${k}"><option value="">Indifférent</option>${[5, 7, 9].map(n => `<option value="${n}" ${+f[k] === n ? "selected" : ""}>${n}/10 et +</option>`).join("")}</select></div>`).join("")}</div>
    <label class="chk" style="margin-bottom:20px"><input type="checkbox" name="furnished" value="1" ${f.furnished ? "checked" : ""}> Meublé uniquement</label>
    <div class="row-actions"><button type="button" class="btn ghost" data-act="reset">Tout effacer</button><button class="btn">Afficher les biens</button></div></form>`);
  m.querySelector("#ff").onsubmit = e => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.target)); closeModal(); go("#/" + qs({ ...state.f, deal: "", sort: "", min_price: "", max_price: "", bedrooms: "", q: "", furnished: "", min_elec: "", min_water: "", min_access: "", ...d })); };
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
      <span>${ic("pin", 15)} ${esc(l.street)}</span>
      <span style="margin-left:auto" class="row-actions"><button class="btn ghost sm" data-fav="${l.id}" aria-pressed="${fav}">${favLabel(fav)}</button>
      ${u && !isOwner ? `<button class="btn ghost sm" data-report="${l.id}">${I.flag} Signaler</button>` : ""}</span></div>
    <div class="gal n${n}" data-act="lightbox">${imgs.slice(0, 5).map((s, i) => `<img src="${esc(s)}" alt="Photo ${i + 1} : ${esc(l.title)}" data-i="${i}" ${i ? 'loading="lazy"' : ""}>`).join("")}</div>
    <div class="dt-body"><div>
      ${l.is_demo ? '<div class="notice warn" style="margin-top:16px">Annonce de <b>démonstration</b> : le bien n\'est pas réellement disponible.</div>' : ""}
      <div class="block-sec"><a class="hostrow" href="#/hote/${l.host.id}">${avatar(l.host.avatar, l.host.name, "lg")}<div><h2 style="margin:0;font-size:18px">${cap(l.ptype)} ${l.deal === "location" ? "à louer" : "à vendre"} · hôte : ${esc(l.host.name)}</h2>
        ${l.host.verified ? `<span class="verif">${ic("shield", 15)} Identité de l'hôte vérifiée par Ndaku</span>` : '<span class="unverif">Hôte non encore vérifié : ne payez rien avant la visite.</span>'}
        ${l.host.rating ? `<br><span class="hint">${stars(Math.round(l.host.rating))} ${Number(l.host.rating).toFixed(1)} · ${l.host.reviews_count} avis sur l'hôte</span>` : ""}</div></a>
        <div class="specs" style="margin-top:14px">${l.ptype === "terrain" ? "" : `<span>${ic("bed", 18)} ${l.bedrooms} chambre${l.bedrooms > 1 ? "s" : ""}</span><span>${ic("bath", 18)} ${l.bathrooms} salle${l.bathrooms > 1 ? "s" : ""} de bain</span>`}<span>${ic("area", 18)} ${l.surface} m²</span>${l.furnished ? `<span>${ic("sofa", 18)} Meublé</span>` : ""}${l.views != null ? `<span>${ic("eye", 18)} ${l.views} vue${l.views > 1 ? "s" : ""}</span>` : ""}</div></div>
      ${l.elec_score ? `<div class="block-sec"><h2>Courant, eau et accès</h2><div class="scores">${scoreRow("bolt", "Électricité (régularité du courant)", l.elec_score)}${scoreRow("drop", "Eau (régularité et qualité)", l.water_score)}${scoreRow("road", "Accessibilité de la maison", l.access_score)}</div>
        <div class="specs" style="margin-top:12px">${l.access_type ? `<span>${ic("road", 18)} ${esc(state.meta.access_types?.[l.access_type] || l.access_type)}</span>` : ""}${l.rain_access != null ? `<span>${ic("rain", 18)} ${l.rain_access ? "Accessible en saison des pluies" : "Difficile d'accès en saison des pluies"}</span>` : ""}</div>
        <p class="hint">Notes de 1 (très mauvais) à 10 (parfait), déclarées par l'hôte. Vérifiez-les pendant la visite.</p></div>` : ""}
      <div class="block-sec"><h2>À propos de ce bien</h2><div class="desc">${esc(l.description)}</div>
        ${l.credits?.length ? `<p class="hint">Photos : ${l.credits.map(c => `${/^https:\/\/commons\.wikimedia\.org\//.test(c.page || "") ? `<a href="${esc(c.page)}" target="_blank" rel="noopener noreferrer">${esc(c.author)}</a>` : esc(c.author)} (${esc(c.license)})`).join(" · ")}, via Wikimedia Commons</p>` : ""}</div>
      ${l.amenities.length ? `<div class="block-sec"><h2>Équipements</h2><div class="am-grid">${l.amenities.map(a => `<div>${ic(AMENITY_ICON[a], 22)} ${esc(a)}</div>`).join("")}</div></div>` : ""}
      <div class="block-sec" id="slots"></div>
      <div class="block-sec" id="mkt" hidden></div>
      <div class="block-sec"><h2>Où se situe le bien</h2><p>${esc(l.street)}${l.address ? ` — <b>${esc(l.address)}</b>` : ""}</p>
        ${l.exact_location ? "" : '<p class="hint">Emplacement approximatif. L\'adresse exacte (numéro) est communiquée dès que vous contactez l\'hôte.</p>'}
        ${l.lat != null ? '<div class="mini-map" id="dmap"></div>' : ""}</div>
      <div class="block-sec"><h2>${l.reviews_count ? `${I.star} ${Number(l.rating).toFixed(1)} · ${l.reviews_count} avis vérifié${l.reviews_count > 1 ? "s" : ""} sur le bien` : "Avis sur le bien"}</h2>
        ${l.reviews.map(r => `<div class="rev">${avatar(r.avatar, r.name)}<div><div class="who">${esc(r.name)} ${stars(r.rating)}</div><time>${when(r.created_at)}${r.edited ? " · modifié" : ""}</time><div>${esc(r.comment)}</div></div></div>`).join("") || '<p class="hint">Aucun avis pour le moment.</p>'}
        ${l.can_review ? reviewForm(l.my_review, "sur ce bien") : '<p class="hint">Seuls les clients ayant échangé avec l\'hôte via Ndaku peuvent laisser un avis.</p>'}</div>
    </div>
    <aside><div class="panel"><div><div class="big">${esc("$" + fmt(l.price))}${l.deal === "location" ? " <small>/ mois</small>" : ""}</div>
        <p class="hint hide-m" style="margin:6px 0 0">${esc(l.commune)}, ${esc(l.city)}</p></div>
      ${isOwner || isAdmin ? `<div class="hide-m"><p class="hint" style="margin-top:12px">Vous gérez cette annonce.</p>${isOwner && l.status === "active" ? `<button class="btn ghost block" data-close="${l.id}">Marquer comme ${l.deal === "location" ? "loué" : "vendu"}</button>` : ""}</div>`
        : l.conversation_id ? `<a class="btn" href="#/messages/${l.conversation_id}">Ouvrir la discussion</a>` : `<button class="btn" data-visit="${l.id}">Demander une visite</button>`}
      ${isOwner && l.status !== "rejected" ? `<button class="btn ghost block hide-m" style="margin-top:10px" data-slots="${l.id}">${ic("cal", 16)} Proposer des créneaux de visite</button>` : ""}
      <div class="safe hide-m"><b>${ic("shield", 16)} Restez protégé</b><br>Ne versez jamais d'argent avant d'avoir visité. Chaque photo et chaque adresse sont uniques sur Ndaku.</div></div></aside></div></div>`;
  state.gallery = imgs;
  if (l.lat != null) {
    const map = makeMap($("#dmap"), [l.lat, l.lng], 15);
    if (l.exact_location) L.marker([l.lat, l.lng], { icon: L.divIcon({ className: "pin-wrap", html: pinHtml(l), iconSize: null }) }).addTo(map);
    else L.circle([l.lat, l.lng], { radius: 250, color: "#F26122", fillColor: "#F26122", fillOpacity: .2, weight: 2 }).addTo(map);
  }
  drawSlots(l, isOwner).catch(() => {});
  if (l.status === "active") marketCompare(l).catch(() => {});
  bindReviewForm(`/api/listings/${id}/reviews`, () => detail(id));
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
  document.body.classList.toggle("in-thread", !!cid);
  const drawInbox = async () => {
    const r = await api("/api/conversations");
    $("#convs").innerHTML = r.items.length ? r.items.map(c => `<a class="conv ${c.id === cid ? "on" : ""} ${c.unread ? "unread" : ""}" href="#/messages/${c.id}">
      ${avatar(c.other_avatar, c.other_name, "lg")}<div class="t"><b>${esc(c.other_name)}${c.other_verified ? " " + verifiedTick : ""}</b><span>${esc(c.title)}</span>
      <span>${c.last_mine ? "Vous : " : ""}${c.last_kind === "contact" ? ic("idcard", 14) + " Coordonnées partagées" : c.last_kind === "visit" ? ic("cal", 14) + " " + esc((c.last_body || "").slice(0, 70)) : esc((c.last_body || "").slice(0, 80))}</span></div>
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
    const kind = m.kind === "visit" ? `<span class="k">${ic("cal", 13)} ${meta.slot_id ? "Visite réservée" : "Demande de visite"}${meta.date ? " · " + esc(new Date(meta.date + "T12:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })) : ""}</span>`
      : m.kind === "contact" ? `<span class="k">${ic("idcard", 13)} Coordonnées partagées</span>` : "";
    return `${m.warn ? `<div class="warn">${ic("alert", 15)} Ce message parle d'argent. Ne payez jamais d'acompte, de caution ou de « frais de visite » avant d'avoir visité le bien et vérifié les documents.</div>` : ""}
      <div class="bubble ${m.mine ? "mine" : ""} ${m.kind !== "text" ? m.kind : ""}" ${m.mine ? `data-ts="${m.created_at}"` : ""}>${kind}${esc(m.body)}<time>${hour(m.created_at)} · ${when(m.created_at)}${m.mine ? '<span class="rc"></span>' : ""}</time></div>`;
  };
  th.innerHTML = `<div class="thread-h"><a class="icon-btn" href="#/messages" aria-label="Retour">${ic("back", 22)}</a>${avatar(t.other.avatar, t.other.name)}
      <div class="t"><b>${esc(t.other.name)}${t.other.verified ? " " + verifiedTick : ""}</b><a href="#/listing/${t.listing_id}">${esc(t.title)}</a></div>
      <button class="btn soft sm" data-share="${cid}" aria-label="Partager mes coordonnées">${ic("idcard", 16)}<span class="hide-sm"> Mes coordonnées</span></button><button class="icon-btn" data-convmenu="${cid}" aria-label="Plus d'options">${ic("dots", 22)}</button></div>
    <div class="msgs" id="msgs"></div>
    ${t.blocked ? `<div class="notice warn" style="margin:12px">Discussion bloquée${t.blocked_by_me ? ` · <button class="linkish" data-unblock="${cid}">Débloquer</button>` : ""}.</div>`
      : `<form class="composer" id="cmp"><textarea name="body" rows="1" maxlength="2000" placeholder="Écrire un message…" aria-label="Message" required></textarea><button class="btn send" aria-label="Envoyer">${ic("send", 18)}<span class="hide-sm">Envoyer</span></button></form>`}`;
  const box = $("#msgs");
  const append = list => { if (!list.length) return; box.insertAdjacentHTML("beforeend", list.map(bubble).join("")); lastId = list[list.length - 1].id; box.scrollTop = box.scrollHeight; };
  // Accusés de lecture : une coche = envoyé, deux coches = lu par l'autre personne ; « Vu » sous le dernier message lu.
  const receipts = seen => {
    const mine = [...box.querySelectorAll(".bubble[data-ts]")];
    mine.forEach(b => {
      const read = seen != null && +b.dataset.ts <= seen + 1;
      const rc = b.querySelector(".rc");
      rc.className = "rc" + (read ? " read" : ""); rc.innerHTML = ic(read ? "check2" : "check", 15);
      rc.title = read ? "Lu" : "Envoyé"; rc.setAttribute("aria-label", rc.title);
    });
    box.querySelector(".seen")?.remove();
    const last = mine[mine.length - 1];
    if (last && seen != null && +last.dataset.ts <= seen + 1) last.insertAdjacentHTML("afterend", `<div class="seen">Vu ${new Date(seen * 1000).toDateString() === new Date().toDateString() ? "à " + hour(seen) : "le " + when(seen)}</div>`);
  };
  append(t.messages); receipts(t.other_read_at);
  const me = state.user; if (me.unread) { me.unread = Math.max(0, me.unread - 1); renderTabbar(); }
  const cmp = $("#cmp");
  if (cmp) {
    const ta = cmp.querySelector("textarea");
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 140) + "px"; });
    ta.addEventListener("focus", () => setTimeout(() => { box.scrollTop = box.scrollHeight; }, 300));
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !matchMedia("(max-width:760px)").matches) { e.preventDefault(); cmp.requestSubmit(); } });
    cmp.onsubmit = async e => {
      e.preventDefault(); const body = ta.value.trim(); if (!body) return;
      if (needAvatar()) return;
      ta.value = ""; ta.style.height = "auto";
      try { await api(`/api/conversations/${cid}/messages`, { json: { body } }); await poll(); drawInbox(); } catch (x) { ta.value = body; toast(x.message); }
    };
  }
  const poll = async () => { const r = await api(`/api/conversations/${cid}?after=${lastId}`); append(r.messages); receipts(r.other_read_at); };
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
  const m = modal("Options de la discussion", `<div class="radio-list"><button class="btn ghost block" data-block="${cid}">${ic("ban", 16)} Bloquer cette personne</button></div>
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
  cacheFavoritesOffline(r.items);
  $("#fv").innerHTML = r.items.length ? `<p class="sec-sub">${r.items.length} bien${r.items.length > 1 ? "s" : ""} enregistré${r.items.length > 1 ? "s" : ""}.</p><div class="grid">${r.items.map(l => cardHtml(l)).join("")}</div>`
    : '<div class="empty"><h3>Aucun favori</h3><p>Touchez le cœur d\'une annonce pour la retrouver ici, sur tous vos appareils — même sans connexion.</p><a class="btn" href="#/">Explorer</a></div>';
}
async function profile() {
  const u = state.user;
  if (!u) { $("#view").innerHTML = `<div class="wrap empty"><h3>Bienvenue sur Ndaku</h3><p>Connectez-vous pour gérer vos favoris, vos messages et vos annonces.</p><div class="row-actions" style="justify-content:center"><button class="btn" data-act="login">Se connecter</button><button class="btn ghost" data-act="signup">S'inscrire</button></div></div>`; return; }
  const sec = (id, icon, title, body) => `<section class="set-sec" id="set-${id}"><h2>${ic(icon, 20)} ${title}</h2>${body}</section>`;
  const providers = u.providers.map(p => p === "apple" ? "Apple (iCloud)" : "Google");
  $("#view").innerHTML = `<div class="wrap page settings"><h1>${ic("gear", 24)} Paramètres</h1>
    <nav class="set-nav" aria-label="Sections">${[["profil", "Profil"], ["securite", "Sécurité"], ["notifications", "Notifications"], ["alertes", "Alertes"], ...(u.role === "host" ? [["verification", "Vérification"]] : []), ["compte", "Compte"]].map(([k, l]) => `<a href="#/profile" data-sec="${k}">${l}</a>`).join("")}</nav>
    ${sec("profil", "user", "Profil", `<div class="profile-head">${avatar(u.avatar, u.name, "xl")}<div><b style="font-size:18px">${esc(u.name)}</b>
        <p class="hint">${u.role === "host" ? "Hôte" : u.role === "admin" ? "Administrateur" : "Client"}${u.verified ? ` · ${verifiedTick} identité vérifiée` : ""} · ${esc(u.email)}</p><button class="btn soft sm" data-act="avatar">${ic("camera", 15)} Changer de photo</button></div></div>
      <form id="pf" class="form"><div class="field"><label for="p-n">Nom</label><input id="p-n" name="name" value="${esc(u.name)}" maxlength="80" required></div>
        <div class="field"><label for="p-t">Téléphone</label><input id="p-t" name="phone" type="tel" value="${esc(u.phone || "")}" maxlength="30" placeholder="+243 …"><span class="hint">Jamais affiché publiquement : vous le partagez vous-même dans une discussion.</span></div>
        <div class="err" id="pfErr"></div><button class="btn">Enregistrer</button></form>`)}
    ${sec("securite", "lock", "Sécurité", `<p class="hint">Connexion avec : ${[...providers, ...(u.has_password ? ["e-mail + mot de passe"] : [])].join(", ") || "—"}</p>
      <form id="pwf" class="form" autocomplete="on"><h3>${u.has_password ? "Changer de mot de passe" : "Créer un mot de passe"}</h3>
        ${u.has_password ? `<div class="field"><label for="pw-c">Mot de passe actuel</label><input id="pw-c" name="current_password" type="password" autocomplete="current-password" required maxlength="128"></div>` : `<p class="hint">Vous vous connectez avec ${esc(providers.join(" / "))}. Un mot de passe vous permet aussi de vous connecter avec votre e-mail.</p>`}
        <div class="field"><label for="pw-n">Nouveau mot de passe</label><input id="pw-n" name="new_password" type="password" autocomplete="new-password" required maxlength="128"><span class="hint">10 caractères min., majuscule, minuscule et chiffre.</span></div>
        <div class="field"><label for="pw-r">Confirmer le nouveau mot de passe</label><input id="pw-r" name="confirm" type="password" autocomplete="new-password" required maxlength="128"></div>
        <label class="chk" style="margin-bottom:12px"><input type="checkbox" id="pw-show"> Afficher les mots de passe</label>
        <div class="err" id="pwErr" role="alert"></div><button class="btn">${u.has_password ? "Changer le mot de passe" : "Créer le mot de passe"}</button></form>
      <div class="set-row"><div><b>Appareils connectés</b><br><span class="hint">Changer de mot de passe déconnecte déjà vos autres appareils.</span></div><button class="btn ghost sm" data-act="logout-all">${ic("logout", 15)} Déconnecter tous les appareils</button></div>`)}
    <section class="set-sec" id="set-notifications"><div id="notifPrefs"></div></section>
    ${sec("alertes", "bell", "Mes alertes de recherche", `<p class="hint">Faites une recherche puis touchez « Créer une alerte » : nous vous prévenons dès qu'une maison correspondante est publiée.</p><div id="alerts">${SK.rows(2)}</div>`)}
    ${u.role === "host" ? sec("verification", "shield", "Vérification d'identité", `<p class="hint">${u.verified ? "Votre identité est vérifiée : le badge apparaît sur vos annonces." : "Pièce d'identité + selfie, examinés par l'équipe Ndaku puis effacés."}</p>${u.verified ? "" : '<a class="btn soft sm" href="#/verification">Faire vérifier mon identité</a>'}`) : ""}
    ${sec("compte", "user", "Compte", `<div class="set-row"><div><b>Raccourcis</b></div><div class="row-actions">${u.role === "host" ? `<a class="btn ghost sm" href="#/host">Mes annonces</a>` : ""}<a class="btn ghost sm" href="#/favorites">Favoris</a><a class="btn ghost sm" href="#/prix">${ic("trend", 15)} Prix du marché</a></div></div>
      <div class="set-row"><div><b>Se déconnecter</b><br><span class="hint">De cet appareil uniquement.</span></div><button class="btn ghost sm" data-act="logout">${ic("logout", 15)} Se déconnecter</button></div>
      ${u.role === "admin" ? "" : `<div class="set-row danger-zone"><div><b>Supprimer mon compte</b><br><span class="hint">Définitif : profil, annonces, photos, discussions et avis sont effacés.</span></div><button class="btn danger sm" data-act="delete-account">${ic("trash", 15)} Supprimer</button></div>`}`)}
  </div>`;
  $("#view").querySelector(".set-nav").onclick = e => { const a = e.target.closest("[data-sec]"); if (!a) return; e.preventDefault(); $(`#set-${a.dataset.sec}`).scrollIntoView({ behavior: "smooth", block: "start" }); };
  $("#pf").onsubmit = async e => {
    e.preventDefault();
    try { state.user = (await api("/api/auth/me", { method: "PATCH", json: Object.fromEntries(new FormData(e.target)) })).user; renderHeader(); drawNotifPrefs(); toast("Profil enregistré"); }
    catch (x) { $("#pfErr").textContent = x.message; }
  };
  $("#pw-show").onchange = e => $("#pwf").querySelectorAll("input[type=password],input[data-pw]").forEach(i => { i.dataset.pw = 1; i.type = e.target.checked ? "text" : "password"; });
  $("#pwf").onsubmit = async e => {
    e.preventDefault(); const d = Object.fromEntries(new FormData(e.target)), err = $("#pwErr");
    if (d.new_password !== d.confirm) { err.textContent = "Les deux nouveaux mots de passe ne correspondent pas."; return; }
    const b = e.target.querySelector(".btn"); b.disabled = true;
    try {
      await api("/api/auth/password/change", { json: { current_password: d.current_password || "", new_password: d.new_password } });
      state.user = (await api("/api/auth/me")).user; toast("Mot de passe enregistré. Vos autres appareils ont été déconnectés."); profile();
    } catch (x) { err.textContent = x.message; b.disabled = false; }
  };
  drawNotifPrefs(); drawAlerts();
}
function deleteAccountModal() {
  const u = state.user;
  const m = modal("Supprimer mon compte", `<form id="dlf"><div class="notice warn">${ic("alert", 16)} Cette action est <b>définitive</b>. Votre profil, vos annonces, leurs photos, vos discussions, favoris, alertes et avis seront effacés.</div>
    ${u.has_password ? `<div class="field"><label for="dl-p">Mot de passe</label><input id="dl-p" name="password" type="password" autocomplete="current-password" required></div>`
      : `<div class="field"><label for="dl-c">Tapez <b>SUPPRIMER</b> pour confirmer</label><input id="dl-c" name="confirm" autocomplete="off" required></div>`}
    <div class="err" id="dlErr" role="alert"></div><div class="row-actions"><button class="btn danger">Supprimer définitivement</button><button type="button" class="btn ghost" data-act="close">Annuler</button></div></form>`);
  m.querySelector("#dlf").onsubmit = async e => {
    e.preventDefault();
    try { await api("/api/auth/me/delete", { json: Object.fromEntries(new FormData(e.target)) }); clearOffline(); state.user = null; state.favs = new Set(); closeModal(); renderHeader(); go("#/"); toast("Votre compte a été supprimé."); }
    catch (x) { $("#dlErr").textContent = x.message; }
  };
}

/* ============================================================================ espace hôte */
async function dashboard() {
  const u = state.user;
  if (!u) { $("#view").innerHTML = `<div class="wrap empty"><h3>Devenez hôte sur Ndaku</h3><p>Publiez vos maisons à louer ou à vendre en quelques minutes.</p><button class="btn" data-act="signup-host">Créer un compte hôte</button></div>`; return; }
  if (u.role !== "host") throw new Error("Espace réservé aux hôtes.");
  $("#view").innerHTML = `<div class="wrap page"><div class="row-actions" style="justify-content:space-between;margin-bottom:12px"><h1 style="margin:0">Mes annonces</h1><a class="btn" href="#/new">${ic("plus", 16)} Nouvelle annonce</a></div><div id="mine">${SK.rows(4)}</div></div>`;
  const [r, st] = await Promise.all([api("/api/my/listings"), api("/api/my/stats").catch(() => ({ items: [], daily: [] }))]);
  const S = Object.fromEntries(st.items.map(x => [x.id, x]));
  const sum = k => st.items.reduce((a, x) => a + (x[k] || 0), 0);
  $("#mine").innerHTML = `${u.verified ? "" : `<div class="notice ok">${ic("shield", 16)} <b>Obtenez le badge « Hôte vérifié »</b> : les clients contactent davantage les hôtes vérifiés. <a href="#/verification">Vérifier mon identité</a></div>`}
    ${r.items.length ? `<div class="tiles">${[["eye", "Vues (30 jours)", st.daily.reduce((a, d) => a + d.n, 0)], ["heart", "Favoris", sum("fav_count")], ["chat", "Contacts", sum("contacts")], ["cal", "Visites réservées", sum("visits")]].map(([i, lb, v]) => `<div class="tile">${ic(i, 18)}<b>${fmt(v)}</b><span>${lb}</span></div>`).join("")}</div>` : ""}
    ${state.auth.email_verification && !u.email_verified ? '<div class="notice warn">Confirmez votre adresse e-mail pour publier. <button type="button" class="linkish" data-act="resend">Renvoyer l\'e-mail</button></div>' : ""}
    ${u.avatar ? "" : '<div class="notice warn">Ajoutez une photo de profil pour publier. <button type="button" class="linkish" data-act="avatar">Ajouter</button></div>'}
    ${r.items.length ? `<div class="table-wrap"><table class="tbl"><thead><tr><th></th><th>Annonce</th><th>Prix</th><th>Statut</th><th title="Vues uniques">${ic("eye", 15)}</th><th title="Favoris">${ic("heart", 15)}</th><th title="Contacts">${ic("chat", 15)}</th><th title="Visites">${ic("cal", 15)}</th><th></th></tr></thead><tbody>
      ${r.items.map(l => `<tr><td>${safeUrl(l.cover) ? `<img class="thumb" src="${esc(safeUrl(l.cover))}" alt="">` : ""}</td><td><a href="#/listing/${l.id}"><b>${esc(l.title)}</b></a><br><span class="hint">${esc(l.address || "")} · ${esc(l.commune)}, ${esc(l.city)}</span>${l.status === "pending" ? `<br><span class="hint">En vérification : ${esc(l.risk_reasons.join(" · "))}</span>` : ""}</td>
        <td>${money(l)}</td><td><span class="pill ${l.status}">${{ active: "En ligne", pending: "En vérification", rejected: "Rejetée", closed: l.deal === "location" ? "Loué" : "Vendu" }[l.status]}</span></td><td>${S[l.id]?.views ?? 0}</td><td>${S[l.id]?.fav_count ?? 0}</td><td><a href="#/messages">${l.conversations}</a></td><td>${S[l.id]?.visits ?? 0}</td>
        <td><div class="row-actions">${l.status === "active" || l.status === "pending" ? `<button class="btn soft sm" data-slots="${l.id}">${ic("cal", 14)} Créneaux</button>` : ""}${l.status === "active" || l.status === "closed" ? `<button class="btn danger sm" data-del="${l.id}" aria-label="Supprimer">${ic("trash", 14)}</button>` : ""}</div></td></tr>`).join("")}</tbody></table></div>`
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
    <button type="button" data-rm="${i}" aria-label="Retirer">${ic("x", 14)}</button>
    ${p.state === "up" ? '<div class="st">Vérification…</div>' : p.state === "ok" ? `<div class="st ok">${ic("check", 12)} Unique</div>` : `<div class="why">${esc(p.reason)}</div>`}</div>`).join("");
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
    <h2 style="font-size:18px;margin:18px 0 4px">Courant, eau et accès</h2>
    <p class="hint" style="margin-top:0">Soyez honnête : ces notes sont visibles par les clients et vérifiées lors des visites. 1 = très mauvais, 10 = parfait.</p>
    ${[["elec_score", "bolt", "Qualité du courant", "Coupures fréquentes ? Tension stable ?"], ["water_score", "drop", "Qualité de l'eau", "Eau au robinet tous les jours ? Propre ?"], ["access_score", "road", "Accessibilité de la maison", "Facile à trouver et à atteindre en voiture ?"]].map(([k, i, lb, h]) =>
      `<div class="field slider"><label for="n-${k}">${ic(i, 18)} ${lb} *</label><div class="sl-row"><input id="n-${k}" name="${k}" type="range" min="1" max="10" step="1" value="5" aria-describedby="n-${k}-v"><output id="n-${k}-v" for="n-${k}">5/10 · ${SCORE_WORD(5)}</output></div><span class="hint">${h}</span></div>`).join("")}
    <div class="cols"><div class="field"><label for="n-road">${ic("road", 16)} Route menant à la maison *</label><select id="n-road" name="access_type" required><option value="">Choisir…</option>${Object.entries(M.access_types || {}).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
    <div class="field"><span class="lbl">${ic("rain", 16)} Accessible en saison des pluies ? *</span><div class="seg-pick mini"><label><input type="radio" name="rain_access" value="1"><b>Oui</b></label><label><input type="radio" name="rain_access" value="0"><b>Non</b></label></div></div></div>
    <label class="chk" style="margin-bottom:14px"><input type="checkbox" name="furnished" value="1"> ${ic("sofa", 16)} Meublé</label>
    <div class="field"><span class="lbl">Équipements</span><div class="tags">${M.amenities.map(a => `<label class="tag"><input type="checkbox" name="amenities" value="${esc(a)}">${ic(AMENITY_ICON[a], 16)} ${esc(a)}</label>`).join("")}</div></div>
    <div class="field"><span class="lbl">Photos (${M.min_images} à ${M.max_images}) — uniques, prises par vous</span>
      <label class="drop" id="drop" for="n-files">Glissez vos photos ici ou <u>parcourez</u><br><span class="hint">JPEG, PNG ou WebP · min. 480×320 · chaque photo est comparée à toutes les annonces existantes</span></label>
      <input id="n-files" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden><div class="previews" id="pvs"></div></div>
    <div class="err" id="nerr" role="alert"></div><button class="btn" id="nsub">Publier l'annonce</button></form></div>`;
  // -------- localisation + épingle
  let loc = {}, pin = null;
  const map = makeMap($("#pinMap"));
  const setPin = ll => {
    if (pin) pin.setLatLng(ll); else { pin = L.marker(ll, { draggable: true }).addTo(map); pin.on("dragend", () => { $("#pinHint").innerHTML = `${ic("checkc", 15)} Position enregistrée`; }); }
    $("#pinHint").innerHTML = `${ic("checkc", 15)} Position enregistrée (déplacez l'épingle si besoin)`;
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
  $("#nf").addEventListener("input", e => { if (e.target.type === "range") $(`#${e.target.id}-v`).textContent = `${e.target.value}/10 · ${SCORE_WORD(+e.target.value)}`; });
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
    if (!d.access_type || !fd.has("rain_access")) { err.textContent = "Indiquez le type de route et l'accès en saison des pluies."; return; }
    for (const k of ["elec_score", "water_score", "access_score"]) d[k] = +d[k];
    d.rain_access = d.rain_access === "1";
    const ll = pin.getLatLng();
    Object.assign(d, { amenities: fd.getAll("amenities"), furnished: fd.has("furnished"), image_ids: ok.map(p => p.id),
      commune_id: loc.commune_id, quartier_id: loc.quartier_id || null, avenue_id: loc.avenue_id, lat: ll.lat, lng: ll.lng });
    const btn = $("#nsub"); btn.disabled = true; btn.textContent = "Contrôle anti-fraude en cours…";
    try {
      const r = await api("/api/listings", { json: d });
      photos = [];
      toast(r.status === "active" ? "Annonce publiée" : "Annonce reçue : vérification par la modération");
      go("#/host");
    } catch (x) { err.textContent = x.message; btn.disabled = false; btn.textContent = "Publier l'annonce"; }
  };
}

/* ============================================================================= modération */
const ADMIN_TABS = [["queue", "Annonces en attente"], ["kyc", "Identités"], ["reports", "Signalements"], ["users", "Utilisateurs signalés"], ["places", "Lieux proposés"], ["osm", "Référentiel (OSM)"]];
async function admin(tab) {
  if (state.user?.role !== "admin") throw new Error("Espace réservé à la modération.");
  $("#view").innerHTML = `<div class="wrap page"><h1>Modération</h1><div class="tabs">${ADMIN_TABS.map(([k, l]) => `<button class="${k === tab ? "on" : ""}" data-tab="${k}">${l}</button>`).join("")}</div><div id="adm">${SK.rows(5)}</div></div>`;
  const box = $("#adm");
  if (tab === "queue") {
    const r = await api("/api/admin/queue");
    box.innerHTML = `<div class="notice ok"><b>Annonces de démonstration</b> — importe des annonces illustrées par de vraies photos de maisons de RDC (Wikimedia Commons, licences libres, crédits affichés). Elles arrivent ici : vérifiez chaque photo avant d'approuver.
      <div class="row-actions" style="margin-top:10px"><button class="btn sm" data-demo="commons">Importer (photos réelles)</button><span class="hint" id="demoSt"></span></div></div>
      ${r.items.map(l => `<div class="block-sec"><div class="row-actions" style="align-items:flex-start;justify-content:space-between"><div style="display:flex;gap:14px">${safeUrl(l.cover) ? `<img class="thumb" src="${esc(safeUrl(l.cover))}" alt="">` : ""}<div><a href="#/listing/${l.id}"><b>${esc(l.title)}</b></a>${l.is_demo ? ' <span class="pill">Démo</span>' : ""}<br><span class="hint">Hôte : ${esc(l.host)} ${l.host_verified ? verifiedTick : `<button class="linkish" data-verify="${l.host_id}">vérifier l'hôte</button>`} · ${money(l)} · ${esc(l.commune)}</span>
        ${l.risk_reasons.length || l.reports.length ? `<div class="risk" style="margin-top:8px"><b>Risque ${l.risk_score}</b><ul style="margin:4px 0 0">${l.risk_reasons.map(x => `<li>${esc(x)}</li>`).join("")}${l.reports.map(x => `<li>Signalement : ${esc(x)}</li>`).join("")}</ul></div>` : ""}</div></div>
        <div class="row-actions"><button class="btn sm" data-decide="approve" data-id="${l.id}">Approuver</button><button class="btn danger sm" data-decide="reject" data-id="${l.id}">Rejeter</button></div></div></div>`).join("") || '<div class="empty"><h3>${ic("checkc", 22)} File vide</h3></div>'}`;
  } else if (tab === "kyc") {
    const r = await api("/api/admin/verifications");
    box.innerHTML = r.items.map(v => `<div class="block-sec kyc"><div class="row-actions" style="justify-content:space-between;align-items:flex-start">
        <div class="hostrow">${avatar(v.avatar, v.name, "lg")}<div><b>${esc(v.name)}</b><br><span class="hint">${esc(v.email)} · ${esc(r.id_types[v.id_type] || v.id_type)} · ${v.listings} annonce(s) · ${when(v.created_at)}</span></div></div>
        <div class="row-actions"><button class="btn sm" data-kyc="approve" data-id="${v.id}">Approuver</button><button class="btn danger sm" data-kyc="reject" data-id="${v.id}">Refuser</button></div></div>
      <div class="kyc-docs"><figure><img src="/api/admin/verifications/${v.id}/id_doc" alt="Pièce d'identité" loading="lazy"><figcaption>Pièce d'identité</figcaption></figure><figure><img src="/api/admin/verifications/${v.id}/selfie" alt="Selfie" loading="lazy"><figcaption>Selfie avec la pièce</figcaption></figure></div>
      <p class="hint">Comparez le visage du selfie, de la pièce et de la photo de profil. Les documents sont effacés dès votre décision.</p></div>`).join("") || `<div class="empty"><h3>${ic("checkc", 22)} Aucune demande en attente</h3></div>`;
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

/* ============================================================== v5 : confiance et services */
const scoreRow = (i, label, n) => `<div class="score"><span class="s-l">${ic(i, 18)} ${label}</span>
  <span class="meter" role="meter" aria-valuemin="1" aria-valuemax="10" aria-valuenow="${n}" aria-label="${esc(label)}"><i style="width:${n * 10}%"></i></span>
  <b>${n}/10</b><span class="s-w">${SCORE_WORD(n)}</span></div>`;
const dayLabel = ts => new Date(ts * 1000).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
const slotWhen = s => `${dayLabel(s.starts_at)} à ${hour(s.starts_at)}`;

/* ------------------------------------------------------------- agenda de visites */
async function drawSlots(l, isOwner) {
  const box = $("#slots"); if (!box || (l.status !== "active" && !isOwner)) { box && box.remove(); return; }
  const r = await api(`/api/listings/${l.id}/slots`);
  const mine = r.items.find(s => s.mine), open = r.items.filter(s => s.status === "open");
  let html = `<h2>${ic("cal", 20)} Visites</h2>`;
  if (isOwner) {
    html += r.items.length ? `<ul class="slot-list">${r.items.map(s => `<li><span>${ic("clock", 15)} ${slotWhen(s)}</span>${s.status === "booked" ? `<span class="pill active">Réservé par ${esc(s.booker || "un client")}</span>${s.conversation_id ? ` <a href="#/messages/${s.conversation_id}">Discussion</a>` : ""}` : '<span class="pill">Libre</span>'}
        <button class="linkish" data-slotcancel="${s.id}" data-owner="1">Supprimer</button></li>`).join("")}</ul>` : '<p class="hint">Aucun créneau proposé. Proposez des horaires : les clients réservent en un clic.</p>';
    html += `<button class="btn soft sm" data-slots="${l.id}">${ic("plus", 15)} Proposer des créneaux</button>`;
  } else if (mine) {
    html += `<div class="notice ok">${ic("checkc", 16)} Votre visite est réservée le <b>${slotWhen(mine)}</b>. <button class="linkish" data-slotcancel="${mine.id}">Annuler</button></div>`;
  } else if (open.length) {
    const days = {};
    open.forEach(s => { (days[dayLabel(s.starts_at)] ||= []).push(s); });
    html += `<p class="hint">Choisissez un créneau proposé par l'hôte : la visite est confirmée immédiatement.</p>` + Object.entries(days).slice(0, 7).map(([d, list]) =>
      `<div class="slot-day"><b>${esc(cap(d))}</b><div class="slot-chips">${list.map(s => `<button class="chip-btn" data-book="${s.id}" data-when="${esc(slotWhen(s))}">${hour(s.starts_at)}</button>`).join("")}</div></div>`).join("");
  } else {
    html += `<p class="hint">L'hôte n'a pas encore proposé de créneaux. Demandez une visite par message.</p>`;
  }
  box.innerHTML = html;
}
function slotsModal(lid) {
  const today = new Date(Date.now() + 864e5).toISOString().slice(0, 10);
  const hours = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"];
  const m = modal("Proposer des créneaux de visite", `<form id="slf"><p class="hint">Choisissez un jour et les heures auxquelles vous pouvez faire visiter. Répétez pour d'autres jours.</p>
    <div class="cols"><div class="field"><label for="sl-d">Jour</label><input id="sl-d" type="date" name="day" min="${new Date().toISOString().slice(0, 10)}" value="${today}" required></div>
    <div class="field"><label for="sl-m">Durée</label><select id="sl-m" name="duration"><option value="30">30 min</option><option value="45">45 min</option><option value="60" selected>1 h</option></select></div></div>
    <span class="lbl">Heures</span><div class="tags">${hours.map(h => `<label class="tag"><input type="checkbox" name="h" value="${h}">${ic("clock", 14)} ${h}</label>`).join("")}</div>
    <div class="err" id="slErr" role="alert"></div><button class="btn block" style="margin-top:14px">Ajouter ces créneaux</button></form>`);
  m.querySelector("#slf").addEventListener("change", e => { if (e.target.closest(".tag")) e.target.closest(".tag").classList.toggle("on", e.target.checked); });
  m.querySelector("#slf").onsubmit = async e => {
    e.preventDefault(); const fd = new FormData(e.target), hs = fd.getAll("h");
    if (!hs.length) { $("#slErr").textContent = "Cochez au moins une heure."; return; }
    const starts = hs.map(h => new Date(`${fd.get("day")}T${h}:00`).toISOString());
    try { const r = await api(`/api/listings/${lid}/slots`, { json: { starts, duration: +fd.get("duration") } }); closeModal(); toast(`${r.created} créneau(x) ajouté(s)`); route(); }
    catch (x) { $("#slErr").textContent = x.message; }
  };
}
function bookModal(sid, whenTxt) {
  if (needLogin() || needAvatar()) return;
  const m = modal("Réserver une visite", `<form id="bkf"><p>${ic("cal", 16)} <b>${esc(cap(whenTxt))}</b></p>
    <div class="field"><label for="bk-m">Message pour l'hôte (facultatif)</label><textarea id="bk-m" name="message" maxlength="500" style="min-height:70px" placeholder="Ex. Je viendrai avec mon épouse."></textarea></div>
    <div class="safe">${ic("shield", 15)} Ne payez jamais de « frais de visite » : une visite sur Ndaku est gratuite.</div>
    <div class="err" id="bkErr" role="alert"></div><button class="btn block" style="margin-top:12px">Confirmer la visite</button></form>`);
  m.querySelector("#bkf").onsubmit = async e => {
    e.preventDefault(); const b = e.target.querySelector(".btn"); b.disabled = true;
    try { const r = await api(`/api/slots/${sid}/book`, { json: Object.fromEntries(new FormData(e.target)) }); closeModal(); toast("Visite réservée : l'hôte est prévenu."); go(`#/messages/${r.conversation_id}`); }
    catch (x) { $("#bkErr").textContent = x.message; b.disabled = false; }
  };
}

/* ----------------------------------------------------------------- prix du marché */
async function marketCompare(l) {
  const box = $("#mkt"); if (!box || !l.commune_id) return;
  const r = await api(`/api/stats/prices?commune_id=${l.commune_id}&deal=${l.deal}`);
  const c = r.current, rent = l.deal === "location";
  const mine = rent ? l.price : l.price / (l.surface || 1);
  let html = `<h2>${ic("trend", 20)} Prix à ${esc(l.commune)}</h2>`;
  if (c?.n >= 3 && c.median) {
    const d = Math.round((mine / c.median - 1) * 100);
    html += `<p>${rent ? "Loyer médian" : "Prix médian au m²"} : <b>$${fmt(Math.round(c.median))}${rent ? " / mois" : " / m²"}</b> <span class="hint">(${c.n} annonces en ligne)</span></p>
      <p>Ce bien est <b>${Math.abs(d) < 5 ? "dans la moyenne" : d > 0 ? `${d} % au-dessus` : `${-d} % en dessous`}</b>${Math.abs(d) < 5 ? "" : " de la médiane"}.${d < -40 ? ` <span class="unverif">${ic("alert", 14)} Prix très bas : méfiez-vous des arnaques.</span>` : ""}</p>`;
  } else html += `<p class="hint">Pas encore assez d'annonces à ${esc(l.commune)} pour comparer les prix.</p>`;
  html += `<a class="linkish" href="#/prix?city_id=${l.city_id}&deal=${l.deal}">Voir les prix par commune</a>`;
  box.innerHTML = html; box.hidden = false;
}
const tipEl = () => $("#ctip") || Object.assign(document.body.appendChild(document.createElement("div")), { id: "ctip", className: "ctip" });
function chartTip(e, html) { const t = tipEl(); if (!html) { t.style.opacity = 0; return; } t.textContent = html; t.style.opacity = 1; t.style.left = Math.min(e.clientX + 14, innerWidth - t.offsetWidth - 8) + "px"; t.style.top = (e.clientY - t.offsetHeight - 12) + "px"; }
function barChart(rows, unit) {
  const max = Math.max(...rows.map(r => r.median));
  return `<div class="hbars" role="list">${rows.map(r => `<div class="hb" role="listitem" data-tip="${esc(r.commune)} · $${fmt(Math.round(r.median))} ${unit} · ${r.n} annonces">
    <span class="hb-l">${esc(r.commune)}</span><span class="hb-t"><i style="width:${Math.max(2, r.median / max * 100)}%"></i><b>$${fmt(Math.round(r.median))}</b></span></div>`).join("")}</div>`;
}
function lineChart(pts, unit) {
  const W = 640, H = 220, L = 52, R = 16, T = 14, B = 28;
  const vals = pts.map(p => p.median), hi = Math.max(...vals) * 1.1, lo = 0;
  const step = Math.pow(10, Math.floor(Math.log10(hi || 1))), top = Math.ceil(hi / step) * step;
  const x = i => L + (pts.length < 2 ? (W - L - R) / 2 : i * (W - L - R) / (pts.length - 1)), y = v => T + (H - T - B) * (1 - (v - lo) / (top - lo));
  const ticks = [0, top / 2, top], kfmt = v => v >= 1000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0) + "K" : v;
  const mlabel = mth => new Date(mth + "-15").toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
  return `<svg class="lchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Évolution du prix médian (${unit})">
    ${ticks.map(t => `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" class="grid"/><text x="${L - 8}" y="${y(t) + 4}" text-anchor="end">$${kfmt(t)}</text>`).join("")}
    ${pts.map((p, i) => (pts.length <= 6 || i % 2 === 0 || i === pts.length - 1) ? `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${mlabel(p.month)}</text>` : "").join("")}
    <polyline points="${pts.map((p, i) => `${x(i)},${y(p.median)}`).join(" ")}" class="ln"/>
    ${pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.median)}" r="5" class="pt"/><rect x="${x(i) - 16}" y="${T}" width="32" height="${H - T - B}" class="hit" data-tip="${esc(mlabel(p.month))} · $${fmt(Math.round(p.median))} ${unit} · ${p.n} annonces"/>`).join("")}
  </svg>`;
}
async function pricesPage(params) {
  const view = $("#view");
  let deal = params.deal === "vente" ? "vente" : "location", city = +params.city_id || null;
  const provs = await children(null);
  if (!city) {
    const kin = provs.find(p => p.name === "Kinshasa");
    city = kin ? (await children(kin.id)).find(c => c.kind === "city")?.id : null;
  }
  view.innerHTML = `<div class="wrap page" style="max-width:860px"><h1>${ic("trend", 24)} Prix du marché</h1>
    <p class="hint">Médianes calculées sur les annonces réelles publiées sur Ndaku (hors démonstration). La médiane résiste aux prix extrêmes.</p>
    <div class="cols"><div class="field"><label for="pp-p">Province</label><select id="pp-p">${provs.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select></div>
    <div class="field"><label for="pp-c">Ville</label><select id="pp-c"></select></div></div>
    <div class="tabs"><button class="${deal === "location" ? "on" : ""}" data-deal="location">Loyers</button><button class="${deal === "vente" ? "on" : ""}" data-deal="vente">Ventes (prix au m²)</button></div>
    <div id="pz">${SK.rows(3)}</div></div>`;
  const pSel = $("#pp-p"), cSel = $("#pp-c");
  const fillCities = async pid => { const cs = (await children(pid)).filter(c => c.kind === "city"); cSel.innerHTML = cs.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join(""); return cs; };
  let provId = provs[0]?.id;
  for (const p of provs) { if ((await children(p.id)).some(c => c.id === city)) { provId = p.id; break; } }
  if (provId) { pSel.value = provId; await fillCities(provId); if (city) cSel.value = city; }
  const draw = async () => {
    const cid = +cSel.value; if (!cid) return;
    const name = cSel.selectedOptions[0]?.textContent || "";
    $("#pz").innerHTML = SK.rows(3);
    const r = await api(`/api/stats/prices?city_id=${cid}&deal=${deal}`), unit = deal === "location" ? "/ mois" : "/ m²";
    const c = r.current;
    if (!c?.n) { $("#pz").innerHTML = `<div class="empty"><h3>Pas encore de données à ${esc(name)}</h3><p>Les médianes apparaîtront dès que des annonces réelles y seront publiées.</p></div>`; return; }
    $("#pz").innerHTML = `<div class="tiles"><div class="tile">${ic("trend", 18)}<b>$${fmt(Math.round(c.median))}</b><span>${deal === "location" ? "Loyer médian" : "Prix médian au m²"} à ${esc(name)}</span></div><div class="tile">${ic("home", 18)}<b>${c.n}</b><span>annonces en ligne</span></div></div>
      ${r.by_commune.length ? `<h2 class="chart-t">${deal === "location" ? "Loyer médian" : "Prix médian au m²"} par commune <span class="hint">(${unit}, communes avec au moins 2 annonces)</span></h2>${barChart(r.by_commune, unit)}` : ""}
      ${r.monthly.length >= 2 ? `<h2 class="chart-t">Évolution sur 12 mois <span class="hint">(${unit})</span></h2>${lineChart(r.monthly, unit)}` : ""}
      <details class="tbl-view"><summary>Voir les données en tableau</summary><div class="table-wrap"><table class="tbl"><thead><tr><th>Commune / mois</th><th>Médiane</th><th>Annonces</th></tr></thead><tbody>
        ${r.by_commune.map(x => `<tr><td>${esc(x.commune)}</td><td>$${fmt(Math.round(x.median))}</td><td>${x.n}</td></tr>`).join("")}${r.monthly.map(x => `<tr><td>${esc(x.month)}</td><td>$${fmt(Math.round(x.median))}</td><td>${x.n}</td></tr>`).join("")}</tbody></table></div></details>`;
  };
  pSel.onchange = async () => { await fillCities(+pSel.value); draw(); };
  cSel.onchange = draw;
  $("#view").querySelector(".tabs").onclick = e => { const b = e.target.closest("[data-deal]"); if (!b) return; deal = b.dataset.deal; $("#view").querySelectorAll("[data-deal]").forEach(x => x.classList.toggle("on", x === b)); draw(); };
  const pz = $("#pz");
  pz.addEventListener("mousemove", e => { const h = e.target.closest("[data-tip]"); chartTip(e, h && h.dataset.tip); });
  pz.addEventListener("mouseleave", e => chartTip(e, ""));
  cleanup.push(() => chartTip({}, ""));
  await draw();
}

/* ----------------------------------------------------------------- alertes */
function alertModal() {
  if (needLogin()) return;
  const f = state.f;
  const parts = [f.ptype ? cap(f.ptype) : "Bien", f.bedrooms ? `${f.bedrooms} ch. et +` : "", state.placeName ? `à ${state.placeName}` : "", f.max_price ? `≤ $${fmt(f.max_price)}` : ""].filter(Boolean);
  const m = modal("Créer une alerte", `<form id="alf"><p>Nous vous prévenons (notification, et e-mail/SMS selon vos préférences) dès qu'une maison correspondant à cette recherche est publiée.</p>
    <div class="field"><label for="al-l">Nom de l'alerte</label><input id="al-l" name="label" maxlength="120" value="${esc(parts.join(" "))}"></div>
    <div class="err" id="alErr" role="alert"></div><button class="btn block">${ic("bell", 16)} Créer l'alerte</button></form>`);
  m.querySelector("#alf").onsubmit = async e => {
    e.preventDefault();
    const d = { label: e.target.label.value };
    ["deal", "ptype", "province_id", "city_id", "commune_id", "quartier_id", "min_price", "max_price", "bedrooms", "min_elec", "min_water"].forEach(k => { if (f[k]) d[k] = f[k]; });
    if (f.furnished) d.furnished = true;
    try { await api("/api/alerts", { json: d }); closeModal(); toast("Alerte créée : vous serez prévenu."); } catch (x) { $("#alErr").textContent = x.message; }
  };
}
async function drawAlerts() {
  const box = $("#alerts"); if (!box) return;
  const r = await api("/api/alerts").catch(() => ({ items: [] }));
  box.innerHTML = r.items.length ? `<ul class="slot-list">${r.items.map(a => `<li><span>${ic("bell", 15)} <b>${esc(a.label)}</b> <span class="hint">${[a.deal === "vente" ? "Achat" : a.deal === "location" ? "Location" : "", a.min_bedrooms ? a.min_bedrooms + " ch. et +" : "", a.max_price ? "≤ $" + fmt(a.max_price) : "", a.min_elec ? "courant ≥ " + a.min_elec : "", a.min_water ? "eau ≥ " + a.min_water : ""].filter(Boolean).join(" · ")}</span></span>
    <button class="linkish" data-delalert="${a.id}">Supprimer</button></li>`).join("")}</ul>` : '<p class="hint">Aucune alerte.</p>';
}

/* ----------------------------------------------------------------- notifications */
function drawNotifPrefs() {
  const box = $("#notifPrefs"), u = state.user; if (!box || !u) return;
  const ch = state.auth.notify_channels || {}, n = u.notify || {};
  const row = (k, i, label, avail, why) => `<label class="chk ${avail ? "" : "off"}"><input type="checkbox" name="${k}" ${n[k] ? "checked" : ""} ${avail ? "" : "disabled"}> ${ic(i, 16)} ${label}${why ? ` <span class="hint">${why}</span>` : ""}</label>`;
  const needPhone = !u.phone ? "(ajoutez votre numéro ci-dessus)" : !u.phone_verified ? "" : "";
  box.innerHTML = `<h2>${ic("bell", 20)} Notifications</h2><p><b>Être prévenu des nouveaux messages, visites et alertes</b></p>
    <p class="hint">Les notifications n'incluent jamais le contenu de vos messages, seulement une invitation à ouvrir Ndaku.</p>
    <form id="npf" class="notif-prefs">${row("email", "send", `E-mail (${esc(u.email)})`, true)}
      ${row("sms", "chat", "SMS", ch.sms && u.phone_verified, !ch.sms ? "(bientôt disponible)" : needPhone)}
      ${row("whatsapp", "chat", "WhatsApp", ch.whatsapp && u.phone_verified, !ch.whatsapp ? "(bientôt disponible)" : needPhone)}
      ${(ch.sms || ch.whatsapp) && u.phone && !u.phone_verified ? `<button type="button" class="btn soft sm" data-act="phone">Confirmer mon numéro par SMS</button>` : ""}</form>`;
  box.querySelector("#npf").onchange = async e => {
    try { state.user = (await api("/api/auth/me", { method: "PATCH", json: { notify: { [e.target.name]: e.target.checked } } })).user; toast("Préférences enregistrées"); }
    catch (x) { e.target.checked = !e.target.checked; toast(x.message); }
  };
}
async function phoneModal() {
  try { await api("/api/auth/me/phone/code", { method: "POST" }); } catch (x) { return toast(x.message); }
  const m = modal("Confirmer mon numéro", `<form id="phf"><p>Un code à 6 chiffres a été envoyé par SMS au ${esc(state.user.phone)}.</p>
    <div class="field"><label for="ph-c">Code</label><input id="ph-c" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required></div>
    <div class="err" id="phErr" role="alert"></div><button class="btn block">Confirmer</button></form>`);
  m.querySelector("#phf").onsubmit = async e => {
    e.preventDefault();
    try { state.user = (await api("/api/auth/me/phone/verify", { json: { code: e.target.code.value.trim() } })).user; closeModal(); drawNotifPrefs(); toast("Numéro confirmé"); }
    catch (x) { $("#phErr").textContent = x.message; }
  };
}
const NOTIF_ICON = { message: "chat", alert: "bell", visit: "cal", kyc: "shield", review: "star", listing: "home" };
async function notificationsPage() {
  if (!state.user) throw Object.assign(new Error("Connexion requise"), { status: 401 });
  $("#view").innerHTML = `<div class="wrap page" style="max-width:720px"><h1>Notifications</h1><div id="nl">${SK.rows(5)}</div></div>`;
  const r = await api("/api/notifications");
  $("#nl").innerHTML = r.items.length ? r.items.map(n => `<a class="notif ${n.read ? "" : "unread"}" href="${/^#\/[\w/?=&-]*$/.test(n.link) ? esc(n.link) : "#/"}">
      <span class="n-ic">${ic(NOTIF_ICON[n.kind] || "bell", 20)}</span><span class="t"><b>${esc(n.title)}</b>${n.body ? `<span>${esc(n.body)}</span>` : ""}<time>${when(n.created_at)} · ${hour(n.created_at)}</time></span></a>`).join("")
    : `<div class="empty"><h3>${ic("bell", 22)} Rien de nouveau</h3><p>Messages, visites et alertes de recherche apparaîtront ici.</p></div>`;
  if (r.items.some(n => !n.read)) { api("/api/notifications/read", { method: "POST" }).catch(() => {}); state.user.notif_unread = 0; renderHeader(); }
}

/* ----------------------------------------------------------------- profil public de l'hôte */
async function hostPage(id) {
  $("#view").innerHTML = `<div class="wrap page">${SK.rows(1)}${SK.cards(3)}</div>`;
  const h = await api(`/api/hosts/${id}`);
  $("#view").innerHTML = `<div class="wrap page"><div class="profile-head">${avatar(h.avatar, h.name, "xl")}<div><h1 style="margin:0">${esc(h.name)}</h1>
      <p class="hint">Hôte depuis ${new Date(h.since * 1000).toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</p>
      ${h.verified ? `<span class="verif">${ic("shield", 15)} Identité vérifiée par Ndaku</span>` : '<span class="unverif">Identité non vérifiée</span>'}
      <p>${h.rating ? `${stars(Math.round(h.rating))} <b>${Number(h.rating).toFixed(1)}</b> · ${h.reviews_count} avis` : '<span class="hint">Pas encore d\'avis</span>'}</p></div></div>
    <h2 class="sec-title">Annonces de ${esc(h.name)}</h2>${h.listings.length ? `<div class="grid">${h.listings.map(l => cardHtml(l)).join("")}</div>` : '<p class="hint">Aucune annonce en ligne.</p>'}
    <div class="block-sec" style="max-width:720px"><h2>Avis sur l'hôte</h2>
      ${h.reviews.map(r => `<div class="rev">${avatar(r.avatar, r.name)}<div><div class="who">${esc(r.name)} ${stars(r.rating)}</div><time>${when(r.created_at)}${r.edited ? " · modifié" : ""}</time><div>${esc(r.comment)}</div></div></div>`).join("") || '<p class="hint">Aucun avis pour le moment.</p>'}
      ${h.can_review ? reviewForm(h.my_review, "sur cet hôte (ponctualité, honnêteté, réactivité)")
        : '<p class="hint">Seuls les clients ayant échangé avec l\'hôte via Ndaku peuvent le noter.</p>'}</div></div>`;
  bindReviewForm(`/api/hosts/${id}/reviews`, () => hostPage(id));
}

/* ----------------------------------------------------------------- vérification d'identité */
async function kycPage() {
  const u = state.user;
  if (!u) throw Object.assign(new Error("Connexion requise"), { status: 401 });
  if (u.role !== "host") throw new Error("La vérification d'identité est réservée aux hôtes.");
  $("#view").innerHTML = `<div class="wrap page" style="max-width:640px">${SK.rows(3)}</div>`;
  const r = await api("/api/verification");
  const req = r.request, head = `<h1>${ic("shield", 24)} Vérification d'identité</h1>`;
  if (r.verified) { $("#view").innerHTML = `<div class="wrap page" style="max-width:640px">${head}<div class="notice ok">${ic("checkc", 16)} Votre identité est vérifiée. Le badge « Hôte vérifié » apparaît sur vos annonces.</div></div>`; return; }
  if (req?.status === "pending") { $("#view").innerHTML = `<div class="wrap page" style="max-width:640px">${head}<div class="notice warn">${ic("clock", 16)} Demande envoyée le ${when(req.created_at)} : en cours d'examen par l'équipe Ndaku. Vous serez notifié.</div></div>`; return; }
  $("#view").innerHTML = `<div class="wrap page" style="max-width:640px">${head}
    ${req?.status === "rejected" ? `<div class="notice warn">${ic("alert", 16)} Demande précédente refusée${req.note ? ` : ${esc(req.note)}` : ""}. Vous pouvez en envoyer une nouvelle.</div>` : ""}
    <p>Le badge « Hôte vérifié » rassure les clients et fait remonter vos annonces. Il nous faut :</p>
    <form id="kf" class="form"><div class="field"><label for="k-t">Type de pièce</label><select id="k-t" name="id_type" required>${Object.entries(r.id_types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
      <div class="field"><label for="k-d">${ic("idcard", 16)} Photo de la pièce (recto, lisible, sans reflet)</label><input id="k-d" name="id_doc" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" required></div>
      <div class="field"><label for="k-s">${ic("camera", 16)} Selfie en tenant la pièce près de votre visage</label><input id="k-s" name="selfie" type="file" accept="image/jpeg,image/png,image/webp" capture="user" required></div>
      <div class="safe">${ic("shield", 15)} Vos documents ne sont jamais publiés : seule l'équipe de modération les voit, et ils sont <b>effacés dès la décision</b> (ou après 30 jours sans examen).</div>
      <div class="err" id="kErr" role="alert"></div><button class="btn" style="margin-top:14px">Envoyer pour vérification</button></form></div>`;
  $("#kf").onsubmit = async e => {
    e.preventDefault(); if (needAvatar()) return;
    const f = e.target, b = f.querySelector(".btn");
    if (!f.id_doc.files[0] || !f.selfie.files[0]) { $("#kErr").textContent = "Ajoutez les deux photos."; return; }
    b.disabled = true; b.textContent = "Envoi…";
    try {
      const fd = new FormData(); fd.append("id_type", f.id_type.value);
      fd.append("id_doc", await shrink(f.id_doc.files[0], 1600)); fd.append("selfie", await shrink(f.selfie.files[0], 1600));
      await api("/api/verification", { method: "POST", body: fd }); toast("Demande envoyée"); kycPage();
    } catch (x) { $("#kErr").textContent = x.message; b.disabled = false; b.textContent = "Envoyer pour vérification"; }
  };
}

/* ----------------------------------------------------------------- hors-ligne (favoris) */
function clearOffline() { navigator.serviceWorker?.controller?.postMessage("clear"); }
async function cacheFavoritesOffline(items) {
  // Préchargement des fiches des favoris pour une consultation sans connexion (non compté comme une vue).
  if (!navigator.serviceWorker?.controller || !navigator.onLine) return;
  for (const l of items.slice(0, 30)) await fetch(`/api/listings/${l.id}`, { headers: { "X-Ndaku": "1", "X-Ndaku-Offline": "1" } }).catch(() => {});
}
function offlineBanner() {
  let b = $("#offline");
  if (navigator.onLine) { b && b.remove(); return; }
  if (!b) { b = document.createElement("div"); b.id = "offline"; b.className = "offline"; document.body.prepend(b); }
  b.innerHTML = `${ic("wifioff", 16)} Hors ligne : vos favoris restent consultables. <a href="#/favorites">Mes favoris</a>`;
}
addEventListener("online", offlineBanner); addEventListener("offline", offlineBanner);
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
/* hauteur réelle visible (clavier mobile ouvert) pour garder la zone de saisie au-dessus du clavier */
if (window.visualViewport) {
  const setVh = () => document.documentElement.style.setProperty("--vvh", visualViewport.height + "px");
  visualViewport.addEventListener("resize", setVh); setVh();
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
  if (a === "alert") return alertModal();
  if (a === "phone") return phoneModal();
  if (a === "delete-account") return deleteAccountModal();
  if (a === "resend") return act("/api/auth/resend-verification", undefined, "E-mail de confirmation renvoyé.");
  if (a === "logout" || a === "logout-all") { await api(a === "logout" ? "/api/auth/logout" : "/api/auth/logout-all", { method: "POST" }).catch(() => {}); clearOffline(); state.user = null; state.favs = new Set(); renderHeader(); go("#/"); return toast("À bientôt !"); }
  const tab = t.closest("[data-tab]"); if (tab) return go(`#/admin?tab=${tab.dataset.tab}`);
  const cat = t.closest("[data-cat]"); if (cat) return go("#/" + qs({ ...state.f, ptype: cat.dataset.cat }));
  const fav = t.closest("[data-fav]");
  if (fav) {
    e.preventDefault(); e.stopPropagation();
    if (needLogin()) return;
    try {
      const id = +fav.dataset.fav, r = await api(`/api/listings/${id}/favorite`, { method: "POST" });
      r.favorite ? state.favs.add(id) : state.favs.delete(id);
      document.querySelectorAll(`[data-fav="${id}"]`).forEach(el => { el.classList.toggle("on", r.favorite); el.setAttribute("aria-pressed", r.favorite); if (el.matches(".btn")) el.innerHTML = favLabel(r.favorite); });
      toast(r.favorite ? "Ajouté à vos favoris" : "Retiré de vos favoris");
      if (parse().path === "/favorites" && !r.favorite) route();
    } catch (x) { toast(x.message); }
    return;
  }
  const visit = t.closest("[data-visit]"); if (visit) return visitModal(+visit.dataset.visit);
  const sl = t.closest("[data-slots]"); if (sl) return slotsModal(+sl.dataset.slots);
  const bk = t.closest("[data-book]"); if (bk) return bookModal(+bk.dataset.book, bk.dataset.when);
  const sc = t.closest("[data-slotcancel]"); if (sc) { if (confirm(sc.dataset.owner ? "Supprimer ce créneau ? Si un client l'a réservé, il sera prévenu." : "Annuler votre visite ?")) act(`/api/slots/${sc.dataset.slotcancel}/cancel`, undefined, "Créneau annulé."); return; }
  const da = t.closest("[data-delalert]"); if (da) { try { await api(`/api/alerts/${da.dataset.delalert}`, { method: "DELETE" }); drawAlerts(); toast("Alerte supprimée"); } catch (x) { toast(x.message); } return; }
  const kd = t.closest("[data-kyc]");
  if (kd) { const note = kd.dataset.kyc === "reject" ? prompt("Motif du refus (envoyé à l'hôte) :", "Photos illisibles ou visage non concordant.") : ""; if (note === null) return; return act(`/api/admin/verifications/${kd.dataset.id}/decision`, { action: kd.dataset.kyc, note }); }
  const rep = t.closest("[data-report]"); if (rep) return reportModal(+rep.dataset.report);
  const share = t.closest("[data-share]"); if (share) return shareModal(+share.dataset.share);
  const cm = t.closest("[data-convmenu]"); if (cm) return convMenu(+cm.dataset.convmenu);
  const blk = t.closest("[data-block]"); if (blk) { closeModal(); return act(`/api/conversations/${blk.dataset.block}/block`, {}, "Personne bloquée."); }
  const ub = t.closest("[data-unblock]"); if (ub) return act(`/api/conversations/${ub.dataset.unblock}/block`, { unblock: true }, "Discussion débloquée.");
  const del = t.closest("[data-del]");
  if (del && confirm("Supprimer cette annonce ? Ses photos et son adresse seront libérées.")) { try { await api("/api/listings/" + del.dataset.del, { method: "DELETE" }); route(); } catch (x) { toast(x.message); } return; }
  const cl = t.closest("[data-close]"); if (cl) { try { await api("/api/listings/" + cl.dataset.close, { method: "PATCH", json: { status: "closed" } }); toast("Annonce clôturée"); route(); } catch (x) { toast(x.message); } return; }
  const demo = t.closest("[data-demo]"); if (demo) return runDemo(demo.dataset.demo, demo);
  const ver = t.closest("[data-verify]"); if (ver) return act(`/api/admin/users/${ver.dataset.verify}/verify`, undefined, "Hôte vérifié");
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
  try {
    const r = await api("/api/auth/me");
    if (r.user && (r.user.unread !== state.user.unread || r.user.notif_unread !== state.user.notif_unread)) { state.user.unread = r.user.unread; state.user.notif_unread = r.user.notif_unread; renderHeader(); }
  } catch { /* hors ligne */ }
}, 30000);

(async () => {
  try {
    [state.meta, { user: state.user }, state.auth] = await Promise.all([api("/api/meta"), api("/api/auth/me"), api("/api/auth/config")]);
    await loadFavs();
  } catch (e) { $("#view").innerHTML = errPage(navigator.onLine ? "Ndaku est momentanément indisponible. " + e.message : "Vous êtes hors ligne. Reconnectez-vous pour utiliser Ndaku."); return; }
  offlineBanner();
  route();
})();
})();
