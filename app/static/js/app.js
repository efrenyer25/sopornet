/* SoporteNet — comportamiento general de la interfaz (DOM y eventos). */
"use strict";

document.addEventListener("DOMContentLoaded", () => {
  // Menú lateral en móviles
  const sidebar = document.getElementById("sidebar");
  document.getElementById("btn-menu")?.addEventListener("click", (evento) => {
    evento.stopPropagation();
    sidebar.classList.toggle("abierta");
  });
  document.addEventListener("click", (evento) => {
    if (sidebar?.classList.contains("abierta") && !sidebar.contains(evento.target)) {
      sidebar.classList.remove("abierta");
    }
  });

  // Cerrar mensajes flash (y ocultarlos solos a los 6 segundos)
  document.querySelectorAll(".alerta").forEach((alerta) => {
    alerta.querySelector("[data-cerrar]")?.addEventListener("click", () => alerta.remove());
    if (alerta.classList.contains("alerta-success") || alerta.classList.contains("alerta-info")) {
      setTimeout(() => alerta.remove(), 6000);
    }
  });

  // Confirmación antes de acciones destructivas
  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      if (!window.confirm(form.dataset.confirmar)) evento.preventDefault();
    });
  });

  // Filtros que se envían al cambiar
  document.querySelectorAll("select[data-autoenvio]").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });
});

/**
 * Envoltura de fetch para la API REST: envía/recibe JSON y lanza error legible.
 * @param {string} url
 * @param {RequestInit} opciones
 */
async function api(url, opciones = {}) {
  const respuesta = await fetch(url, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    credentials: "same-origin",
    ...opciones,
  });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(datos.error || `Error ${respuesta.status}`);
  return datos;
}
