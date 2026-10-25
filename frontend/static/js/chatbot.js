/* Asistente de ayuda de ReMarket: botón flotante + panel de chat. Usa las variables CSS de la app. */
(function () {
  const SUGERENCIAS = [
    "¿Cómo funciona la app?",
    "¿Cómo registro un producto?",
    "¿Cómo se calcula la prioridad?",
    "¿Por qué un producto quedó sin destino?",
    "¿Cómo planifico una ruta?",
  ];
  const historial = [];
  let ocupado = false;

  const css = `
#cb-btn{position:fixed;right:18px;bottom:18px;z-index:1000;width:56px;height:56px;border-radius:50%;border:0;background:var(--ac);color:#fff;font-size:26px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.3)}
#cb-btn:focus-visible,#cb-x:focus-visible,#cb-send:focus-visible,.cb-chip:focus-visible,#cb-in:focus-visible{outline:2px solid var(--ac2);outline-offset:2px}
#cb{position:fixed;right:18px;bottom:86px;z-index:1000;width:min(380px,calc(100vw - 36px));height:min(540px,calc(100vh - 110px));display:none;flex-direction:column;background:var(--sf);color:var(--tx);border:1px solid var(--bd);border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.28);overflow:hidden}
#cb.on{display:flex}
#cb header{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--ac);color:#fff;max-width:none;margin:0}
#cb header b{font:800 15px "Bricolage Grotesque","Public Sans",system-ui,sans-serif}
#cb-x{background:none;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer}
#cb-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;font-size:14px}
.cb-m{max-width:88%;padding:8px 11px;border-radius:12px;line-height:1.45;word-wrap:break-word}
.cb-m.bot{align-self:flex-start;background:var(--bg);border:1px solid var(--bd)}
.cb-m.me{align-self:flex-end;background:var(--ac2);color:#fff}
.cb-chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 12px 8px}
.cb-chip{background:none;border:1px solid var(--ac);color:var(--ac);border-radius:99px;padding:4px 10px;font:500 12.5px inherit;cursor:pointer}
#cb-f{display:flex;gap:6px;padding:10px;border-top:1px solid var(--bd)}
#cb-in{flex:1;min-width:0}
#cb-send{background:var(--ac);color:#fff;border:0;border-radius:7px;padding:0 14px;font:600 14px inherit;cursor:pointer}
#cb-send:disabled{opacity:.6;cursor:wait}
#cb-mode{font-size:11px;color:var(--mu);padding:0 12px 8px}
@media(prefers-reduced-motion:no-preference){.cb-m{animation:cbin .15s ease-out}@keyframes cbin{from{opacity:0;transform:translateY(4px)}}}`;
  document.head.appendChild(Object.assign(document.createElement("style"), { textContent: css }));

  document.body.insertAdjacentHTML("beforeend", `
<button id="cb-btn" aria-label="Abrir asistente de ayuda" aria-expanded="false" aria-controls="cb">💬</button>
<section id="cb" role="dialog" aria-label="Asistente de ayuda de ReMarket">
  <header><b>Asistente ReMarket</b><button id="cb-x" aria-label="Cerrar asistente">×</button></header>
  <div id="cb-log" role="log" aria-live="polite"></div>
  <div class="cb-chips" id="cb-chips"></div>
  <div id="cb-mode"></div>
  <form id="cb-f"><input id="cb-in" placeholder="Escribe tu duda…" maxlength="500" autocomplete="off" aria-label="Mensaje"><button id="cb-send">Enviar</button></form>
</section>`);

  const $c = (s) => document.querySelector(s);
  const panel = $c("#cb"), btn = $c("#cb-btn"), log = $c("#cb-log"), inp = $c("#cb-in"), send = $c("#cb-send");

  // Texto seguro: escapa HTML y permite **negrita** y saltos de línea.
  const fmt = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]))
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/\n/g, "<br>");

  function pintar(rol, texto) {
    const d = document.createElement("div");
    d.className = "cb-m " + (rol === "user" ? "me" : "bot");
    d.innerHTML = fmt(texto);
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  function abrir(v) {
    panel.classList.toggle("on", v);
    btn.setAttribute("aria-expanded", v);
    if (v) { inp.focus(); if (!log.children.length) bienvenida(); } else btn.focus();
  }

  function bienvenida() {
    pintar("bot", "¡Hola! Soy el asistente de **ReMarket**. Te ayudo a registrar, clasificar, asignar y rastrear productos. ¿Qué necesitas?");
    $c("#cb-chips").innerHTML = SUGERENCIAS.map((s) => `<button type="button" class="cb-chip">${s}</button>`).join("");
  }

  async function enviar(texto) {
    texto = texto.trim();
    if (!texto || ocupado) return;
    ocupado = true; send.disabled = true;
    $c("#cb-chips").innerHTML = "";
    pintar("user", texto);
    historial.push({ role: "user", content: texto });
    const esp = pintar("bot", "Escribiendo…");
    try {
      const pestana = typeof tab !== "undefined" && typeof TABS !== "undefined" ? TABS[tab] : "";
      const r = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensajes: historial.slice(-12), pestana }),
      });
      if (!r.ok) throw new Error();
      const j = await r.json();
      esp.innerHTML = fmt(j.respuesta);
      historial.push({ role: "assistant", content: j.respuesta });
      $c("#cb-mode").textContent = j.modo === "ia" ? "Respuestas con IA" : "Modo básico (sin IA configurada)";
    } catch {
      esp.innerHTML = fmt("No pude conectarme con el asistente. Revisa tu conexión e inténtalo de nuevo.");
      historial.pop();
    }
    log.scrollTop = log.scrollHeight;
    ocupado = false; send.disabled = false; inp.focus();
  }

  btn.onclick = () => abrir(!panel.classList.contains("on"));
  $c("#cb-x").onclick = () => abrir(false);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && panel.classList.contains("on")) abrir(false); });
  $c("#cb-f").onsubmit = (e) => { e.preventDefault(); const t = inp.value; inp.value = ""; enviar(t); };
  $c("#cb-chips").onclick = (e) => { if (e.target.classList.contains("cb-chip")) enviar(e.target.textContent); };
})();
