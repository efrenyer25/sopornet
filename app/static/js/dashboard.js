/* Dashboard: consume /api/estadisticas y dibuja los gráficos con Chart.js. */
"use strict";

const COLORES = {
  azul: "#0b6bcb",
  verde: "#10b39b",
  categorias: ["#0b6bcb", "#10b39b", "#6c4ce0", "#e8901c", "#d93f3f", "#7a8796"],
  prioridades: ["#94a3b8", "#3b82c4", "#e8901c", "#d93f3f"],
};

function configurarTema() {
  const oscuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
  Chart.defaults.color = oscuro ? "#98a6b5" : "#5d6b7a";
  Chart.defaults.borderColor = oscuro ? "#283545" : "#e6ebf1";
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.maintainAspectRatio = false;
}

function graficoTendencia({ fechas, creados, resueltos }) {
  new Chart(document.getElementById("grafico-tendencia"), {
    type: "line",
    data: {
      labels: fechas,
      datasets: [
        { label: "Creados", data: creados, borderColor: COLORES.azul, backgroundColor: COLORES.azul + "22", fill: true, tension: 0.3 },
        { label: "Resueltos", data: resueltos, borderColor: COLORES.verde, backgroundColor: "transparent", tension: 0.3 },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function graficoBarras(id, datos, colores, horizontal = false) {
  new Chart(document.getElementById(id), {
    type: "bar",
    data: {
      labels: Object.keys(datos),
      datasets: [{ data: Object.values(datos), backgroundColor: colores, borderRadius: 6, maxBarThickness: 38 }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      plugins: { legend: { display: false } },
      scales: { [horizontal ? "x" : "y"]: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

async function cargarDashboard() {
  if (typeof Chart === "undefined") {
    document.querySelectorAll(".grafico").forEach((g) => (g.innerHTML = '<p class="ayuda">No se pudo cargar la librería de gráficos (¿sin internet?).</p>'));
    return;
  }
  configurarTema();
  try {
    const stats = await api("/api/estadisticas");
    graficoTendencia(stats.tendencia);
    graficoBarras("grafico-categorias", stats.por_categoria, COLORES.categorias, true);
    graficoBarras("grafico-prioridad", stats.por_prioridad, COLORES.prioridades);
  } catch (error) {
    console.error("Error cargando estadísticas:", error);
  }
}

document.addEventListener("DOMContentLoaded", cargarDashboard);
