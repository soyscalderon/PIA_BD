// ============================================================================
// INVENTARIO: videojuegos, plataformas y proveedores.
// Todos los datos provienen de la API (MySQL) ya no hay arreglos JSON locales.
// ============================================================================

let plataformasDB = [];
let proveedoresDB = [];
let videojuegosDB = [];

// VARIABLES QUE DEFINEN EL COMPORTAMINETO DE LOS FORMULARIOS

let modoEdicionJuego = false;
let idJuegoEditando = null;

let modoEdicionPlat = false;
let idPlatEditando = null;

let modoEdicionProv = false;
let idProvEditando = null;

// PERMITE NAVEGAR ENTRE TABS

function cambiarTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.add('hidden');
  });

  document.querySelectorAll('[id^="tab-btn-"]').forEach(btn => {
    btn.className = 'px-4 py-2 font-semibold text-sm rounded-t-lg bg-white text-slate-600 hover:bg-slate-200 transition';
  });

  const contenido = document.getElementById(`tab-${tab}`);
  const boton = document.getElementById(`tab-btn-${tab}`);

  if (contenido && boton) {
    contenido.classList.remove('hidden');

    boton.className = 'px-4 py-2 font-semibold text-sm rounded-t-lg bg-indigo-600 text-white transition';
  }
}

window.cambiarTab = cambiarTab;

// INCIALIZA LOS DATOS DE LA APLICACIÓN

async function init() {
  await cargarPlataformas();
  await cargarProveedores();
  await cargarJuegos();
}

function mensajeError(tbody, columnas, error) {
  tbody.innerHTML = `
    <tr>
      <td colspan="${columnas}" class="py-4 text-center text-rose-500 text-xs">
        ${error.message}
      </td>
    </tr>
  `;
}

async function cargarJuegos() {
  const tbody = document.getElementById('tabla-juegos');
  tbody.innerHTML = '';

  try {
    videojuegosDB = await api('/videojuegos');
  } catch (error) {
    mensajeError(tbody, 6, error);
    return;
  }

  videojuegosDB.forEach(j => {
    const plat = plataformasDB.find(p => p.id_plataforma === j.id_plataforma);
    const nombrePlat = j.plataforma || (plat ? plat.nombre : 'N/A');

    tbody.innerHTML += `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 font-semibold text-slate-500">#${j.id_videojuego}</td>

        <td class="py-3 font-medium text-slate-900">
          ${j.titulo}
        </td>

        <td class="py-3">
          <span class="bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full text-xs font-semibold">
            ${nombrePlat}
          </span>
        </td>

        <td class="py-3 font-semibold text-slate-800">
          $${parseFloat(j.precio).toFixed(2)}
        </td>

        <td class="py-3">
          <span class="px-2 py-1 rounded text-xs font-bold ${j.stock > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
            ${j.stock} unidades
          </span>
        </td>

        <td class="py-3 text-right space-x-2">
          <button onclick="prepararEdicionJuego(${j.id_videojuego})"
            class="text-amber-600 hover:text-amber-800 font-medium text-xs">
            <i class="fa-solid fa-pen"></i> Editar
          </button>

          <button onclick="eliminarJuego(${j.id_videojuego})"
            class="text-rose-600 hover:text-rose-800 font-medium text-xs">
            <i class="fa-solid fa-trash"></i> Eliminar
          </button>
        </td>
      </tr>
    `;
  });
}


function prepararEdicionJuego(id) {
  const j = videojuegosDB.find(item => item.id_videojuego === id);
  if (!j) return;

  modoEdicionJuego = true;
  idJuegoEditando = j.id_videojuego;

  document.getElementById('juego_titulo').value = j.titulo;
  document.getElementById('juego_plataforma').value = j.id_plataforma;
  document.getElementById('juego_proveedor').value = j.id_proveedor || '';
  document.getElementById('juego_precio').value = j.precio;
  document.getElementById('juego_stock').value = j.stock;
  document.getElementById('juego_desarrollador').value = j.desarrollador || '';

  document.getElementById('titulo-form-juego').textContent = 'Editar Videojuego';
  document.getElementById('btn-guardar-juego').textContent = 'Actualizar Videojuego';
  document.getElementById('btn-cancelar-juego').classList.remove('hidden');
}


function cancelarEdicionJuego() {
  modoEdicionJuego = false;
  idJuegoEditando = null;

  document.getElementById('form-juego').reset();
  document.getElementById('titulo-form-juego').textContent = 'Nuevo Videojuego';
  document.getElementById('btn-guardar-juego').textContent = 'Guardar Videojuego';
  document.getElementById('btn-cancelar-juego').classList.add('hidden');
}

