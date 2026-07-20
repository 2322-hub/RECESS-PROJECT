/* ─────────────────────────────────────────────────
   BI Platform – Dashboard JavaScript
   ───────────────────────────────────────────────── */

(function () {
  "use strict";

  // ─── State ───
  let DATA = {};
  const charts = {};

  // ─── Colour palette ───
  const COLORS = [
    "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
    "#ec4899","#14b8a6","#f97316","#6366f1","#06b6d4",
  ];

  // ─── Helpers ───
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

  // ─── Chart defaults ───
  Chart.defaults.color = "#94a3b8";
  Chart.defaults.borderColor = "rgba(71,85,105,.3)";
  Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";

  function makeChart(id, config) {
    if (charts[id]) charts[id].destroy();
    const ctx = document.getElementById(id);
    if (!ctx) return null;
    charts[id] = new Chart(ctx, config);
    return charts[id];
  }

  // ─── KPI renderer ───
  function renderKpis(containerId, kpis, scheme) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const cards = [
      { label: "Total Revenue", value: "$" + formatNum(kpis.total_revenue), cls: "kpi-blue" },
      { label: "Total Profit", value: "$" + formatNum(kpis.total_profit), cls: "kpi-green" },
      { label: "Profit Margin", value: (kpis.profit_margin || 0).toFixed(1) + "%", cls: "kpi-orange" },
      { label: "Total Cost", value: "$" + formatNum(kpis.total_cost), cls: "kpi-red" },
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
        { label: "Avg LTV", value: "$" + formatNum(kpis.avg_lifetime_value), cls: "kpi-green" },
        { label: "Total LTV", value: "$" + formatNum(kpis.total_lifetime_value), cls: "kpi-orange" },
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
      options: { responsive: true, plugins: { title: { display: true, text: "Revenue by Region" } } },
    });

    const catData = d.revenue_breakdown?.product_category || [];
    makeChart("chartCategoryPie", {
      type: "pie",
      data: {
        labels: catData.map(c => c.label),
        datasets: [{ data: catData.map(c => c.value), backgroundColor: COLORS }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Revenue by Category" } } },
    });

    const segData = d.revenue_breakdown?.customer_segment || [];
    makeChart("chartSegmentDonut", {
      type: "doughnut",
      data: {
        labels: segData.map(s => s.label),
        datasets: [{ data: segData.map(s => s.value), backgroundColor: COLORS }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Revenue by Segment" } } },
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
      options: { responsive: true, plugins: { title: { display: true, text: "Regional Comparison" } } },
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
      options: { indexAxis: "y", responsive: true, plugins: { title: { display: true, text: "Top Products by Revenue" } } },
    });

    const catData = d.revenue_breakdown?.product_category || [];
    makeChart("chartCategoryRevenue", {
      type: "polarArea",
      data: {
        labels: catData.map(c => c.label),
        datasets: [{ data: catData.map(c => c.value), backgroundColor: COLORS.map(c => c + "99") }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Category Revenue (Polar)" } } },
    });

    const pp = d.product_performance || [];
    var tableHtml = '<table><thead><tr><th>Category</th><th>Product</th><th>Revenue</th><th>Profit</th><th>Quantity</th></tr></thead><tbody>';
    pp.forEach(function(p) {
      tableHtml += '<tr><td>' + escapeHtml(p.product_category) + '</td><td>' + escapeHtml(p.product_name) + '</td><td>$' + escapeHtml(formatNum(p.revenue)) + '</td><td>$' + escapeHtml(formatNum(p.profit)) + '</td><td>' + escapeHtml(formatNum(p.quantity)) + '</td></tr>';
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
      options: { responsive: true, plugins: { title: { display: true, text: "Customers by Segment" } } },
    });

    const byReg = ci.by_region || [];
    makeChart("chartCustRegion", {
      type: "doughnut",
      data: {
        labels: byReg.map(r => r.region),
        datasets: [{ data: byReg.map(r => r.count), backgroundColor: COLORS }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: "Customers by Region" } } },
    });
  }

  // ─── Master render ───
  function renderAll(d) {
    DATA = d;
    renderKpis("kpiRow", d.kpis);
    buildOverviewCharts(d);
    buildRevenueCharts(d);
    buildProductCharts(d);
    buildWebsiteCharts(d);
    buildCustomerCharts(d);
  }

  // ─── Data Fetching ───
  async function fetchData() {
    try {
      const res = await fetch("/api/dashboard-data");
      if (res.status === 401 || res.redirected) { window.location.href = "/login"; return; }
      const d = await res.json();
      renderAll(d);
    } catch (e) {
      console.error("Failed to load dashboard data", e);
    }
  }

  // ─── Filters ───
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
    const first = sel.options[0];
    sel.innerHTML = "";
    sel.appendChild(first);
    [...vals].sort().forEach(v => {
      const o = document.createElement("option");
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  }

  async function applyFilters() {
    const body = {
      table: "sales",
      filters: {
        region: document.getElementById("regionFilter").value,
        product_category: document.getElementById("categoryFilter").value,
        customer_segment: document.getElementById("segmentFilter").value,
      },
    };
    try {
      const res = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await res.json();
      renderKpis("kpiRow", d.kpis);
    } catch (e) { console.error(e); }
  }

  // ─── Navigation ───
  $$(".nav-link").forEach(link => {
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

  // ─── Menu toggle (mobile) ───
  $("#menuToggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  // ─── Refresh button ───
  $("#refreshBtn").addEventListener("click", fetchData);

  // ─── Filter change ───
  ["regionFilter", "categoryFilter", "segmentFilter"].forEach(id => {
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
      const res = await fetch("/api/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, connection_string: connStr }),
      });
      const d = await res.json();
      if (d.error) { alert(d.error); return; }
      document.getElementById("dbModal").classList.remove("show");
      fetchData();
    } catch (e) { alert("Connection failed: " + e.message); }
  });

  // ─── Data Explorer ───
  let explorerPage = 1;
  async function loadExplorer() {
    const table = document.getElementById("explorerTable").value;
    const search = document.getElementById("explorerSearch").value;
    if (!table) return;
    try {
      const res = await fetch("/api/data/" + encodeURIComponent(table) + "?page=" + explorerPage + "&per_page=50&search=" + encodeURIComponent(search));
      const d = await res.json();
      renderTable("explorerTableWrap", d.columns, d.rows);
      renderPagination("explorerPagination", d.pages, d.page, (p) => { explorerPage = p; loadExplorer(); });
    } catch (e) { console.error(e); }
  }
  $("#explorerLoad").addEventListener("click", loadExplorer);

  function renderTable(containerId, columns, rows) {
    const el = document.getElementById(containerId);
    if (!columns || !rows) { el.innerHTML = "<p>No data</p>"; return; }
    var html = "<table><thead><tr>";
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

  // ─── Populate explorer table dropdown ───
  async function loadExplorerTables() {
    try {
      const res = await fetch("/api/tables");
      const tables = await res.json();
      const sel = document.getElementById("explorerTable");
      tables.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o); });
    } catch (e) { console.error(e); }
  }

  // ─── WebSocket real-time ───
  const socket = io();
  socket.on("connect", () => {
    var el = document.getElementById("connStatus");
    el.textContent = "";
    var dot = document.createElement("span");
    dot.className = "status-dot";
    el.appendChild(dot);
    el.appendChild(document.createTextNode(" Real-time connected"));
  });
  socket.on("disconnect", () => {
    var el = document.getElementById("connStatus");
    el.textContent = "";
    var dot = document.createElement("span");
    dot.className = "status-dot";
    dot.style.background = "var(--red)";
    el.appendChild(dot);
    el.appendChild(document.createTextNode(" Disconnected"));
  });
  socket.on("dashboard_update", (d) => {
    renderAll(d);
    populateFilters(d);
  });

  // ─── Init ───
  (async function init() {
    await fetchData();
    await loadExplorerTables();
  })();
})();
