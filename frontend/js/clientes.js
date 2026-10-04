// ============================================================================
// CLIENTES: el listado y el alta se hacen contra la API (MySQL).
// El alta utiliza el stored procedure sp_registrar_cliente.
// ============================================================================

let clientesDB = [];

// VARIABLES QUE DEFINEN EL COMPORTAMIENTO DEL FORMULARIO
let modoEdicionCliente = false;
let idClienteEditando = null;

// INICIALIZACIÓN
function init() {
  cargarClientes();
}

async function cargarClientes() {
  const tbody = document.getElementById('tabla-clientes');
  if (!tbody) return;
  tbody.innerHTML = '';

  try {
    clientesDB = await api('/clientes');
  } catch (error) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-4 text-center text-rose-500 text-xs">${error.message}</td>
      </tr>
    `;
    return;
  }

  clientesDB.forEach(c => {
    tbody.innerHTML += `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 font-semibold text-slate-500">#${c.id_cliente}</td>
        <td class="py-3 font-semibold text-slate-900">${c.nombre}</td>
        <td class="py-3 text-indigo-600">${c.email}</td>
        <td class="py-3 text-slate-500">${c.direccion}</td>
        <td class="py-3 text-right space-x-2">
          <button onclick="prepararEdicionCliente(${c.id_cliente})"
            class="text-amber-600 hover:text-amber-800 font-medium text-xs">
            <i class="fa-solid fa-pen"></i> Editar
          </button>
          <button onclick="eliminarCliente(${c.id_cliente})"
            class="text-rose-600 hover:text-rose-800 font-medium text-xs">
            <i class="fa-solid fa-trash"></i> Eliminar
          </button>
        </td>
      </tr>
    `;
  });
}

function prepararEdicionCliente(id) {
  const c = clientesDB.find(item => item.id_cliente === id);
  if (!c) return;

  modoEdicionCliente = true;
  idClienteEditando = c.id_cliente;

  document.getElementById('cli_nombre').value = c.nombre;
  document.getElementById('cli_email').value = c.email;
  document.getElementById('cli_direccion').value = c.direccion;

  document.getElementById('titulo-form-cliente').textContent = 'Editar Cliente';
  document.getElementById('btn-guardar-cliente').textContent = 'Actualizar Cliente';
  document.getElementById('btn-cancelar-cliente').classList.remove('hidden');
}

function cancelarEdicionCliente() {
  modoEdicionCliente = false;
  idClienteEditando = null;

  document.getElementById('form-cliente').reset();
  document.getElementById('titulo-form-cliente').textContent = 'Registrar Cliente';
  document.getElementById('btn-guardar-cliente').textContent = 'Guardar Cliente';
  document.getElementById('btn-cancelar-cliente').classList.add('hidden');
}

window.prepararEdicionCliente = prepararEdicionCliente;
window.cancelarEdicionCliente = cancelarEdicionCliente;


document.getElementById('form-cliente').addEventListener('submit', async (e) => {
  e.preventDefault();

  const datosCliente = {
    nombre: document.getElementById('cli_nombre').value,
    email: document.getElementById('cli_email').value,
    direccion: document.getElementById('cli_direccion').value
  };

  try {
    if (modoEdicionCliente) {
      // PUT /api/clientes/{id}
      await api(`/clientes/${idClienteEditando}`, 'PUT', datosCliente);
    } else {
      // POST /api/clientes -> sp_registrar_cliente
      await api('/clientes', 'POST', datosCliente);
    }
  } catch (error) {
    alert(error.message);
    return;
  }

  cancelarEdicionCliente();
  await cargarClientes();
});


async function eliminarCliente(id) {
  if (!confirm('¿Deseas eliminar este cliente?')) return;

  try {
    // DELETE /api/clientes/{id}
    await api(`/clientes/${id}`, 'DELETE');
  } catch (error) {
    alert(error.message);
    return;
  }

  await cargarClientes();
}

window.eliminarCliente = eliminarCliente;

init();
