// Test de fumée de l'interface dans un DOM simulé (jsdom) contre un serveur réel.
// Usage : npm i jsdom ; uvicorn app.main:app --port 8000 ; BASE=http://127.0.0.1:8000 node tests/ui_smoke.js
const { JSDOM } = require("jsdom"); const BASE = process.env.BASE || "http://127.0.0.1:8000";
const sleep = ms => new Promise(r => setTimeout(r, ms)); let fails = 0;
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };
async function until(f, ms = 25000) { const t = Date.now(); while (Date.now() - t < ms) { try { if (f()) return true } catch (e) {} await sleep(150) } return false }
(async () => {
  const dom = await JSDOM.fromURL(BASE + "/", { runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, beforeParse(w) {
    w.fetch = (u, o) => fetch(new URL(u, BASE), o); if (!w.crypto || !w.crypto.randomUUID) Object.defineProperty(w, "crypto", { value: require("crypto").webcrypto }); w.alert = m => console.log("alert:", m) } });
  const d = dom.window.document, $ = s => d.querySelector(s), $$ = s => [...d.querySelectorAll(s)];
  await until(() => $$("#colours input").length > 0); ok($$("#colours input").length > 0, "filtres couleur chargés depuis /api/options");
  $("#agenda").value = "match de foot avec les amis"; $("#go").click();
  ok(await until(() => $$("#out .card").length === 3 && $$("#out .ok").length === 3), "3 tenues affichées avec boutons 👍 🔀 👎");
  const text0 = $$("#out .card").map(c => c.textContent);
  $$("#out .ok")[0].click(); ok(await until(() => $("#nf").textContent === "1"), "👍 ajoute la tenue à « Mes tenues aimées »");
  ok($$("#favs .card").length === 1 && $$("#out .card")[0].classList.contains("liked"), "carte aimée marquée et copiée dans la liste");
  $$("#out .skip")[0].click(); ok(await until(() => $$("#out .card")[1] && !$$("#out .card")[1].textContent.includes("Je cherche") && $$("#out .card")[1].textContent !== text0[1]), "🔀 remplace la tenue sans recharger");
  $$("#out .no")[0].click(); ok(await until(() => $("#out [data-act=swapall]")), "👎 ouvre le panneau (articles à choisir, raisons)");
  ok($("#out [data-act=swapsel]").disabled === true, "« Remplacer les articles choisis » désactivé tant qu'aucun article n'est choisi");
  $$("#out [data-act=pick]")[0].click(); ok(await until(() => $("#out [data-act=swapsel]") && !$("#out [data-act=swapsel]").disabled), "choisir un article active le bouton");
  $("#out [data-act=swapsel]").click(); ok(await until(() => $("#xinfo").textContent.includes("exclu") && $$("#out .ok").length >= 1), "remplacement avec articles exclus ; compteur d'exclusions affiché");
  const nos = $$("#out [data-act=no]"), card = nos[nos.length - 1].closest(".card"), before = card.textContent; nos[nos.length - 1].click();
  await until(() => card.querySelector("[data-act=swapall]")); card.querySelector("[data-act=swapall]").click();
  ok(await until(() => card.textContent !== before && !card.textContent.includes("Je cherche") && !card.textContent.includes("Plus d'autre")), "« Changer toute la tenue » remplace la carte");
  ok(await until(() => /retours/.test($("#stats").textContent)), "statistiques de retours mises à jour");
  console.log(fails ? `${fails} échec(s)` : "interface : tout est OK"); process.exit(fails ? 1 : 0);
})();
