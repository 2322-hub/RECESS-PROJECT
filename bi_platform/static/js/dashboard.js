/* ─────────────────────────────────────────────────
   BI Platform – Dashboard JavaScript (v2.0)
   ───────────────────────────────────────────────── */

(function () {
  "use strict";

  let DATA = {};
  let filteredKpis = null;
  const charts = {};

  const COLORS = [
    "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
    "#ec4899","#14b8a6","#f97316","#6366f1","#06b6d4",
  ];

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  function formatNum(n) {
    if (n == null) return "N/A";
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return n.toLocaleString();
  }

  // ─── Theme ───
  const THEME_KEY = "bi-theme";
  function getTheme() { return localStorage.getItem(THEME_KEY) || "dark"; }
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const isLight = theme === "light";
    Chart.defaults.color = isLight ? "#374151" : "#94a3b8";
    Chart.defaults.borderColor = isLight ? "rgba(209,213,219,.4)" : "rgba(71,85,105,.3)";
    document.documentElement.style.setProperty("--bg", isLight ? "#f8fafc" : "#0f172a");
    document.documentElement.style.setProperty("--surface", isLight ? "#ffffff" : "#1e293b");
    document.documentElement.style.setProperty("--surface-2", isLight ? "#f1f5f9" : "#334155");
    document.documentElement.style.setProperty("--border", isLight ? "#e2e8f0" : "#475569");
    document.documentElement.style.setProperty("--text", isLight ? "#1e293b" : "#f1f5f9");
    document.documentElement.style.setProperty("--text-muted", isLight ? "#64748b" : "#94a3b8");
  }
  applyTheme(getTheme());

  // ─── Chart defaults ───
  Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";

  function makeChart(id, config) {
    if (charts[id]) charts[id].destroy();
    const ctx = document.getElementById(id);
    if (!ctx) return null;
    charts[id] = new Chart(ctx, config);
    return charts[id];
  }

  // ─── Chart export as image ───
  function exportChartAsImage(canvasId) {
    const chart = charts[canvasId];
    if (!chart) return;
    const url = chart.toBase64Image("image/png", 1);
    const a = document.createElement("a");
    a.href = url;
    a.download = canvasId + "_chart.png";
    a.click();
  }

  document.addEventListener("click", function(e) {
    if (e.target.classList.contains("chart-export-btn")) {
      const canvas = e.target.closest(".card")?.querySelector("canvas");
      if (canvas) exportChartAsImage(canvas.id);
    }
  });

  // ─── KPI renderer ───
  function renderKpis(containerId, kpis, scheme) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const cards = [
      { label: "Total Revenue", value: "UGX " + formatNum(kpis.total_revenue), cls: "kpi-blue" },
      { label: "Total Profit", value: "UGX " + formatNum(kpis.total_profit), cls: "kpi-green" },
      { label: "Profit Margin", value: (kpis.profit_margin || 0).toFixed(1) + "%", cls: "kpi-orange" },
      { label: "Total Cost", value: "UGX " + formatNum(kpis.total_cost), cls: "kpi-red" },
      { label: "Records", value: formatNum(kpis.record_count), cls: "kpi-purple" },
    ];
    if (scheme === "website") {
      cards.length = 0;
      cards.push(
        { label: "Page Views", value: formatNum(kpis.total_page_views), cls: "kpi-blue" },
        { label: "Unique Visitors", value: formatNum(kpis.total_unique_visitors), cls: "kpi-green" },
        { label: "Bounce Rate", value: kpis.avg_bounce_rate + "%", cls: "kpi-orange" },
        { label: "Conversions", value: formatNum(kpis.total_conversions), cls: "kpi-purple" },
        { label: "Conversion Rate", value: kpis.conversion_rate + "%", cls: "kpi-green" },
      );
    }
    if (scheme === "customer") {
      cards.length = 0;
      cards.push(
        { label: "Total Customers", value: formatNum(kpis.total_customers), cls: "kpi-blue" },
        { label: "Avg LTV", value: "UGX " + formatNum(kpis.avg_lifetime_value), cls: "kpi-green" },
        { label: "Total LTV", value: "UGX " + formatNum(kpis.total_lifetime_value), cls: "kpi-orange" },
        { label: "Avg Orders", value: kpis.avg_orders, cls: "kpi-purple" },
      );
    }
    el.innerHTML = cards.map(c =>
      '<div class="kpi-card ' + escapeHtml(c.cls) + '">' +
        '<span class="kpi-label">' + escapeHtml(c.label) + '</span>' +
        '<span class="kpi-value">' + escapeHtml(c.value) + '</span>' +
      '</div>'
    ).join("");
  }

  // ─── Drill-down state ───
  let activeDrillDown = null;

  function drillDown(filterId, value) {
    if (!value) return;
    const sel = document.getElementById(filterId);
    if (!sel) return;
    const opts = Array.from(sel.options).map(o => o.value);
    if (!opts.includes(value)) {
      const opt = document.createElement("option");
      opt.value = value; opt.textContent = value;
      sel.appendChild(opt);
    }
    if (activeDrillDown && activeDrillDown.filterId === filterId && activeDrillDown.value === value) {
      clearDrillDown();
      return;
    }
    sel.value = value;
    activeDrillDown = { filterId, value };
    const tag = document.getElementById("drilldownTag");
    const bar = document.getElementById("drilldownBar");
    const colName = filterId.replace("Filter", "").replace("_", " ");
    tag.textContent = colName + " = " + value;
    bar.classList.add("active");
    applyFilters();
  }

  function clearDrillDown() {
    if (!activeDrillDown) return;
    const sel = document.getElementById(activeDrillDown.filterId);
    if (sel) sel.value = "";
    activeDrillDown = null;
    document.getElementById("drilldownBar").classList.remove("active");
    applyFilters();
  }
  document.getElementById("drilldownClear").addEventListener("click", clearDrillDown);

  function drillDownClickHandler(filterId) {
    return function(_event, elements) {
      if (!elements || !elements.length) return;
      const idx = elements[0].index;
      const chart = charts[this.canvas.id];
      if (chart) {
        const label = chart.data.labels[idx];
        drillDown(filterId, label);
      }
    };
  }

  function drillDownHoverHandler(_event, elements) {
    this.canvas.style.cursor = elements && elements.length ? "pointer" : "default";
  }

  // ─── Chart builders ───
  function buildOverviewCharts(d) {
    const monthly = d.monthly_trends || [];
    makeChart("chartRevenueTrend", {
      type: "line",
      data: {
        labels: monthly.map(m => m.date),
        datasets: [
          { label: "Revenue", data: monthly.map(m => m.revenue), borderColor: COLORS[0], backgroundColor: COLORS[0] + "22", fill: true, tension: .3 },
          { label: "Profit", data: monthly.map(m => m.profit), borderColor: COLORS[1], backgroundColor: COLORS[1] + "22", fill: true, tension: .3 },
        ],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Monthly Revenue & Profit Trend" } } },
    });

    const regionData = d.revenue_breakdown?.region || [];
    makeChart("chartRegionBar", {
      type: "bar",
      data: {
        labels: regionData.map(r => r.label),
        datasets: [{ label: "Revenue", data: regionData.map(r => r.value), backgroundColor: COLORS }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Revenue by Region (click to drill down)" } },
        onClick: drillDownClickHandler("regionFilter"),
        onHover: drillDownHoverHandler,
      },
    });

    const catData = d.revenue_breakdown?.product_category || [];
    makeChart("chartCategoryPie", {
      type: "pie",
      data: {
        labels: catData.map(c => c.label),
        datasets: [{ data: catData.map(c => c.value), backgroundColor: COLORS }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Revenue by Category (click to drill down)" } },
        onClick: drillDownClickHandler("categoryFilter"),
        onHover: drillDownHoverHandler,
      },
    });

    const segData = d.revenue_breakdown?.customer_segment || [];
    makeChart("chartSegmentDonut", {
      type: "doughnut",
      data: {
        labels: segData.map(s => s.label),
        datasets: [{ data: segData.map(s => s.value), backgroundColor: COLORS }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Revenue by Segment (click to drill down)" } },
        onClick: drillDownClickHandler("segmentFilter"),
        onHover: drillDownHoverHandler,
      },
    });

    const regComp = d.regional_comparison || [];
    makeChart("chartProfitMargin", {
      type: "bar",
      data: {
        labels: regComp.map(r => r.region),
        datasets: [{ label: "Avg Order Value", data: regComp.map(r => r.avg_order_value), backgroundColor: COLORS[2] }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Avg Order Value by Region" } } },
    });
  }

  function buildRevenueCharts(d) {
    const kpis = d.kpis || {};
    renderKpis("revenueKpis", kpis);
    const monthly = d.monthly_trends || [];
    makeChart("chartMonthlyRev", {
      type: "bar",
      data: {
        labels: monthly.map(m => m.date),
        datasets: [
          { label: "Revenue", data: monthly.map(m => m.revenue), backgroundColor: COLORS[0] },
          { label: "Quantity", data: monthly.map(m => m.quantity), backgroundColor: COLORS[3], hidden: true },
        ],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Monthly Revenue" } } },
    });
    makeChart("chartMonthlyProfit", {
      type: "line",
      data: {
        labels: monthly.map(m => m.date),
        datasets: [{ label: "Profit", data: monthly.map(m => m.profit), borderColor: COLORS[1], tension: .3, fill: { target: "origin", above: COLORS[1] + "22" } }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Monthly Profit" } } },
    });
    const rc = d.regional_comparison || [];
    makeChart("chartRegionalTable", {
      type: "bar",
      data: {
        labels: rc.map(r => r.region),
        datasets: [
          { label: "Revenue", data: rc.map(r => r.revenue), backgroundColor: COLORS[0] },
          { label: "Profit", data: rc.map(r => r.profit), backgroundColor: COLORS[1] },
        ],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Regional Comparison (click to drill down)" } },
        onClick: drillDownClickHandler("regionFilter"),
        onHover: drillDownHoverHandler,
      },
    });
  }

  function buildProductCharts(d) {
    const topP = d.top_products || [];
    makeChart("chartTopProducts", {
      type: "bar",
      data: {
        labels: topP.map(p => p.label),
        datasets: [{ label: "Revenue", data: topP.map(p => p.value), backgroundColor: COLORS }],
      },
      options: {
        indexAxis: "y", responsive: true,
        plugins: { title: { display: true, text: "Top Products by Revenue (click to drill down)" } },
        onClick: drillDownClickHandler("categoryFilter"),
        onHover: drillDownHoverHandler,
      },
    });
    const catData = d.revenue_breakdown?.product_category || [];
    makeChart("chartCategoryRevenue", {
      type: "polarArea",
      data: {
        labels: catData.map(c => c.label),
        datasets: [{ data: catData.map(c => c.value), backgroundColor: COLORS.map(c => c + "99") }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Category Revenue (click to drill down)" } },
        onClick: drillDownClickHandler("categoryFilter"),
        onHover: drillDownHoverHandler,
      },
    });
    const pp = d.product_performance || [];
    let tableHtml = '<table><thead><tr><th>Category</th><th>Product</th><th>Revenue</th><th>Profit</th><th>Quantity</th></tr></thead><tbody>';
    pp.forEach(function(p) {
      tableHtml += '<tr><td>' + escapeHtml(p.product_category) + '</td><td>' + escapeHtml(p.product_name) + '</td><td>UGX ' + escapeHtml(formatNum(p.revenue)) + '</td><td>UGX ' + escapeHtml(formatNum(p.profit)) + '</td><td>' + escapeHtml(formatNum(p.quantity)) + '</td></tr>';
    });
    tableHtml += '</tbody></table>';
    document.getElementById("productTable").innerHTML = tableHtml;
  }

  function buildWebsiteCharts(d) {
    const wa = d.website_analytics || {};
    renderKpis("websiteKpis", wa, "website");
    const trend = wa.daily_trend || [];
    makeChart("chartPageViews", {
      type: "line",
      data: {
        labels: trend.map(t => t.date),
        datasets: [
          { label: "Page Views", data: trend.map(t => t.page_views), borderColor: COLORS[0], tension: .3 },
          { label: "Visitors", data: trend.map(t => t.visitors), borderColor: COLORS[1], tension: .3 },
        ],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Daily Page Views & Visitors" } } },
    });
    makeChart("chartConversions", {
      type: "bar",
      data: {
        labels: trend.map(t => t.date),
        datasets: [{ label: "Revenue", data: trend.map(t => t.revenue), backgroundColor: COLORS[2] + "99" }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Daily Website Revenue" } } },
    });
  }

  function buildCustomerCharts(d) {
    const ci = d.customer_insights || {};
    renderKpis("customerKpis", ci, "customer");
    const bySeg = ci.by_segment || [];
    makeChart("chartCustSegment", {
      type: "bar",
      data: {
        labels: bySeg.map(s => s.segment),
        datasets: [
          { label: "Customers", data: bySeg.map(s => s.count), backgroundColor: COLORS[0] },
          { label: "Avg LTV", data: bySeg.map(s => s.avg_ltv), backgroundColor: COLORS[1], hidden: true },
        ],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Customers by Segment (click to drill down)" } },
        onClick: drillDownClickHandler("segmentFilter"),
        onHover: drillDownHoverHandler,
      },
    });
    const byReg = ci.by_region || [];
    makeChart("chartCustRegion", {
      type: "doughnut",
      data: {
        labels: byReg.map(r => r.region),
        datasets: [{ data: byReg.map(r => r.count), backgroundColor: COLORS }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Customers by Region (click to drill down)" } },
        onClick: drillDownClickHandler("regionFilter"),
        onHover: drillDownHoverHandler,
      },
    });
  }

  function renderAll(d) {
    DATA = d;
    renderKpis("kpiRow", d.kpis);
    buildOverviewCharts(d);
    buildRevenueCharts(d);
    buildProductCharts(d);
    buildWebsiteCharts(d);
    buildCustomerCharts(d);
  }

  function showError(msg) {
    let bar = document.getElementById("errorBar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "errorBar";
      bar.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;padding:12px 20px;background:#ef4444;color:#fff;text-align:center;font-size:14px;cursor:pointer;";
      document.body.prepend(bar);
    }
    bar.textContent = msg;
    bar.style.display = "block";
    bar.onclick = () => { bar.style.display = "none"; };
    setTimeout(() => { if (bar) bar.style.display = "none"; }, 8000);
  }
  function hideError() {
    const bar = document.getElementById("errorBar");
    if (bar) bar.style.display = "none";
  }

  let _lastConn = null;
  function showSpinner() { document.getElementById("spinnerOverlay").classList.add("active"); }
  function hideSpinner() { document.getElementById("spinnerOverlay").classList.remove("active"); }

  async function fetchData() {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    if (_lastConn && _lastConn !== conn) {
      clearDrillDown();
      ["regionFilter", "categoryFilter", "segmentFilter"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
    }
    _lastConn = conn;
    showSpinner();
    try {
      const res = await fetch("/api/v1/dashboard-data?conn=" + encodeURIComponent(conn));
      if (res.status === 401 || res.redirected) { window.location.href = "/login"; return; }
      const text = await res.text();
      let d;
      try { d = JSON.parse(text); } catch (_) { showError("Server error (HTTP " + res.status + ")."); console.error("Non-JSON:", text.slice(0, 500)); return; }
      if (d.error) { hideSpinner(); showError("Data load error: " + d.error); console.error("API error:", d); return; }
      hideError();
      renderAll(d);
      populateFilters(d);
      hideSpinner();
    } catch (e) {
      hideSpinner();
      showError("Failed to load: " + e.message);
      console.error("Fetch error", e);
    }
  }

  function populateFilters(d) {
    const regions = new Set();
    const categories = new Set();
    const segments = new Set();
    (d.revenue_breakdown?.region || []).forEach(r => regions.add(r.label));
    (d.revenue_breakdown?.product_category || []).forEach(c => categories.add(c.label));
    (d.revenue_breakdown?.customer_segment || []).forEach(s => segments.add(s.label));
    fillSelect("regionFilter", regions);
    fillSelect("categoryFilter", categories);
    fillSelect("segmentFilter", segments);
  }

  function fillSelect(id, vals) {
    const sel = document.getElementById(id);
    if (!sel) return;
    const prevValue = sel.value;
    const first = sel.options[0];
    sel.innerHTML = "";
    sel.appendChild(first);
    [...vals].sort().forEach(v => {
      const o = document.createElement("option");
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
    if (prevValue && [...sel.options].some(o => o.value === prevValue)) {
      sel.value = prevValue;
    }
  }

  async function applyFilters() {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    const body = {
      table: "sales",
      conn: conn,
      filters: {
        region: document.getElementById("regionFilter").value,
        product_category: document.getElementById("categoryFilter").value,
        customer_segment: document.getElementById("segmentFilter").value,
      },
      date_start: document.getElementById("dateStart").value || null,
      date_end: document.getElementById("dateEnd").value || null,
    };
    try {
      const res = await fetch("/api/v1/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await res.json();
      filteredKpis = d.kpis;
      renderKpis("kpiRow", d.kpis);
    } catch (e) { console.error(e); }
  }

  // ─── Navigation ───
  $$(".nav-link[data-section]").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const sec = link.dataset.section;
      $$(".nav-link").forEach(l => l.classList.remove("active"));
      link.classList.add("active");
      $$(".section").forEach(s => s.classList.remove("active"));
      const target = document.getElementById("sec-" + sec);
      if (target) target.classList.add("active");
      $("#pageTitle").textContent = link.textContent;
      document.getElementById("sidebar").classList.remove("open");
    });
  });

  // ─── Menu toggle ───
  $("#menuToggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  // ─── Refresh ───
  $("#refreshBtn").addEventListener("click", fetchData);

  // ─── Theme toggle ───
  $("#themeToggle").addEventListener("click", () => {
    const current = getTheme();
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
    Object.values(charts).forEach(c => { if (c && c.update) c.update(); });
  });

  // ─── Filter change ───
  ["regionFilter", "categoryFilter", "segmentFilter"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", () => {
      if (activeDrillDown && activeDrillDown.filterId !== id) {
        clearDrillDown();
      } else if (activeDrillDown && activeDrillDown.filterId === id && !el.value) {
        clearDrillDown();
      }
      applyFilters();
    });
  });
  ["dateStart", "dateEnd"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", applyFilters);
  });

  // ─── DB Modal ───
  $("#connectDbBtn").addEventListener("click", () => document.getElementById("dbModal").classList.add("show"));
  $("#dbModalCancel").addEventListener("click", () => document.getElementById("dbModal").classList.remove("show"));
  $("#dbModalConnect").addEventListener("click", async () => {
    const name = $("#dbName").value.trim();
    const connStr = $("#dbConnStr").value.trim();
    if (!name || !connStr) return;
    try {
      const res = await fetch("/api/v1/connect", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, connection_string: connStr }),
      });
      const d = await res.json();
      if (d.error) { alert(d.error); return; }
      document.getElementById("dbModal").classList.remove("show");
      await populateActiveConn();
      document.getElementById("activeConn").value = name;
      fetchData();
    } catch (e) { alert("Connection failed: " + e.message); }
  });

  // ─── Data Explorer ───
  let explorerPage = 1;
  async function loadExplorerTables() {
    const conn = document.getElementById("explorerConn").value;
    try {
      const res = await fetch("/api/v1/tables?conn=" + encodeURIComponent(conn));
      const tables = await res.json();
      const sel = document.getElementById("explorerTable");
      sel.innerHTML = tables.map(t => '<option value="' + t + '">' + t + '</option>').join("");
      if (tables.length) loadExplorer();
    } catch (e) { console.error(e); }
  }
  async function loadExplorer() {
    const conn = document.getElementById("explorerConn").value;
    const table = document.getElementById("explorerTable").value;
    const search = document.getElementById("explorerSearch").value;
    if (!table) return;
    try {
      const res = await fetch("/api/v1/data/" + encodeURIComponent(table) + "?conn=" + encodeURIComponent(conn) + "&page=" + explorerPage + "&per_page=50&search=" + encodeURIComponent(search));
      const d = await res.json();
      renderTable("explorerTableWrap", d.columns, d.rows);
      renderPagination("explorerPagination", d.pages, d.page, (p) => { explorerPage = p; loadExplorer(); });
    } catch (e) { console.error(e); }
  }
  $("#explorerConn").addEventListener("change", () => { explorerPage = 1; loadExplorerTables(); });
  $("#explorerTable").addEventListener("change", () => { explorerPage = 1; loadExplorer(); });
  $("#explorerLoad").addEventListener("click", () => { explorerPage = 1; loadExplorer(); });
  $("#explorerSearch").addEventListener("keypress", (e) => { if (e.key === "Enter") { explorerPage = 1; loadExplorer(); } });
  $("#explorerExport").addEventListener("click", () => {
    const conn = document.getElementById("explorerConn").value;
    const table = document.getElementById("explorerTable").value;
    if (!table) return;
    window.location.href = "/api/v1/export/" + encodeURIComponent(table) + "?conn=" + encodeURIComponent(conn);
  });

  function renderTable(containerId, columns, rows) {
    const el = document.getElementById(containerId);
    if (!columns || !rows) { el.innerHTML = "<p>No data</p>"; return; }
    let html = "<table><thead><tr>";
    columns.forEach(c => { html += "<th>" + escapeHtml(c) + "</th>"; });
    html += "</tr></thead><tbody>";
    rows.forEach(r => {
      html += "<tr>";
      columns.forEach(c => { html += "<td>" + escapeHtml(r[c] != null ? r[c] : "") + "</td>"; });
      html += "</tr>";
    });
    html += "</tbody></table>";
    el.innerHTML = html;
  }

  function renderPagination(containerId, totalPages, current, cb) {
    const el = document.getElementById(containerId);
    if (!el || totalPages <= 1) { if (el) el.innerHTML = ""; return; }
    let html = "";
    html += "<button " + (current <= 1 ? "disabled" : "") + " data-p=\"" + (current - 1) + "\">&laquo;</button>";
    for (let i = 1; i <= Math.min(totalPages, 10); i++) {
      html += "<button class=\"" + (i === current ? 'active' : '') + "\" data-p=\"" + i + "\">" + i + "</button>";
    }
    html += "<button " + (current >= totalPages ? "disabled" : "") + " data-p=\"" + (current + 1) + "\">&raquo;</button>";
    el.innerHTML = html;
    el.querySelectorAll("button").forEach(b => {
      b.addEventListener("click", () => { const p = parseInt(b.dataset.p); if (!isNaN(p)) cb(p); });
    });
  }

  // ─── SQL Query with CodeMirror ───
  let sqlCodeMirror = null;
  async function loadConnections() {
    try {
      const res = await fetch("/api/v1/connections");
      const names = await res.json();
      const sel = document.getElementById("sqlConnection");
      sel.innerHTML = "";
      names.forEach(n => { const o = document.createElement("option"); o.value = n; o.textContent = n; sel.appendChild(o); });
    } catch (e) { console.error(e); }
  }

  function initCodeMirror() {
    const textarea = document.getElementById("sqlEditor");
    if (!textarea || !window.CodeMirror) return;
    const theme = getTheme() === "light" ? "material-darker" : "dracula";
    sqlCodeMirror = CodeMirror.fromTextArea(textarea, {
      mode: "text/x-sql",
      theme: theme,
      lineNumbers: true,
      indentWithTabs: false,
      smartIndent: true,
      tabSize: 2,
      autofocus: true,
      lineWrapping: true,
      extraKeys: { "Ctrl-Enter": function() { document.getElementById("sqlRunBtn").click(); } },
    });
  }

  $("#sqlRunBtn").addEventListener("click", async () => {
    const conn = document.getElementById("sqlConnection").value;
    const sql = sqlCodeMirror ? sqlCodeMirror.getValue().trim() : document.getElementById("sqlEditor").value.trim();
    if (!sql) return;
    const el = document.getElementById("sqlResult");
    el.innerHTML = "<p>Running...</p>";
    try {
      const res = await fetch("/api/v1/custom-query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connection: conn, sql }),
      });
      const d = await res.json();
      if (d.error) { el.innerHTML = "<p style='color:var(--red)'>" + escapeHtml(d.error) + "</p>"; return; }
      renderTable("sqlResult", d.columns, d.rows || []);
    } catch (e) { el.innerHTML = "<p style='color:var(--red)'>Error: " + escapeHtml(e.message) + "</p>"; }
  });
  $("#sqlClearBtn").addEventListener("click", () => {
    document.getElementById("sqlResult").innerHTML = "";
    if (sqlCodeMirror) sqlCodeMirror.setValue("");
  });
  $("#sqlExportBtn").addEventListener("click", async () => {
    const conn = document.getElementById("sqlConnection").value;
    const sql = sqlCodeMirror ? sqlCodeMirror.getValue().trim() : document.getElementById("sqlEditor").value.trim();
    if (!sql) return;
    try {
      const res = await fetch("/api/v1/export-query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connection: conn, sql }),
      });
      if (!res.ok) { const d = await res.json(); showError(d.error || "Export failed"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "query_result.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { showError("Export failed: " + e.message); }
  });

  // ─── Forecasting ───
  $("#forecastRunBtn").addEventListener("click", async () => {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    const periods = parseInt(document.getElementById("forecastPeriods").value) || 6;
    const el = document.getElementById("forecastMetrics");
    el.innerHTML = "<p style='color:var(--text-muted)'>Generating forecast...</p>";
    try {
      const res = await fetch("/api/v1/forecast", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conn, periods }),
      });
      if (!res.ok) {
        let msg = "Forecast failed (HTTP " + res.status + ")";
        try { const err = await res.json(); if (err.error) msg = err.error; } catch (_) {}
        el.innerHTML = "<p style='color:var(--red)'>" + escapeHtml(msg) + "</p>";
        return;
      }
      const d = await res.json();
      if (d.error) { el.innerHTML = "<p style='color:var(--red)'>" + escapeHtml(d.error) + "</p>"; return; }

      if (d.metrics) {
        el.innerHTML = '<div class="kpi-row">' +
          '<div class="kpi-card kpi-blue"><span class="kpi-label">MAE</span><span class="kpi-value">' + d.metrics.mae + '</span></div>' +
          '<div class="kpi-card kpi-green"><span class="kpi-label">RMSE</span><span class="kpi-value">' + d.metrics.rmse + '</span></div>' +
          '<div class="kpi-card kpi-orange"><span class="kpi-label">AIC</span><span class="kpi-value">' + d.metrics.aic + '</span></div>' +
          '</div>';
      }

      const hist = d.historical || [];
      const fc = d.forecast || [];
      const lower = d.lower_bound || [];
      const upper = d.upper_bound || [];

      const allDates = [...hist.map(h => h.date), ...fc.map(f => f.date)];
      const histRevenue = hist.map(h => h.revenue);
      const forecastValues = new Array(hist.length).fill(null).concat(fc.map(f => f.value));
      const lowerValues = new Array(hist.length).fill(null).concat(lower.map(l => l.value));
      const upperValues = new Array(hist.length).fill(null).concat(upper.map(u => u.value));

      makeChart("chartForecast", {
        type: "line",
        data: {
          labels: allDates,
          datasets: [
            { label: "Historical Revenue", data: histRevenue, borderColor: COLORS[0], backgroundColor: COLORS[0] + "22", fill: false, tension: .3 },
            { label: "Forecast", data: forecastValues, borderColor: COLORS[2], borderDash: [5, 5], fill: false, tension: .3 },
            { label: "Upper Bound", data: upperValues, borderColor: COLORS[1] + "44", backgroundColor: COLORS[1] + "11", fill: "+1", tension: .3, pointRadius: 0 },
            { label: "Lower Bound", data: lowerValues, borderColor: COLORS[1] + "44", fill: false, tension: .3, pointRadius: 0 },
          ],
        },
        options: {
          responsive: true,
          plugins: { title: { display: true, text: "Revenue Forecast (" + periods + " months)" } },
          scales: {
            x: { title: { display: true, text: "Date" } },
            y: { title: { display: true, text: "Revenue (UGX)" } },
          },
        },
      });
    } catch (e) {
      el.innerHTML = "<p style='color:var(--red)'>Forecast failed: " + escapeHtml(e.message) + "</p>";
    }
  });

  // ─── Anomaly Detection ───
  $("#anomalyRunBtn").addEventListener("click", async () => {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    const summaryEl = document.getElementById("anomalySummary");
    const resultsEl = document.getElementById("anomalyResults");
    summaryEl.innerHTML = "<p style='color:var(--text-muted)'>Analyzing data...</p>";
    resultsEl.innerHTML = "";
    try {
      const res = await fetch("/api/v1/anomalies", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conn }),
      });
      const d = await res.json();
      if (d.error) { summaryEl.innerHTML = "<p style='color:var(--red)'>" + escapeHtml(d.error) + "</p>"; return; }

      const rev = d.revenue || {};
      const s = rev.summary || {};
      summaryEl.innerHTML = '<div class="kpi-row">' +
        '<div class="kpi-card kpi-blue"><span class="kpi-label">Mean Revenue</span><span class="kpi-value">UGX ' + formatNum(s.mean) + '</span></div>' +
        '<div class="kpi-card kpi-green"><span class="kpi-label">Std Dev</span><span class="kpi-value">UGX ' + formatNum(s.std) + '</span></div>' +
        '<div class="kpi-card kpi-orange"><span class="kpi-label">Trend</span><span class="kpi-value">' + (s.trend || "N/A") + '</span></div>' +
        '<div class="kpi-card kpi-purple"><span class="kpi-label">Anomalies</span><span class="kpi-value">' + (s.anomaly_count || 0) + ' (' + (s.anomaly_pct || 0) + '%)</span></div>' +
        '</div>';

      const anomalies = rev.anomalies || [];
      if (anomalies.length === 0) {
        resultsEl.innerHTML = '<div class="card" style="margin-top:1rem"><p style="color:var(--text-muted)">No anomalies detected in the data.</p></div>';
      } else {
        let html = '<div class="card" style="margin-top:1rem"><h3>Detected Anomalies</h3><table><thead><tr><th>Date</th><th>Value</th><th>Z-Score</th><th>Type</th><th>Deviation</th></tr></thead><tbody>';
        anomalies.forEach(a => {
          const typeClass = a.type === "spike" ? "color:var(--green)" : "color:var(--red)";
          html += '<tr><td>' + a.date + '</td><td>UGX ' + formatNum(a.value) + '</td><td>' + a.z_score + '</td><td style="' + typeClass + ';font-weight:600">' + a.type + '</td><td>' + a.deviation_pct + '%</td></tr>';
        });
        html += '</tbody></table></div>';
        resultsEl.innerHTML = html;
      }
    } catch (e) {
      summaryEl.innerHTML = "<p style='color:var(--red)'>Anomaly detection failed: " + escapeHtml(e.message) + "</p>";
    }
  });

  // ─── NL Query ───
  $("#nlQueryRunBtn").addEventListener("click", async () => {
    const query = document.getElementById("nlQueryInput").value.trim();
    if (!query) return;
    const el = document.getElementById("nlQueryResult");
    el.innerHTML = "<p style='color:var(--text-muted)'>Processing...</p>";
    try {
      const res = await fetch("/api/v1/nl-query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const d = await res.json();
      if (d.error) { el.innerHTML = "<p style='color:var(--red)'>" + escapeHtml(d.error) + "</p>"; return; }

      let html = '<div class="card" style="margin-top:.5rem">';
      html += '<p style="color:var(--text-muted);font-size:.85rem"><strong>Intent:</strong> ' + escapeHtml(d.intent || "unknown") + '</p>';
      html += '<p style="color:var(--text-muted);font-size:.85rem"><strong>SQL:</strong> <code style="background:var(--surface-2);padding:.2rem .4rem;border-radius:4px">' + escapeHtml(d.sql || "") + '</code></p>';
      if (d.explanation) html += '<p style="color:var(--text-muted);font-size:.85rem;margin-top:.5rem">' + escapeHtml(d.explanation) + '</p>';
      if (d.columns && d.rows) {
        html += '<div style="margin-top:.5rem;overflow:auto;max-height:300px">';
        html += '<table><thead><tr>';
        d.columns.forEach(c => { html += '<th>' + escapeHtml(c) + '</th>'; });
        html += '</tr></thead><tbody>';
        d.rows.forEach(r => {
          html += '<tr>';
          d.columns.forEach(c => { html += '<td>' + escapeHtml(r[c] != null ? r[c] : "") + '</td>'; });
          html += '</tr>';
        });
        html += '</tbody></table></div>';
      }
      html += '</div>';
      el.innerHTML = html;
    } catch (e) {
      el.innerHTML = "<p style='color:var(--red)'>Query failed: " + escapeHtml(e.message) + "</p>";
    }
  });
  $("#nlQueryInput").addEventListener("keypress", (e) => {
    if (e.key === "Enter") $("#nlQueryRunBtn").click();
  });

  // ─── Export PDF / Excel ───
  $("#exportPdfBtn").addEventListener("click", async () => {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    try {
      const res = await fetch("/api/v1/report/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conn }),
      });
      if (!res.ok) { const d = await res.json(); showError(d.error || "PDF export failed"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "bi_report_" + conn + ".pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { showError("PDF export failed: " + e.message); }
  });

  $("#exportExcelBtn").addEventListener("click", async () => {
    const conn = (document.getElementById("activeConn") || {}).value || "demo";
    try {
      const res = await fetch("/api/v1/report/excel", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conn }),
      });
      if (!res.ok) { const d = await res.json(); showError(d.error || "Excel export failed"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "bi_report_" + conn + ".xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { showError("Excel export failed: " + e.message); }
  });

  // ─── Saved Views ───
  $("#saveViewBtn").addEventListener("click", () => {
    document.getElementById("viewName").value = "";
    document.getElementById("saveViewModal").classList.add("show");
  });

  $("#saveViewConfirm").addEventListener("click", async () => {
    const name = document.getElementById("viewName").value.trim();
    if (!name) return;
    const activeSection = document.querySelector(".nav-link.active")?.dataset.section || "overview";
    const filters = {
      region: document.getElementById("regionFilter").value,
      category: document.getElementById("categoryFilter").value,
      segment: document.getElementById("segmentFilter").value,
      date_start: document.getElementById("dateStart").value,
      date_end: document.getElementById("dateEnd").value,
      conn: (document.getElementById("activeConn") || {}).value || "demo",
    };
    try {
      const res = await fetch("/api/v1/views", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, view_type: "filter", filters, section: activeSection, connection: filters.conn }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showError(err.error || "Failed to save view (HTTP " + res.status + ")");
        return;
      }
      document.getElementById("saveViewModal").classList.remove("show");
    } catch (e) { showError("Failed to save view: " + e.message); }
  });

  $("#loadViewsBtn").addEventListener("click", async () => {
    const listEl = document.getElementById("savedViewsList");
    listEl.innerHTML = "<p style='color:var(--text-muted)'>Loading...</p>";
    document.getElementById("loadViewsModal").classList.add("show");
    try {
      const res = await fetch("/api/v1/views");
      if (!res.ok) { listEl.innerHTML = "<p style='color:var(--red)'>Failed to load views</p>"; return; }
      const views = await res.json();
      if (!Array.isArray(views) || views.length === 0) {
        listEl.innerHTML = "<p style='color:var(--text-muted)'>No saved views yet.</p>";
        return;
      }
      listEl.innerHTML = views.map(v =>
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:.6rem;border:1px solid var(--border);border-radius:var(--radius);margin-bottom:.4rem">' +
          '<div><strong>' + escapeHtml(v.name) + '</strong><br><span style="font-size:.8rem;color:var(--text-muted)">' + escapeHtml(v.section || "overview") + ' | ' + escapeHtml(v.connection || "demo") + '</span></div>' +
          '<div class="btn-group">' +
            '<button class="btn btn-sm btn-accent" onclick="window._loadView(' + v.id + ')">Load</button>' +
            '<button class="btn btn-sm btn-danger" onclick="window._deleteView(' + v.id + ')">Delete</button>' +
          '</div>' +
        '</div>'
      ).join("");
    } catch (e) { listEl.innerHTML = "<p style='color:var(--red)'>Failed to load views</p>"; }
  });

  const VALID_SECTIONS = new Set(["overview","revenue","products","website","customers","data-explorer","sql-query","forecasting","anomalies","admin","nl-query"]);

  window._loadView = async function(viewId) {
    try {
      const res = await fetch("/api/v1/views/" + viewId);
      if (!res.ok) {
        showError("View not found or failed to load");
        return;
      }
      const view = await res.json();
      if (view.error) { showError(view.error); return; }
      if (view.filters) {
        const f = view.filters;
        if (f.region != null) document.getElementById("regionFilter").value = f.region;
        if (f.category != null) document.getElementById("categoryFilter").value = f.category;
        if (f.segment != null) document.getElementById("segmentFilter").value = f.segment;
        if (f.date_start != null) document.getElementById("dateStart").value = f.date_start;
        if (f.date_end != null) document.getElementById("dateEnd").value = f.date_end;
        if (f.conn && document.getElementById("activeConn")) {
          document.getElementById("activeConn").value = f.conn;
        }
      }
      if (view.section && VALID_SECTIONS.has(view.section)) {
        const navLink = document.querySelector('.nav-link[data-section="' + CSS.escape(view.section) + '"]');
        if (navLink && !navLink.classList.contains("active")) navLink.click();
      }
      document.getElementById("loadViewsModal").classList.remove("show");
      applyFilters();
    } catch (e) { showError("Failed to load view: " + e.message); }
  };

  window._deleteView = async function(viewId) {
    if (!confirm("Delete this view?")) return;
    try {
      const res = await fetch("/api/v1/views/" + viewId, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showError(err.error || "Failed to delete view");
        return;
      }
      $("#loadViewsBtn").click();
    } catch (e) { showError("Failed to delete view: " + e.message); }
  };

  // ─── Dashboard Widget Drag-and-Drop ───
  function initSortableGrids() {
    if (!window.Sortable) return;
    document.querySelectorAll(".widget-grid").forEach(grid => {
      Sortable.create(grid, {
        animation: 150,
        ghostClass: "sortable-ghost",
        dragClass: "sortable-drag",
        handle: ".card",
      });
    });
  }

  // ─── WebSocket ───
  const socket = io();
  socket.on("connect", () => {
    const el = document.getElementById("connStatus");
    el.innerHTML = '<span class="status-dot"></span> Real-time connected';
  });
  socket.on("disconnect", () => {
    const el = document.getElementById("connStatus");
    el.innerHTML = '<span class="status-dot" style="background:var(--red)"></span> Disconnected';
  });
  socket.on("dashboard_update", (d) => {
    renderAll(d);
    populateFilters(d);
    const anyFilterActive = ["regionFilter", "categoryFilter", "segmentFilter"].some(
      id => document.getElementById(id)?.value
    );
    if (anyFilterActive && filteredKpis) {
      renderKpis("kpiRow", filteredKpis);
    }
  });

  // ─── Online users (collaborative) ───
  socket.on("online_users", (users) => {
    const el = document.getElementById("onlineUsers");
    if (!el) return;
    if (!users || users.length <= 1) { el.innerHTML = ""; return; }
    el.innerHTML = '<span style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem;display:block">' + users.length + ' users online</span>';
  });

  socket.on("cursor_update", (data) => {
    if (!data || !data.cursor) return;
    const container = document.getElementById("cursorContainer");
    let cursor = document.getElementById("cursor-" + data.username);
    if (!cursor) {
      cursor = document.createElement("div");
      cursor.id = "cursor-" + data.username;
      cursor.style.cssText = "position:fixed;pointer-events:none;transition:all .1s;z-index:10000;";
      cursor.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M5 3l14 9-7 2-3 7z" fill="currentColor"/></svg><span style="font-size:10px;background:var(--accent);color:#fff;padding:1px 4px;border-radius:3px;margin-left:4px">' + escapeHtml(data.username) + '</span>';
      container.appendChild(cursor);
    }
    cursor.style.left = data.cursor.x + "px";
    cursor.style.top = data.cursor.y + "px";
    cursor.style.color = COLORS[Math.abs(data.username.charCodeAt(0)) % COLORS.length];
    clearTimeout(cursor._timeout);
    cursor._timeout = setTimeout(() => { cursor.remove(); }, 3000);
  });

  document.addEventListener("mousemove", (e) => {
    socket.emit("cursor_move", { x: e.clientX, y: e.clientY });
  });

  // ─── Populate active connection dropdown ───
  async function populateActiveConn() {
    try {
      const res = await fetch("/api/v1/connections");
      const names = await res.json();
      const sel = document.getElementById("activeConn");
      const defaultConn = document.getElementById("defaultConn").value || "demo";
      const current = sel.value;
      sel.innerHTML = names.map(n => '<option value="' + n + '">' + n + '</option>').join("");
      if (names.includes(current)) sel.value = current;
      else if (names.includes(defaultConn)) sel.value = defaultConn;
      else sel.value = names[0];
    } catch (e) { console.error(e); }
  }
  $("#activeConn").addEventListener("change", fetchData);

  // ─── Init ───
  (async function init() {
    await populateActiveConn();
    await fetchData();
    loadExplorerTables();
    loadConnections();
    initCodeMirror();
    initSortableGrids();
  })();
})();
