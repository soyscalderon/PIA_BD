// La API se consume a traves del mismo dominio (nginx hace de proxy hacia el
// contenedor "api" en el puerto 8080). Se puede cambiar por una URL absoluta,
// por ejemplo: const API_URL = "http://localhost:8080/api";
const API_URL = "/api";

async function api(ruta, metodo = "GET", cuerpo = null) {
  const opciones = { method: metodo, headers: {} };

  if (cuerpo !== null) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }

  const respuesta = await fetch(`${API_URL}${ruta}`, opciones);
  const datos = await respuesta.json().catch(() => ({}));

  if (!respuesta.ok) {
    throw new Error(datos.error || "No se pudo completar la operacion.");
  }

  return datos;
}
