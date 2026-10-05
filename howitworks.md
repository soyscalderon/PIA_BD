# How GameStore Works

This document explains the runtime architecture of the project: how the three
Docker containers cooperate, how the JavaScript in the frontend talks to the
API, and how `backend/app.py` orchestrates every request between the browser
and the MySQL database.

```
Browser (http://localhost:3000)
        │
        ▼
┌─────────────────────────┐        ┌──────────────────────────────┐
│  web  (nginx)           │        │  api  (Python http.server)   │
│  - serves HTML/CSS/JS   │  /api  │  backend/app.py              │
│  - proxies /api/ ───────┼──────► │  - validates JSON            │
└─────────────────────────┘        │  - builds SQL                │
                                   │  - runs SPs / view           │
                                   └──────────────┬───────────────┘
                                                  │ PyMySQL (3306)
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  db  (MySQL 8.0)             │
                                   │  database/init.sql           │
                                   └──────────────────────────────┘
```

All three containers live on the same Docker network, so they reach each other
by **service name**: `web` calls `http://api:8080`, and `api` connects to host
`db`. Nothing but the published ports (`3000` and `8080`) is exposed to the
host machine.

---

## 1. The Docker containers

Everything is declared in `docker-compose.yml`. Running `docker compose up
--build` builds and starts the whole stack.

### Service `db` (MySQL)

- Built from `database/Dockerfile`: the official `mysql:8.0` image plus
  `database/init.sql`, which is copied to `/docker-entrypoint-initdb.d/` so
  MySQL executes it **automatically on the first boot** (schema, stored
  procedures, view and sample data).
- `database/data` is bind-mounted to `/var/lib/mysql`, so the data files live
  inside the project folder and survive `docker compose down`.
- Credentials come from `.env` (`MYSQL_USER=gamestore`, `MYSQL_PASSWORD=gamestore`...)
  and are injected as environment variables.
- A **healthcheck** (`mysqladmin ping` every 5s) marks the container as
  `healthy` only when MySQL really accepts connections.

### Service `api` (Python)

- Built from `backend/Dockerfile`: `python:3.12-slim`, installs
  `requirements.txt` (`PyMySQL` + `cryptography`) and runs `python -u app.py`.
- `depends_on: db: condition: service_healthy` → compose waits until MySQL is
  healthy before starting the API. On top of that, `app.py` calls
  `esperar_bd()` (`backend/app.py:51`), which retries the connection for up to
  2 minutes, so a slow MySQL never crashes the API.
- Receives its database credentials through environment variables
  (`DB_HOST=db`, `DB_USER=gamestore`, ...), read at `backend/app.py:17-26`.
  The same code works against any MySQL just by changing those variables.
- Publishes `${API_PORT:-8080}:8080`, so you can also test the API directly
  with `curl http://localhost:8080/api`.

### Service `web` (nginx)

- Built from `frontend/Dockerfile`: the `nginx:1.27-alpine` image with the
  three HTML pages, `css/`, `js/` and a custom `frontend/nginx.conf`.
- Listens on port 80 inside the container, published as `3000` on the host.
- Serves the static files and, crucially, **acts as a reverse proxy**: any
  request to `/api/...` is forwarded to `http://api:8080` (`nginx.conf:16-25`).
  That is why the frontend can use a relative URL (`const API_URL = "/api"`)
  and there are **no CORS problems** in normal use (the API still sends CORS
  headers anyway, `backend/app.py:566-569`, in case you call it directly on
  port 8080).

### Startup order

```
db (healthy)  →  api (waits for db, then serves)  →  web (waits for api)
```

`docker compose down` stops everything but keeps `database/data`; deleting
that folder and running `up --build` resets the database to the sample data.

---

## 2. The frontend (HTML + vanilla JavaScript)

There is **no framework and no build step**: plain HTML, Tailwind (CDN) and
ES2017 JavaScript. nginx just copies the files into the image and serves them.

### Files

