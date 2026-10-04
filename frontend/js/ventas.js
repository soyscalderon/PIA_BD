// ============================================================================
// VENTAS: el alta se procesa con el stored procedure sp_procesar_venta y el
// historial se consulta desde la vista vw_ventas de MySQL.
// ============================================================================

// INICIALIZACIÓN
async function init() {
  await cargarSelects();
  await cargarVentas();
}


async function cargarSelects() {
  let clientes = [];
  let juegos = [];

  try {
    [clientes, juegos] = await Promise.all([api('/clientes'), api('/videojuegos')]);
  } catch (error) {
    alert(error.message);
    return;
  }

  const selCli = document.getElementById('ven_cliente');
  if (selCli) {
    selCli.innerHTML = '<option value="">Seleccione un cliente</option>';
    clientes.forEach(c => {
      selCli.innerHTML += `<option value="${c.id_cliente}">${c.nombre}</option>`;
    });
  }

  const selJuegos = document.getElementById('ven_juego');
  if (selJuegos) {
    selJuegos.innerHTML = '<option value="">Seleccione un videojuego</option>';
    juegos.forEach(j => {
      selJuegos.innerHTML += `<option value="${j.id_videojuego}">${j.titulo} ($${parseFloat(j.precio).toFixed(2)} - Stock: ${j.stock})</option>`;
    });
  }
}


async function cargarVentas() {
  const tbody = document.getElementById('tabla-ventas');
  if (!tbody) return;
  tbody.innerHTML = '';

  let ventas = [];
  try {
    ventas = await api('/ventas');
  } catch (error) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="py-4 text-center text-rose-500 text-xs">${error.message}</td>
      </tr>
    `;
    return;
  }

  ventas.forEach(v => {
    tbody.innerHTML += `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 font-semibold text-slate-500">#${v.id_pedido}</td>
        <td class="py-3 font-medium text-slate-900">${v.cliente}</td>
        <td class="py-3 text-indigo-600">${v.videojuego}</td>
        <td class="py-3">${v.cantidad}</td>
        <td class="py-3 font-bold text-emerald-600">$${parseFloat(v.total).toFixed(2)}</td>
        <td class="py-3 text-xs text-slate-400">${new Date(v.fecha_pedido).toLocaleString()}</td>
      </tr>
    `;
  });
}


document.getElementById('form-venta').addEventListener('submit', async (e) => {
  e.preventDefault();

  const datosVenta = {
    id_cliente: parseInt(document.getElementById('ven_cliente').value),
    id_videojuego: parseInt(document.getElementById('ven_juego').value),
    cantidad: parseInt(document.getElementById('ven_cantidad').value)
  };

  try {
    // POST /api/ventas -> sp_procesar_venta (valida y descuenta el stock)
    await api('/ventas', 'POST', datosVenta);
  } catch (error) {
    alert(error.message);
    return;
  }

  document.getElementById('form-venta').reset();
  await cargarSelects();
  await cargarVentas();
});

init();
