const CONFIG = {
  map: "image/quickmap-lroc.png",                    
  logos: ["image/staminalogo.png", "image/Space_Apps_Logo_Color_and_White.width-440.jpegquality-60.png"],
};
const MISSIONS = [
  { id: "a11", name: "Apollo 11", color: "#f4f78f" },
  { id: "a12", name: "Apollo 12", color: "#e83ee8" },
  { id: "a15", name: "Apollo 15", color: "#4fd97b" },
  { id: "a17", name: "Apollo 17", color: "#f2601f" },
];

const DEFAULT_POINTS = {
  a11: [[71.4, 48.5]], a12: [[55.0, 51.0]],
  a15: [[64.5, 31.2], [57.1, 51.5]], a17: [[74.0, 35.0], [68.6, 55.1]],
};
const INFO = {
  a11: {
    site: "Mare Tranquillitatis — Base de la Tranquillité",
    facts: [["Lancement", "16 juillet 1969"], ["Alunissage", "20 juillet 1969"], ["Équipage", "Neil Armstrong, Buzz Aldrin (sol) · Michael Collins (orbite)"], ["Sur la Lune", "≈ 21 h 36 · 1 sortie de ≈ 2 h 31"], ["Échantillons", "≈ 21,5 kg"], ["Coordonnées", "0,67° N · 23,47° E"]],
    story: "Première mission habitée à se poser sur la Lune. Le module Eagle a dû être piloté à la main par Armstrong pour éviter un champ de rochers, avec très peu de carburant restant. Armstrong puis Aldrin ont marché sur le sol lunaire, planté le drapeau américain et installé un sismomètre et un réflecteur laser encore utilisés aujourd’hui. Retour sur Terre le 24 juillet 1969."
  },
  a12: {
    site: "Oceanus Procellarum — près de la sonde Surveyor 3",
    facts: [["Lancement", "14 novembre 1969"], ["Alunissage", "19 novembre 1969"], ["Équipage", "Pete Conrad, Alan Bean (sol) · Richard Gordon (orbite)"], ["Sur la Lune", "≈ 31 h · 2 sorties (≈ 7 h 45)"], ["Échantillons", "≈ 34 kg"], ["Coordonnées", "3,01° S · 23,42° O"]],
    story: "Le lanceur a été frappé deux fois par la foudre peu après le décollage, mais la mission a pu continuer. Premier alunissage de précision : l’équipage s’est posé à environ 180 m de Surveyor 3, dont il a rapporté des pièces pour étudier l’effet de l’environnement lunaire. Les astronautes ont aussi déployé la première station scientifique ALSEP complète. Retour le 24 novembre 1969."
  },
  a15: {
    site: "Hadley–Apennin — au pied des Apennins, près de la rille Hadley",
    facts: [["Lancement", "26 juillet 1971"], ["Alunissage", "30 juillet 1971"], ["Équipage", "David Scott, James Irwin (sol) · Alfred Worden (orbite)"], ["Sur la Lune", "≈ 67 h · 3 sorties (≈ 18 h 30)"], ["Échantillons", "≈ 77 kg"], ["Coordonnées", "26,13° N · 3,63° E"]],
    story: "Première mission « J » : plus longue, plus scientifique, avec le premier rover lunaire (LRV) qui a permis de parcourir environ 28 km. L’équipage a rapporté la « Genesis Rock », un fragment de croûte lunaire très ancienne. Scott a aussi lâché un marteau et une plume devant la caméra pour montrer qu’ils tombent à la même vitesse en l’absence d’air. Retour le 7 août 1971."
  },
  a17: {
    site: "Taurus–Littrow — vallée bordée de massifs montagneux",
    facts: [["Lancement", "7 décembre 1972 (de nuit)"], ["Alunissage", "11 décembre 1972"], ["Équipage", "Eugene Cernan, Harrison Schmitt (sol) · Ronald Evans (orbite)"], ["Sur la Lune", "≈ 75 h · 3 sorties (≈ 22 h)"], ["Échantillons", "≈ 110 kg"], ["Coordonnées", "20,19° N · 30,77° E"]],
    story: "Dernière mission habitée sur la Lune à ce jour. Harrison Schmitt, seul géologue à avoir marché sur la Lune, a découvert un sol orange composé de billes de verre volcanique vieilles de plus de 3 milliards d’années. L’équipage a parcouru environ 36 km en rover. Pendant le trajet aller, la célèbre photo « Blue Marble » de la Terre a été prise. Retour le 19 décembre 1972."
  }
};

