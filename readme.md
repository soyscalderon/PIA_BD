# GAMESTORE

Sitio web para la administracion de inventario, clientes y ventas de una
tienda de videojuegos. El proyecto esta dividido en tres contenedores:
frontend (HTML, CSS y JavaScript puro), backend (API en Python sin frameworks)
y base de datos (MySQL).

## Estructura del proyecto

```
.
├── docker-compose.yml      # Orquesta los tres contenedores
├── .env.example            # Variables opcionales (puertos)
├── database/
│   ├── Dockerfile
│   ├── init.sql            # Esquema, stored procedures, vista y datos iniciales
│   ├── utf8.cnf            # Forza UTF-8 en la carga inicial
│   └── data/               # Archivos de MySQL (se genera sola, ignorada en git)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt    # PyMySQL y cryptography (unicos dependencias)
│   └── app.py              # API REST en Python (http.server)
└── frontend/
    ├── Dockerfile
    ├── nginx.conf          # Sirve los estaticos y hace de proxy hacia la API
    ├── index.html          # Inventario (videojuegos, plataformas, proveedores)
    ├── clientes.html       # Directorio de clientes
    ├── ventas.html         # Procesamiento y historial de ventas
    ├── css/styles.css
    └── js/
        ├── config.js       # Cliente generico de la API (fetch)
        ├── catalogo.js
        ├── clientes.js
        └── ventas.js
```

## Requisitos

- Docker
- Docker Compose (incluido en Docker Desktop o disponible como plugin)

No se necesita instalar Python, MySQL, Node ni ningun otro lenguaje o
framework en la maquina: todo se ejecuta dentro de contenedores.

## Como ejecutar el proyecto

Desde la carpeta raiz del proyecto:

```
docker compose up --build
```

La primera vez se descargan las imagenes, se construyen los contenedores y
MySQL ejecuta automaticamente `database/init.sql` para crear el esquema, los
stored procedures, la vista y los datos de ejemplo.

En una segunda ocasion basta con:

```
docker compose up -d
```

## Como acceder

| Servicio | URL | Puerto |
|----------|-----|--------|
| Frontend | http://localhost:3000 | 3000 (HTTP) |
| API      | http://localhost:8080/api | 8080 (HTTP) |
| MySQL Workbench | https://localhost:3002 | 3001 (HTTPS), 3002 (HTTP) |
| MySQL    | solo dentro de la red de Docker | 3306 |

El frontend consume la API a traves del mismo dominio (`/api/...`), ya que
nginx hace de proxy hacia el contenedor `api` en el puerto 8080. La API tambien
queda expuesta directamente en el puerto 8080 para pruebas con curl o
cualquier cliente REST.

Los puertos se pueden cambiar con las variables de entorno `WEB_PORT` y
`API_PORT` (ver `.env.example`), por ejemplo creando un archivo `.env` con:

```
WEB_PORT=8081
API_PORT=9090
```

## Servicios y dependencias

Declaradas en `docker-compose.yml`:

| Servicio | Construccion | Depende de |
|----------|--------------|------------|
| `db`  | `./database`  | - |
| `api` | `./backend`   | `db` (hasta que el healthcheck responda) |
| `web` | `./frontend`  | `api` |
| `workbench` | imagen `lscr.io/linuxserver/mysql-workbench` | `db` (hasta que el healthcheck responda) |

En MySQL Workbench crear una conexion con Host `db`, Puerto `3306`,
Usuario `gamestore` (o `root`) y la contrasena de `.env`.

La carpeta `./database/data` del propio proyecto queda montada como
`/var/lib/mysql` dentro del contenedor (bind mount), de modo que los datos
permanecen aunque se detengan o reconstruyan los contenedores y se pueden
inspeccionar directamente desde la maquina. Esa carpeta esta ignorada en
`.gitignore` y se crea automaticamente en el primer arranque.

## Base de datos

Esquema normalizado (tercera forma normal), sin datos redundantes:

- `plataforma` (id, nombre, fabricante)
- `proveedor` (id, nombre_empresa, contacto, telefono)
- `videojuego` (id, titulo, FK plataforma, FK proveedor, precio, stock, desarrollador)
- `cliente` (id, nombre, email, direccion)
- `pedido` (id, FK cliente, fecha) - una venta es un pedido
- `detalle_pedido` (FK pedido, FK videojuego, cantidad, precio_unitario) - renglones del pedido

El precio de venta se guarda una sola vez en `detalle_pedido`
(`precio_unitario`), por lo que no se duplica el precio del videojuego ni el
nombre del cliente en cada venta. El total de una venta se calcula como
`cantidad * precio_unitario`.

Elementos adicionales:

- Vista `vw_ventas`: historial de ventas con cliente, videojuego, total y fecha.
- Stored procedure `sp_registrar_cliente`: alta de clientes (boton
  "Guardar Cliente (SP)").
- Stored procedure `sp_procesar_venta`: crea el pedido, registra el detalle y
  descuenta el inventario dentro de una sola transaccion, validando que exista
  stock suficiente (boton "Procesar Venta").
- Restricciones de clave foranea: impiden eliminar plataformas, proveedores,
  videojuegos o clientes que ya esten en uso, y evitan borrar un pedido sin
  devolver el stock al inventario.

Los datos de ejemplo (plataformas, proveedores, videojuegos, clientes y dos
ventas) fueron migrados desde los arreglos JSON que existian originalmente en
los archivos JavaScript; esos archivos ya no almacenan informacion, solo
consultan la API.

## Endpoints de la API

Metodos disponibles (respuestas en JSON):

| Recurso | GET | POST | PUT | DELETE |
|---------|-----|------|-----|--------|
| `/api/plataformas` | lista | crea | - | - |
| `/api/plataformas/{id}` | detalle | - | actualiza | elimina |
| `/api/proveedores` | lista | crea | - | - |
| `/api/proveedores/{id}` | detalle | - | actualiza | elimina |
| `/api/videojuegos` | lista (con plataforma y proveedor) | crea | - | - |
| `/api/videojuegos/{id}` | detalle | - | actualiza | elimina |
| `/api/clientes` | lista | crea (SP) | - | - |
| `/api/clientes/{id}` | detalle | - | actualiza | elimina |
| `/api/ventas` | historial | procesa venta (SP) | - | - |
| `/api/ventas/{id}` | detalle del pedido | - | reemplaza el pedido | elimina y repone stock |

Ejemplo de prueba desde una terminal:

```
curl http://localhost:8080/api/videojuegos
curl -X POST http://localhost:8080/api/ventas \
  -H "Content-Type: application/json" \
  -d '{"id_cliente": 1, "id_videojuego": 1, "cantidad": 2}'
```

Errores devueltos por la API:

- `400` datos invalidos o campos obligatorios faltantes.
- `404` recurso inexistente.
- `409` violacion de integridad (registro en uso, correo duplicado, stock
  insuficiente).
- `500` error interno.

## Comandos utiles

```
docker compose ps                 # Estado de los contenedores
docker compose logs -f api        # Ver los logs de la API
docker compose logs -f db         # Ver los logs de MySQL
docker compose down               # Detener los contenedores (conserva los datos)
rm -rf database/data              # Borrar la base de datos por completo
docker compose up -d --build      # Reconstruir y volver a levantar
```

Para reinicializar la base de datos con los datos de ejemplo se ejecuta
`docker compose down` seguido de `rm -rf database/data` y
`docker compose up -d --build`.
