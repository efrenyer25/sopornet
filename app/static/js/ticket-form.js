/* Formulario de ticket: análisis con IA en vivo usando async/await. */
"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const boton = document.getElementById("btn-analizar");
  const panel = document.getElementById("resultado-ia");
  const campo = (nombre) => panel.querySelector(`[data-ia="${nombre}"]`);
  let ultimoResultado = null;

  const nombreCategoria = (clave) =>
    document.querySelector(`#categoria option[value="${clave}"]`)?.textContent ?? clave;
  const nombrePrioridad = (clave) =>
    document.querySelector(`#prioridad option[value="${clave}"]`)?.textContent ?? clave;

  async function analizar() {
    const titulo = document.getElementById("titulo").value.trim();
    const descripcion = document.getElementById("descripcion").value.trim();
    if (titulo.length + descripcion.length < 10) {
      alert("Escribe un título y una descripción antes de analizar.");
      return;
    }

    const textoOriginal = boton.textContent;
    boton.disabled = true;
    boton.textContent = "Analizando…";
    try {
      const resultado = await api("/api/ia/clasificar", {
        method: "POST",
        body: JSON.stringify({ titulo, descripcion }),
      });
      ultimoResultado = resultado;
      const porcentaje = Math.round(resultado.confianza * 100);
      campo("categoria").textContent = nombreCategoria(resultado.categoria);
      campo("prioridad").textContent = nombrePrioridad(resultado.prioridad);
      campo("confianza").textContent = `${porcentaje}%`;
      campo("fuente").textContent = resultado.fuente === "claude" ? "Claude (LLM)" : "Modelo local";
      campo("barra").style.width = `${porcentaje}%`;
      campo("sugerencia").textContent = resultado.sugerencia;
      panel.classList.add("visible");
    } catch (error) {
      alert(`No se pudo analizar: ${error.message}`);
    } finally {
      boton.disabled = false;
      boton.textContent = textoOriginal;
    }
  }

  boton.addEventListener("click", analizar);

  document.getElementById("btn-aplicar-ia").addEventListener("click", () => {
    if (!ultimoResultado) return;
    document.getElementById("categoria").value = ultimoResultado.categoria;
    document.getElementById("prioridad").value = ultimoResultado.prioridad;
  });
});