const $ = id => document.getElementById(id);
const map = $("map"), vp = map.parentElement, mapImg = $("mapImg"), mapEmpty = $("mapEmpty");
const clamp = v => Math.max(0, Math.min(100, v));
let ratio = 2, zoom = 1, px = 0, py = 0, drag = null, dragDot = null, down = null, lastTap = {}, placing = false, current = null;
const hiddenM = new Set();
let points = (() => {
  try { const s = localStorage.getItem("moonmap-points"); if (s) return JSON.parse(s); } catch (e) {}
  return structuredClone(DEFAULT_POINTS);
})();
const savePoints = () => { try { localStorage.setItem("moonmap-points", JSON.stringify(points)); } catch (e) {} };

CONFIG.logos.forEach((src, i) => {
  const item = document.createElement("span");
  item.className = "logo-item";
  item.innerHTML = (i ? '<span class="sep">x</span>' : "") + `<img alt="Logo ${i + 1}">`;
  const img = item.querySelector("img");
  img.onerror = () => item.remove();
  img.src = src;
  $("logos").appendChild(item);
});

function loadMap(src) {
  mapImg.onload = () => { ratio = mapImg.naturalWidth / mapImg.naturalHeight; mapImg.hidden = false; mapEmpty.hidden = true; fitMap(); };
  mapImg.onerror = () => { mapImg.hidden = true; mapEmpty.hidden = false; };
  mapImg.src = src;
}
function fitMap() {            
  const W = vp.clientWidth, H = vp.clientHeight;
  let w = W, h = W / ratio;
  if (h > H) { h = H; w = H * ratio; }
  Object.assign(map.style, { width: w + "px", height: h + "px", left: (W - w) / 2 + "px", top: (H - h) / 2 + "px" });
  applyTransform();
}
function applyTransform() {
  const mx = (zoom - 1) * map.offsetWidth / 2, my = (zoom - 1) * map.offsetHeight / 2;
  px = Math.max(-mx, Math.min(mx, px)); py = Math.max(-my, Math.min(my, py));
  map.style.transform = `translate(${px}px, ${py}px) scale(${zoom})`;
  map.classList.toggle("pannable", zoom > 1);
}
$("zin").onclick = () => { zoom = Math.min(4, zoom + 0.25); applyTransform(); };
$("zout").onclick = () => { zoom = Math.max(1, zoom - 0.25); applyTransform(); };
window.addEventListener("resize", fitMap);

const list = $("missions"), btns = {};
MISSIONS.forEach(m => {
  const b = document.createElement("button");
  b.className = "mission"; b.style.color = m.color;
  b.innerHTML = `<i></i><span>${m.name}</span>`;
  b.onclick = () => {
    const off = b.classList.toggle("off");
    off ? hiddenM.add(m.id) : hiddenM.delete(m.id);
    map.querySelectorAll(`.dot[data-m="${m.id}"]`).forEach(d => d.classList.toggle("hidden", off));
    if (off && current === m.id) closeInfo();
  };
  list.appendChild(b); btns[m.id] = b;
  $("placeSel").insertAdjacentHTML("beforeend", `<option value="${m.id}">${m.name}</option>`);
});

function renderDots() {
  map.querySelectorAll(".dot").forEach(d => d.remove());
  MISSIONS.forEach(m => (points[m.id] || []).forEach((p, i) => {
    const d = document.createElement("div");
    d.className = "dot" + (hiddenM.has(m.id) ? " hidden" : "");
    d.style.cssText = `left:${p[0]}%;top:${p[1]}%;color:${m.color}`;
    d.dataset.label = m.name; d.dataset.m = m.id; d.dataset.i = i;
    map.appendChild(d);
  }));
}

function addPoint(e) {
  const r = map.getBoundingClientRect(), id = $("placeSel").value;
  (points[id] ||= []).push([+clamp((e.clientX - r.left) / r.width * 100).toFixed(1), +clamp((e.clientY - r.top) / r.height * 100).toFixed(1)]);
  if (hiddenM.has(id)) { hiddenM.delete(id); btns[id].classList.remove("off"); }
  savePoints(); renderDots();
}