window.prepararEdicionJuego = prepararEdicionJuego;
window.cancelarEdicionJuego = cancelarEdicionJuego;


document.getElementById('form-juego').addEventListener('submit', async (e) => {
  e.preventDefault();

  const datosJuego = {
    titulo: document.getElementById('juego_titulo').value,
    id_plataforma: parseInt(document.getElementById('juego_plataforma').value),
    id_proveedor: parseInt(document.getElementById('juego_proveedor').value),
    precio: parseFloat(document.getElementById('juego_precio').value),
    stock: parseInt(document.getElementById('juego_stock').value),
    desarrollador: document.getElementById('juego_desarrollador').value
  };

  try {
    if (modoEdicionJuego) {
      // PUT /api/videojuegos/{id}
      await api(`/videojuegos/${idJuegoEditando}`, 'PUT', datosJuego);
    } else {
      // POST /api/videojuegos
      await api('/videojuegos', 'POST', datosJuego);
    }
  } catch (error) {
    alert(error.message);
    return;
  }

  cancelarEdicionJuego();
  await cargarJuegos();
});

async function eliminarJuego(id) {
  if (!confirm('¿Deseas eliminar este videojuego del inventario?')) return;

  try {
    // DELETE /api/videojuegos/{id}
    await api(`/videojuegos/${id}`, 'DELETE');
  } catch (error) {
    alert(error.message);
    return;
  }

  await cargarJuegos();
}

window.eliminarJuego = eliminarJuego;


async function cargarPlataformas() {
  const select = document.getElementById('juego_plataforma');
  const tbody = document.getElementById('tabla-plataformas');

  select.innerHTML = '<option value="">Seleccione Plataforma</option>';
  tbody.innerHTML = '';

  try {
    plataformasDB = await api('/plataformas');
  } catch (error) {
    mensajeError(tbody, 4, error);
    return;
  }

  plataformasDB.forEach(p => {

    select.innerHTML += `
      <option value="${p.id_plataforma}">
        ${p.nombre} (${p.fabricante})
      </option>
    `;

    tbody.innerHTML += `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 font-semibold text-slate-500">#${p.id_plataforma}</td>

        <td class="py-3 font-bold text-slate-900">
          ${p.nombre}
        </td>

        <td class="py-3 text-slate-600">
          ${p.fabricante}
        </td>

        <td class="py-3 text-right space-x-2">
          <button onclick="prepararEdicionPlat(${p.id_plataforma})"
            class="text-amber-600 hover:text-amber-800 font-medium text-xs">
            <i class="fa-solid fa-pen"></i> Editar
          </button>

          <button onclick="eliminarPlataforma(${p.id_plataforma})"
            class="text-rose-600 hover:text-rose-800 font-medium text-xs">
            <i class="fa-solid fa-trash"></i> Eliminar
          </button>
        </td>
      </tr>
    `;
  });
}

function prepararEdicionPlat(id) {
  const p = plataformasDB.find(item => item.id_plataforma === id);
  if (!p) return;

  modoEdicionPlat = true;
  idPlatEditando = p.id_plataforma;

  document.getElementById('plat_nombre').value = p.nombre;
  document.getElementById('plat_fabricante').value = p.fabricante;

  document.getElementById('titulo-form-plat').textContent = 'Editar Plataforma';
  document.getElementById('btn-guardar-plat').textContent = 'Actualizar Plataforma';
  document.getElementById('btn-cancelar-plat').classList.remove('hidden');
}


function cancelarEdicionPlat() {
  modoEdicionPlat = false;
  idPlatEditando = null;

  document.getElementById('form-plataforma').reset();
  document.getElementById('titulo-form-plat').textContent = 'Nueva Plataforma';
  document.getElementById('btn-guardar-plat').textContent = 'Guardar Plataforma';
  document.getElementById('btn-cancelar-plat').classList.add('hidden');
}

window.prepararEdicionPlat = prepararEdicionPlat;
window.cancelarEdicionPlat = cancelarEdicionPlat;

//CREAR Y ACTUALIZAR PLATAFORMA

document.getElementById('form-plataforma').addEventListener('submit', async (e) => {
  e.preventDefault();

  const datosPlataforma = {
    nombre: document.getElementById('plat_nombre').value,
    fabricante: document.getElementById('plat_fabricante').value
  };

  try {
    if (modoEdicionPlat) {
      // PUT /api/plataformas/{id}
      await api(`/plataformas/${idPlatEditando}`, 'PUT', datosPlataforma);
    } else {
      // POST /api/plataformas
      await api('/plataformas', 'POST', datosPlataforma);
    }
  } catch (error) {
    alert(error.message);
    return;
  }

  cancelarEdicionPlat();
  await cargarPlataformas();
  await cargarJuegos();
});