| File | Page | Scripts loaded (in order) |
|------|------|---------------------------|
| `index.html` | Inventory: videojuegos, plataformas, proveedores (tabs) | `js/config.js` → `js/catalogo.js` |
| `clientes.html` | Client directory | `js/config.js` → `js/clientes.js` |
| `ventas.html` | Sale form + sales history | `js/config.js` → `js/ventas.js` |

The **order matters**: `config.js` must load first because it defines the
global function `api()` that every other file uses.

### 2.1 `js/config.js` — the API client

This is the single bridge between the UI and the backend:

```js
const API_URL = "/api";

async function api(ruta, metodo = "GET", cuerpo = null) {
  const opciones = { method: metodo, headers: {} };
  if (cuerpo !== null) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);          // object → JSON text
  }
  const respuesta = await fetch(`${API_URL}${ruta}`, opciones);
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    throw new Error(datos.error || "No se pudo completar la operacion.");
  }
  return datos;                                       // parsed JSON body
}
```

How to read it:

- `api('/videojuegos')` → `GET  /api/videojuegos`
- `api('/videojuegos', 'POST', datos)` → `POST /api/videojuegos` with a JSON
  body built from the `datos` object.
- `api('/videojuegos/3', 'PUT', datos)` → `PUT  /api/videojuegos/3`
- `api('/videojuegos/3', 'DELETE')` → `DELETE /api/videojuegos/3`
- Any non-2xx response **throws** an `Error` whose message is the `{"error": ...}`
  field returned by the API, which is why the pages can simply do
  `catch (error) { alert(error.message) }`.

Because the request goes to `/api/...` on the same origin, nginx forwards it
to the Python container transparently.

### 2.2 `js/catalogo.js` — inventory (index.html)

Responsibilities: render three tables, fill two `<select>` dropdowns, and
handle create/edit/delete for videojuegos, plataformas and proveedores.

State kept at the top of the file:

```js
let plataformasDB = [], proveedoresDB = [], videojuegosDB = [];  // last API data
let modoEdicionJuego = false; let idJuegoEditando = null;        // edit-mode flags
// ... the same pair of flags exists for plataformas and proveedores
```

Flow:

1. **`init()`** (called at the bottom of the file) runs
   `cargarPlataformas()` → `cargarProveedores()` → `cargarJuegos()` in
   sequence. Each loader calls `api(...)`, stores the array in the module
   variable, and rebuilds the `<tbody>` by concatenating an HTML string per
   row (`innerHTML +=`).
2. **Dropdowns**: `cargarPlataformas()` and `cargarProveedores()` also fill
   `#juego_plataforma` and `#juego_proveedor` so the video game form can
   reference them by id.
3. **Create / update share one form.** The `submit` listener on
   `#form-juego` reads the inputs, builds `datosJuego`, and then branches:

   ```js
   if (modoEdicionJuego) await api(`/videojuegos/${idJuegoEditando}`, 'PUT', datosJuego);
   else                   await api('/videojuegos', 'POST', datosJuego);
   ```

   Afterwards it always calls `cancelarEdicionJuego()` (resets the form and
   flags) and `cargarJuegos()` to refresh the table with the new data coming
   back from MySQL.
4. **Edit mode** is entered by `prepararEdicionJuego(id)`, triggered from the
   inline `onclick="prepararEdicionJuego(...)"` on each row. It looks up the
   record in the cached `videojuegosDB` array, copies the values into the
   inputs, changes the titles to "Editar / Actualizar", and reveals the
   cancel button.
5. **Delete** asks for confirmation, calls `DELETE /api/videojuegos/{id}`, and
   reloads. If the API answers `409` (record referenced by sales), the thrown
   message is shown with `alert()`.
6. **Tabs** are pure DOM: `cambiarTab(tab)` hides every `.tab-content` and
   shows `#tab-<name>` (exposed as `window.cambiarTab` so the HTML
   `onclick="cambiarTab('...')"` works).

`clientes.js` follows exactly the same pattern (state flags, loader, shared
form with `modoEdicionCliente`), with the difference that a **new** client is
created through the stored procedure (`POST /api/clientes` →
`sp_registrar_cliente`), while updates use a plain `PUT`.