map.addEventListener("pointerdown", e => {
  const dot = e.target.closest(".dot");
  down = { x: e.clientX, y: e.clientY, dot };
  if (placing && dot) { dragDot = dot; map.setPointerCapture(e.pointerId); return; }
  if (zoom > 1 && !dot) { drag = { x: e.clientX - px, y: e.clientY - py }; map.setPointerCapture(e.pointerId); map.classList.add("dragging"); }
});
map.addEventListener("pointermove", e => {
  if (dragDot) {
    const r = map.getBoundingClientRect();
    const x = +clamp((e.clientX - r.left) / r.width * 100).toFixed(1), y = +clamp((e.clientY - r.top) / r.height * 100).toFixed(1);
    dragDot.style.left = x + "%"; dragDot.style.top = y + "%";
    points[dragDot.dataset.m][+dragDot.dataset.i] = [x, y];
  } else if (drag) { px = e.clientX - drag.x; py = e.clientY - drag.y; applyTransform(); }
});
map.addEventListener("pointerup", e => {
  const dn = down; down = null;
  const moved = dn && Math.hypot(e.clientX - dn.x, e.clientY - dn.y) > 4;
  if (dragDot) savePoints();
  dragDot = null; drag = null; map.classList.remove("dragging");
  if (!dn || moved) return;
  const dot = dn.dot;
  if (!placing) { if (dot) showInfo(dot); return; }
  if (!dot) { addPoint(e); return; }
  const k = dot.dataset.m + dot.dataset.i, now = Date.now();   
  if (lastTap.k === k && now - lastTap.t < 400) { points[dot.dataset.m].splice(+dot.dataset.i, 1); savePoints(); renderDots(); lastTap = {}; }
  else lastTap = { k, t: now };
});
map.addEventListener("pointercancel", () => { dragDot = null; drag = null; down = null; map.classList.remove("dragging"); });

$("placeToggle").onclick = e => {
  placing = !placing;
  map.classList.toggle("placing", placing);
  e.target.classList.toggle("active", placing);
  e.target.textContent = "Mode placement : " + (placing ? "ON" : "OFF");
  if (placing) closeInfo();
};
$("exportBtn").onclick = () => {
  const t = JSON.stringify(points), box = $("exportBox");
  box.value = t; box.hidden = false; box.select();
  try { navigator.clipboard?.writeText(t).catch(() => {}); } catch (e) {}
};
$("resetBtn").onclick = () => { points = structuredClone(DEFAULT_POINTS); savePoints(); renderDots(); };

const info = $("info");
const clearSel = () => document.querySelectorAll(".dot.sel").forEach(x => x.classList.remove("sel"));
function showInfo(dot) {
  const m = MISSIONS.find(x => x.id === dot.dataset.m), d = INFO[m.id];
  current = m.id; clearSel(); dot.classList.add("sel");
  $("infoDot").style.background = m.color;
  $("infoName").textContent = m.name;
  $("infoSub").textContent = d.site;
  $("infoFacts").innerHTML = d.facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  $("infoStory").textContent = d.story;
  info.hidden = false;
}
function closeInfo() { info.hidden = true; current = null; clearSel(); }
$("infoClose").onclick = closeInfo;
document.addEventListener("keydown", e => { if (e.key === "Escape") closeInfo(); });

$("menuBtn").addEventListener("click", () => {
  const closed = $("menu").classList.toggle("closed");
  $("app").classList.toggle("menu-closed", closed);
});

const ov = $("overlay"), ovTools = $("ovTools");
$("importBtn").onclick = () => $("fileInput").click();
$("fileInput").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  if (ov.src.startsWith("blob:")) URL.revokeObjectURL(ov.src);
  ov.src = URL.createObjectURL(f); ov.hidden = false; ovTools.hidden = false;
  $("ovName").textContent = f.name; $("ovToggle").textContent = "Masquer";
});
$("ovOpacity").addEventListener("input", e => ov.style.opacity = e.target.value / 100);
$("ovToggle").onclick = e => { ov.hidden = !ov.hidden; e.target.textContent = ov.hidden ? "Afficher" : "Masquer"; };
$("ovRemove").onclick = () => {
  if (ov.src.startsWith("blob:")) URL.revokeObjectURL(ov.src);
  ov.removeAttribute("src"); ov.hidden = true; ovTools.hidden = true; $("fileInput").value = "";
};

const sun = $("sun"), earth = $("earth");
[["sunBtn", sun], ["earthBtn", earth]].forEach(([id, el]) =>
  $(id).addEventListener("click", () => $(id).classList.toggle("active", el.classList.toggle("on"))));
const SYNODIC_MS = 29.530588 * 86400000, NEW_MOON = Date.UTC(2026, 10, 9, 12, 2), pad = n => String(n).padStart(2, "0");
function tick() {
  const now = new Date(), t = new Date(now.getTime() + 3600000);
  $("clock").textContent = `UTC+1 : ${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())} ${pad(t.getUTCMonth() + 1)}.${pad(t.getUTCDate())}.${t.getUTCFullYear()}`;
  sun.style.backgroundPositionX = `${((now - NEW_MOON) % SYNODIC_MS) / SYNODIC_MS * 200}%`;
}
tick(); setInterval(tick, 1000);

renderDots();
fitMap();
loadMap(CONFIG.map);