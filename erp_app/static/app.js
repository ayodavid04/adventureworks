// A little plain JavaScript: the clock, the live feed, show/copy secrets, Test connection, Extract.

function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

(function clock() {
  const el = document.getElementById("clock");
  if (!el) return;
  const tick = () => { el.textContent = new Date().toISOString().slice(0, 19).replace("T", " ") + " UTC"; };
  tick(); setInterval(tick, 1000);
})();

const STATUS_CODE = { "In process": 1, "Approved": 2, "Backordered": 3, "Rejected": 4, "Shipped": 5, "Cancelled": 6 };

function startFeed() {
  let seen = null;
  async function load() {
    try {
      const r = await fetch("/ui/feed"); if (!r.ok) return;
      const d = await r.json(), n = d.numbers;
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      const fmt = v => Number(v).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      set("n-today", n.today_orders.toLocaleString()); set("v-today", fmt(n.today_value));
      set("n-month", n.month_orders.toLocaleString()); set("v-month", fmt(n.month_value));
      set("n-open", n.open_orders.toLocaleString()); set("n-sim", n.simulated_orders.toLocaleString());
      document.getElementById("sim-state").innerHTML = d.sim_running
        ? `<span class="dot on"></span>Running, ${d.rate} orders a minute` : `<span class="dot"></span>Stopped`;
      const keys = d.orders.map(o => o.id + "@" + o.modified_at);
      const fresh = seen ? new Set(keys.filter(k => !seen.has(k))) : new Set();
      seen = new Set(keys);
      document.querySelector("#feed tbody").innerHTML = d.orders.map(o => `
        <tr class="${fresh.has(o.id + "@" + o.modified_at) ? "fresh" : ""}">
          <td><a href="/orders/${o.id}">${esc(o.sales_order_number)}</a>${o.comment === "SIMULATED" ? ' <span class="sim">SIM</span>' : ""}</td>
          <td>${esc(o.modified_fmt)}</td><td>${esc(o.order_fmt)}</td>
          <td><a href="/customers/${o.customer_id}">${o.customer_id}</a></td><td>${esc(o.territory)}</td>
          <td>${o.online_order ? "Online" : "Store"}</td>
          <td><span class="st st${o.status_code}">${esc(o.status)}</span></td><td class="num">${esc(o.total_due_fmt)}</td></tr>`).join("");
    } catch (e) { /* server restarting; try again next tick */ }
  }
  load(); setInterval(load, 3000);
}

function startDeliveries() {
  async function load() {
    try {
      const r = await fetch("/ui/deliveries"); if (!r.ok) return;
      const rows = await r.json();
      if (!rows.length) return;
      document.querySelector("#deliveries tbody").innerHTML = rows.map(d => `
        <tr><td>${esc(d.created_fmt)}</td><td>${esc(d.event)}</td><td><code>${esc(d.url)}</code></td>
          <td><span class="dl ${esc(d.status)}">${esc(d.status)}</span></td><td class="num">${esc(d.http_status || "")}</td>
          <td class="num">${d.attempts}</td><td>${esc(d.last_error || "")}</td></tr>`).join("");
    } catch (e) {}
  }
  setInterval(load, 3000);
}

function toggleSecret(btn) {
  const s = btn.parentElement.querySelector(".secret");
  const shown = btn.textContent === "Hide";
  s.textContent = shown ? "•".repeat(8) : (s.dataset.secret || "(not set)");
  btn.textContent = shown ? "Show" : "Hide";
}

async function copySecret(btn) {
  const s = btn.parentElement.querySelector(".secret");
  try { await navigator.clipboard.writeText(s.dataset.secret); btn.textContent = "Copied"; }
  catch (e) { btn.textContent = "Copy failed"; }
  setTimeout(() => { btn.textContent = "Copy"; }, 1500);
}

async function testConnection(btn) {
  const out = document.getElementById("conn-result");
  btn.disabled = true; out.className = "result"; out.textContent = "Connecting...";
  try {
    const d = await (await fetch("/integrations/test-connection", { method: "POST" })).json();
    out.className = "result " + (d.ok ? "ok" : "bad"); out.textContent = d.message;
  } catch (e) { out.className = "result bad"; out.textContent = "The app didn't answer."; }
  btn.disabled = false;
}

async function runExtract(ev) {
  ev.preventDefault();
  const f = ev.target, body = new FormData(f), out = document.getElementById("extract-result");
  out.innerHTML = '<p class="muted">Extracting...</p>';
  const r = await fetch("/integrations/extract", { method: "POST", body });
  const d = await r.json();
  if (!r.ok) { out.innerHTML = `<p class="warn">${esc(d.error || d.detail || "Extract failed")}</p>`; return false; }
  const qs = new URLSearchParams();
  for (const [k, v] of body.entries()) if (v) qs.set(k, v);
  document.getElementById("dl-csv").href = "/integrations/download?" + qs + "&format=csv";
  document.getElementById("dl-json").href = "/integrations/download?" + qs + "&format=json";
  document.getElementById("extract-actions").hidden = false;
  out.innerHTML = `<p><b>${d.count.toLocaleString()}</b> rows. First ${d.rows.length} shown.</p>
    <div class="preview-wrap"><table class="grid"><thead><tr>${d.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${d.rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  return false;
}