### 2.3 `js/ventas.js` — sales

- `cargarSelects()` fills the two dropdowns (clientes and videojuegos) with
  `Promise.all([api('/clientes'), api('/videojuegos')])`, i.e. both requests
  run **in parallel**.
- `cargarVentas()` renders the history from `GET /api/ventas`, which the API
  answers from the MySQL view `vw_ventas` (already joined and with `total`
  precomputed).
- The form submits `POST /api/ventas` with
  `{id_cliente, id_videojuego, cantidad}`; the backend executes
  `sp_procesar_venta`, which validates stock and discounts inventory in one
  transaction. Success → the selects and the table are reloaded so the new
  stock appears.

### 2.4 Rendering and error handling conventions

- Rows are built with template literals and injected with `innerHTML +=`.
- Failures inside a loader are caught by `mensajeError(tbody, columnas, error)`
  (or an inline equivalent), which renders a red row with the API message,
  so a down API never blanks the page silently.
- Failures inside a submit/delete are shown with `alert(error.message)`.
- After every successful mutation the corresponding loader is re-run: the
  **database is the single source of truth**, the JS keeps no local copy of
  the data beyond the arrays used for quick lookups.

---

## 3. The backend — `backend/app.py`

A single 626-line file, standard library only (`http.server`) plus PyMySQL.
No Flask/FastAPI: `BaseHTTPRequestHandler` gives us `do_GET/do_POST/do_PUT/
do_DELETE`, and everything else is our own code. The file is organized in
layers, each one only calling the layer below.

### 3.1 Configuration and the database layer

- `CONFIG_BD` (`app.py:17`) builds the PyMySQL connection arguments from
  environment variables, with `autocommit=False` (explicit transactions) and
  `DictCursor` (rows come back as dictionaries, which `json.dumps` can
  serialize directly and which match the keys the JS expects, e.g.
  `id_videojuego`, `titulo`, `stock`).
- `conectar()` → a fresh connection.
- `esperar_bd()` → startup retry loop used by `principal()`.
- `ejecutar(sql, argumentos)` (`app.py:64`) is the workhorse:
  connect → `cursor.execute(sql, args)` (**parameterized**: the `%s`
  placeholders prevent SQL injection) → `commit()` → on any exception
  `rollback()` → always `close()`.