//ELIMINAR PLATAFORMA

async function eliminarPlataforma(id) {
  if (!confirm('¿Deseas eliminar esta plataforma?')) return;

  try {
    // DELETE /api/plataformas/{id}
    await api(`/plataformas/${id}`, 'DELETE');
  } catch (error) {
    alert(error.message);
    return;
  }

  await cargarPlataformas();
  await cargarJuegos();
}

window.eliminarPlataforma = eliminarPlataforma;

async function cargarProveedores() {
  const select = document.getElementById('juego_proveedor');
  const tbody = document.getElementById('tabla-proveedores');

  select.innerHTML = '<option value="">Seleccione Proveedor</option>';
  tbody.innerHTML = '';

  try {
    proveedoresDB = await api('/proveedores');
  } catch (error) {
    mensajeError(tbody, 5, error);
    return;
  }

  proveedoresDB.forEach(pr => {

    select.innerHTML += `
      <option value="${pr.id_proveedor}">
        ${pr.nombre_empresa}
      </option>
    `;

    tbody.innerHTML += `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 font-semibold text-slate-500">#${pr.id_proveedor}</td>

        <td class="py-3 font-bold text-slate-900">
          ${pr.nombre_empresa}
        </td>

        <td class="py-3 text-slate-600">
          ${pr.contacto}
        </td>

        <td class="py-3 text-indigo-600 font-medium">
          ${pr.telefono}
        </td>

        <td class="py-3 text-right space-x-2">
          <button onclick="prepararEdicionProv(${pr.id_proveedor})"
            class="text-amber-600 hover:text-amber-800 font-medium text-xs">
            <i class="fa-solid fa-pen"></i> Editar
          </button>

          <button onclick="eliminarProveedor(${pr.id_proveedor})"
            class="text-rose-600 hover:text-rose-800 font-medium text-xs">
            <i class="fa-solid fa-trash"></i> Eliminar
          </button>
        </td>
      </tr>
    `;
  });
}

function prepararEdicionProv(id) {
  const pr = proveedoresDB.find(item => item.id_proveedor === id);
  if (!pr) return;

  modoEdicionProv = true;
  idProvEditando = pr.id_proveedor;

  document.getElementById('prov_empresa').value = pr.nombre_empresa;
  document.getElementById('prov_contacto').value = pr.contacto;
  document.getElementById('prov_telefono').value = pr.telefono;

  document.getElementById('titulo-form-prov').textContent = 'Editar Proveedor';
  document.getElementById('btn-guardar-prov').textContent = 'Actualizar Proveedor';
  document.getElementById('btn-cancelar-prov').classList.remove('hidden');
}


function cancelarEdicionProv() {
  modoEdicionProv = false;
  idProvEditando = null;

  document.getElementById('form-proveedor').reset();
  document.getElementById('titulo-form-prov').textContent = 'Nuevo Proveedor';
  document.getElementById('btn-guardar-prov').textContent = 'Guardar Proveedor';
  document.getElementById('btn-cancelar-prov').classList.add('hidden');
}

window.prepararEdicionProv = prepararEdicionProv;
window.cancelarEdicionProv = cancelarEdicionProv;

// AGREGAR O ACTUALIZAR PROVEEDOR

document.getElementById('form-proveedor').addEventListener('submit', async (e) => {
  e.preventDefault();

  const datosProveedor = {
    nombre_empresa: document.getElementById('prov_empresa').value,
    contacto: document.getElementById('prov_contacto').value,
    telefono: document.getElementById('prov_telefono').value
  };

  try {
    if (modoEdicionProv) {
      // PUT /api/proveedores/{id}
      await api(`/proveedores/${idProvEditando}`, 'PUT', datosProveedor);
    } else {
      // POST /api/proveedores
      await api('/proveedores', 'POST', datosProveedor);
    }
  } catch (error) {
    alert(error.message);
    return;
  }

  cancelarEdicionProv();
  await cargarProveedores();
});

//ELIMINAR PROVEEDOR

async function eliminarProveedor(id) {
  if (!confirm('¿Deseas eliminar este proveedor?')) return;

  try {
    // DELETE /api/proveedores/{id}
    await api(`/proveedores/${id}`, 'DELETE');
  } catch (error) {
    alert(error.message);
    return;
  }

  await cargarProveedores();
}

window.eliminarProveedor = eliminarProveedor;

init();