- `ejecutar_procedimiento()` (`app.py:86`) is the same, but walks
  `cursor.nextset()` because `CALL sp_...` can return several result sets
  (the SP's `SELECT` of the new id, for example).

### 3.2 The `CONFIG` resource table — generic CRUD

Instead of writing four near-identical CRUD implementations, `app.py:112`
declares a dictionary describing each resource:

```python
"videojuegos": {
    "tabla": "videojuego",
    "pk": "id_videojuego",
    "campos": {"titulo": (str, None), "id_plataforma": (int, 1),
               "precio": (float, 0.01), "stock": (int, 0), ...},
    "listado": "SELECT ... INNER JOIN plataforma ... INNER JOIN proveedor ...",
    "en_uso": "No se puede eliminar el videojuego porque tiene ventas registradas.",
}
```

- `tabla` / `pk` → which table and primary key to use.
- `campos` → field name → (Python type, minimum value). Used by `validar()`.
- `listado` → the `SELECT` for `GET /api/<recurso>`; `videojuegos` uses
  `INNER JOIN` so the response already contains the platform/provider names
  (the JS uses `j.plataforma` directly).
- `en_uso` → the friendly message shown when a foreign key blocks a delete.
- `clientes` additionally declares `"procedimiento"`, which redirects the
  `POST` from a plain `INSERT` to `CALL sp_registrar_cliente(%s, %s, %s)`.

The single function `crud(recurso, metodo, identificador, cuerpo)`
(`app.py:232`) then implements the four verbs for all of them:

| HTTP | Behavior |
|------|----------|
| `GET /api/x` | `listado` query → 200 + array |
| `GET /api/x/{id}` | `SELECT * ... WHERE pk = %s` → 200 or 404 (`NoEncontrado`) |
| `POST /api/x` | `validar()` → build `INSERT` (or `CALL sp_...`) → 201 + the freshly selected row |
| `PUT /api/x/{id}` | `validar()` → build `UPDATE ... SET a=%s, b=%s WHERE pk=%s` → 200 + new row; `afectadas == 0` distinguishes 404 from a no-op |
| `DELETE /api/x/{id}` | `DELETE ... WHERE pk=%s` → 200 or 404; integrity errors → 409 |

`validar()` (`app.py:180`) is the input gate: it rejects non-object JSON,
missing/empty fields, wrong types (`int()`/`float()` conversions) and values
below the configured minimum, raising `DatosInvalidos` → HTTP 400.

### 3.3 `ventas` — the special resource

Sales cannot use the generic CRUD because a sale spans three tables
(`pedido`, `detalle_pedido`, `videojuego.stock`), so `crud_ventas()`
(`app.py:448`) implements the four verbs by hand:

- **GET** → reads the view `vw_ventas` (list, or all lines of one
  `id_pedido`).
- **POST** → `CALL sp_procesar_venta(cliente, juego, cantidad)`: the stored
  procedure validates the client, locks the row with `FOR UPDATE`, checks the
  stock, inserts `pedido` + `detalle_pedido`, subtracts stock and commits —
  all inside one transaction with an `EXIT HANDLER` that rolls back on any
  error. The API returns `201` plus the new `id_pedido`.
- **PUT** → `actualizar_venta()` (`app.py:363`) performs a manual transaction
  with `SELECT ... FOR UPDATE` locks: restore the stock of the old lines,
  delete them, change the client, then insert the new line and discount the
  new stock (or raise `400` if stock is insufficient).
- **DELETE** → `eliminar_venta()` (`app.py:418`) returns the stock of every
  line to inventory and deletes the order (the FK `ON DELETE CASCADE` removes
  the details).

### 3.4 Routing

`despachar(metodo, ruta, cuerpo)` (`app.py:516`) is a tiny hand-rolled
router:

1. Split the path on `/`; the first segment must be `api`, otherwise 404.
2. `GET /api` → an info banner listing the available resources.
3. Second segment = resource, optional third segment = numeric id
   (`/api/videojuegos/3` → `recurso="videojuegos"`, `identificador=3`).
4. `ventas` goes to `crud_ventas`, anything else present in `CONFIG` goes to
   `crud`, everything else raises `NoEncontrado`.

### 3.5 The HTTP layer

`ManejadorHTTP` (`app.py:546`) bridges HTTP and `despachar()`:

- `do_GET/POST/PUT/DELETE` all delegate to `atender(metodo)`.
- `leer_cuerpo()` reads `Content-Length` bytes and `json.loads()` them
  (POST/PUT only).
- `atender()` wraps the call in `try/except` and maps our exceptions to
  status codes:

  | Exception / condition | HTTP |
  |------------------------|------|
  | `DatosInvalidos` | 400 |
  | `NoEncontrado` | 404 |
  | `IntegrityError 1451` (FK in use) | 409 + `cfg["en_uso"]` |
  | `IntegrityError 1452` (bad reference) | 409 "La referencia indicada no existe." |
  | `IntegrityError 1062` (duplicate) | 409 "Ya existe un registro con esos datos unicos." |
  | other `MySQLError` (e.g. "Stock insuficiente" from an SP) | 409 |
  | anything else | 500 |

  (`traducir_error()` at `app.py:211` does this translation.)
- `responder()` serializes with `json.dumps(..., default=_serializar)`
  (dates → ISO strings) and adds the CORS headers.
- `do_OPTIONS` answers `204` to CORS preflight requests.
- `principal()` waits for the DB and then starts
  `ThreadingHTTPServer(("0.0.0.0", 8080))`, so every request runs in its own
  thread and can hold its own DB connection.

---

## 4. The database

`database/init.sql` runs once on first boot. It creates:

| Table | Purpose |
|-------|---------|
| `plataforma` | console/platform catalog |
| `proveedor` | supplier catalog |
| `videojuego` | inventory; FK → plataforma, proveedor |
| `cliente` | customers |
| `pedido` | one sale/order; FK → cliente |
| `detalle_pedido` | order lines: juego, cantidad, `precio_unitario` |

Plus:

- **View `vw_ventas`** — joins `detalle_pedido + pedido + cliente + videojuego`
  and computes `total = cantidad * precio_unitario`. It is what
  `GET /api/ventas` reads, which is why the sales table arrives already
  resolved and calculated.
- **`sp_registrar_cliente`** — inserts a client and `SELECT`s
  `LAST_INSERT_ID()`.
- **`sp_procesar_venta`** — the transactional heart of a sale (validate →
  lock → insert → discount stock → commit).
- **Foreign keys** (`ON DELETE RESTRICT` / `CASCADE`) — they are what turns a
  "delete a platform that still has games" or "delete a client with sales"
  into a `1451` error, which the API converts into a `409` with a friendly
  Spanish message that the frontend shows via `alert()`.

---

## 5. End-to-end walkthroughs

### Create a video game (index.html)

1. The user fills `#form-juego` and presses *Guardar Videojuego*.
2. `catalogo.js` builds `datosJuego` and calls
   `api('/videojuegos', 'POST', datosJuego)`.
3. `fetch` → `POST http://localhost:3000/api/videojuegos` → nginx matches
   `location /api/` → proxies to `http://api:8080/api/videojuegos`.
4. `ManejadorHTTP.do_POST` → `atender` → `despachar` → `crud("videojuegos",
   "POST", None, cuerpo)`.
5. `validar()` type-checks the fields; a `INSERT INTO videojuego (...) VALUES
   (%s, ...)` is executed and committed.
6. The API selects the new row and answers `201` with it.
7. The JS receives the object, leaves edit mode and calls `cargarJuegos()`,
   which issues `GET /api/videojuegos` → the JOIN query → the table re-renders
   with the new row.

### Process a sale (ventas.html)

1. `ventas.js` sends `{id_cliente, id_videojuego, cantidad}`.
2. `crud_ventas("POST", ...)` runs `CALL sp_procesar_venta(...)`.
3. MySQL validates stock (row locked with `FOR UPDATE`), inserts `pedido` and
   `detalle_pedido`, subtracts the stock, commits and returns the new
   `id_pedido`.
4. The API answers `201 {"mensaje": ..., "id_pedido": 7}`.
5. The page reloads the selects (new stock values) and the history from
   `vw_ventas`.

### Delete a platform that is still in use

1. `DELETE /api/plataformas/1`.
2. MySQL rejects it with error `1451` (foreign key constraint).
3. `traducir_error()` maps it to `409` and `crud()` replaces the text with
   `cfg["en_uso"]`.
4. `api()` throws → `alert("No se puede eliminar la plataforma porque esta
   asignada a uno o varios videojuegos.")`.

---

## 6. Quick reference

| Where | What to look at |
|-------|-----------------|
| Ports | `web` 3000 → nginx 80, `api` 8080, `db` 3306 (internal only) |
| Frontend entry point per page | `js/config.js` then the page script |
| API client | `frontend/js/config.js` → `api(ruta, metodo, cuerpo)` |
| Resource/CRUD definitions | `backend/app.py:112` → `CONFIG` |
| Generic CRUD | `backend/app.py:232` → `crud()` |
| Sales logic | `backend/app.py:363/418/448` |
| Router | `backend/app.py:516` → `despachar()` |
| HTTP + error mapping | `backend/app.py:546` → `ManejadorHTTP`, `:211` → `traducir_error` |
| Schema / SPs / view | `database/init.sql` |

Useful commands:

```bash
docker compose up --build        # build + start everything
docker compose logs -f api       # follow the Python API logs
docker compose logs -f db        # follow MySQL logs
docker compose down              # stop (data in database/data is kept)
curl http://localhost:8080/api/videojuegos    # test the API directly
```
