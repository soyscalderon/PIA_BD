"""
GAMESTORE - API en Python usando unicamente la libreria estandar (http.server)
y el driver PyMySQL para conectar a MySQL. No se utiliza ningun framework.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pymysql
from pymysql.err import IntegrityError, MySQLError

PUERTO = int(os.environ.get("API_PORT", "8080"))

CONFIG_BD = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "gamestore"),
    "password": os.environ.get("DB_PASSWORD", "gamestore"),
    "database": os.environ.get("DB_NAME", "gamestore"),
    "charset": "utf8mb4",
    "autocommit": False,
    "cursorclass": pymysql.cursors.DictCursor,
}

RECURSOS = ["plataformas", "proveedores", "videojuegos", "clientes", "ventas"]


# ----------------------------------------------------------------------------
# Excepciones de la aplicacion
# ----------------------------------------------------------------------------

class DatosInvalidos(Exception):
    """Error de validacion de la peticion (HTTP 400)."""


class NoEncontrado(Exception):
    """Recurso inexistente (HTTP 404)."""


# ----------------------------------------------------------------------------
# Conexion a la base de datos
# ----------------------------------------------------------------------------

def conectar():
    return pymysql.connect(**CONFIG_BD)


def esperar_bd(intentos=60, espera=2):
    ultimo_error = None
    for _ in range(intentos):
        try:
            conexion = conectar()
            conexion.close()
            return
        except MySQLError as error:
            ultimo_error = error
            time.sleep(espera)
    raise ultimo_error


def ejecutar(sql, argumentos=None, traer_filas=True):
    """Ejecuta una sentencia y confirma la transaccion."""
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, argumentos or ())
            filas = cursor.fetchall() if traer_filas else None
            ultimo_id = cursor.lastrowid
            afectadas = cursor.rowcount
        conexion.commit()
        return {"filas": filas, "ultimo_id": ultimo_id, "afectadas": afectadas}
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def insertar(sql, argumentos=None):
    return ejecutar(sql, argumentos, traer_filas=False)["ultimo_id"]


def ejecutar_procedimiento(sql, argumentos=None):
    """Ejecuta un CALL y recorre todos los result sets que devuelva."""
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, argumentos or ())
            ultimo_id = cursor.lastrowid
            filas = []
            while True:
                if cursor.description is not None:
                    filas = cursor.fetchall()
                if not cursor.nextset():
                    break
        conexion.commit()
        return {"filas": filas, "ultimo_id": ultimo_id}
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


# ----------------------------------------------------------------------------
# Definicion de los recursos con CRUD generico
# ----------------------------------------------------------------------------

CONFIG = {
    "plataformas": {
        "tabla": "plataforma",
        "pk": "id_plataforma",
        "etiqueta": "la plataforma",
        "mensaje_eliminado": "Plataforma eliminada correctamente.",
        "campos": {
            "nombre": (str, None),
            "fabricante": (str, None),
        },
        "listado": "SELECT * FROM plataforma ORDER BY id_plataforma",
        "en_uso": "No se puede eliminar la plataforma porque esta asignada a uno o varios videojuegos.",
    },
    "proveedores": {
        "tabla": "proveedor",
        "pk": "id_proveedor",
        "etiqueta": "el proveedor",
        "mensaje_eliminado": "Proveedor eliminado correctamente.",
        "campos": {
            "nombre_empresa": (str, None),
            "contacto": (str, None),
            "telefono": (str, None),
        },
        "listado": "SELECT * FROM proveedor ORDER BY id_proveedor",
        "en_uso": "No se puede eliminar el proveedor porque esta asignado a uno o varios videojuegos.",
    },
    "videojuegos": {
        "tabla": "videojuego",
        "pk": "id_videojuego",
        "etiqueta": "el videojuego",
        "mensaje_eliminado": "Videojuego eliminado correctamente.",
        "campos": {
            "titulo": (str, None),
            "id_plataforma": (int, 1),
            "id_proveedor": (int, 1),
            "precio": (float, 0.01),
            "stock": (int, 0),
            "desarrollador": (str, None),
        },
        "listado": (
            "SELECT j.id_videojuego, j.titulo, j.id_plataforma, j.id_proveedor, "
            "j.precio, j.stock, j.desarrollador, "
            "p.nombre AS plataforma, pr.nombre_empresa AS proveedor "
            "FROM videojuego j "
            "INNER JOIN plataforma p ON p.id_plataforma = j.id_plataforma "
            "INNER JOIN proveedor pr ON pr.id_proveedor = j.id_proveedor "
            "ORDER BY j.id_videojuego"
        ),
        "en_uso": "No se puede eliminar el videojuego porque tiene ventas registradas.",
    },
    "clientes": {
        "tabla": "cliente",
        "pk": "id_cliente",
        "etiqueta": "el cliente",
        "mensaje_eliminado": "Cliente eliminado correctamente.",
        "campos": {
            "nombre": (str, None),
            "email": (str, None),
            "direccion": (str, None),
        },
        "listado": "SELECT * FROM cliente ORDER BY id_cliente",
        "en_uso": "No se puede eliminar el cliente porque tiene ventas asignadas.",
        # El alta de clientes se realiza con un stored procedure.
        "procedimiento": ("CALL sp_registrar_cliente(%s, %s, %s)", ["nombre", "email", "direccion"]),
    },
}


def validar(cfg, cuerpo):
    """Convierte y valida los campos enviados por el cliente."""
    if not isinstance(cuerpo, dict):
        raise DatosInvalidos("El cuerpo de la peticion debe ser un JSON valido.")

    valores = {}
    for campo, (tipo, minimo) in cfg["campos"].items():
        if campo not in cuerpo or cuerpo[campo] is None or cuerpo[campo] == "":
            raise DatosInvalidos("El campo '%s' es obligatorio." % campo)

        valor = cuerpo[campo]
        try:
            if tipo is int:
                valor = int(valor)
            elif tipo is float:
                valor = float(valor)
            else:
                valor = str(valor).strip()
        except (TypeError, ValueError):
            raise DatosInvalidos("El campo '%s' no tiene un formato valido." % campo)

        if tipo is str and not valor:
            raise DatosInvalidos("El campo '%s' es obligatorio." % campo)
        if minimo is not None and valor < minimo:
            raise DatosInvalidos(
                "El campo '%s' debe ser mayor o igual a %s." % (campo, minimo)
            )
        valores[campo] = valor
    return valores


def traducir_error(error):
    """Convierte errores de MySQL en respuestas HTTP amigables."""
    if isinstance(error, IntegrityError):
        codigo = error.args[0]
        if codigo == 1451:
            return 409, "El registro no puede eliminarse porque esta referenciado por otros datos."
        if codigo == 1452:
            return 409, "La referencia indicada no existe."
        if codigo == 1062:
            return 409, "Ya existe un registro con esos datos unicos."
        return 409, "Violacion de integridad de datos."
    if isinstance(error, MySQLError):
        mensaje = error.args[1] if len(error.args) > 1 else str(error)
        return 409, mensaje
    return 500, "Error interno del servidor: %s" % error


# ----------------------------------------------------------------------------
# CRUD generico: plataformas, proveedores, videojuegos y clientes
# ----------------------------------------------------------------------------

def crud(recurso, metodo, identificador, cuerpo):
    cfg = CONFIG[recurso]
    tabla, pk = cfg["tabla"], cfg["pk"]

    if metodo == "GET":
        if identificador is None:
            return 200, ejecutar(cfg["listado"])["filas"]
        filas = ejecutar(
            "SELECT * FROM %s WHERE %s = %%s" % (tabla, pk), (identificador,)
        )["filas"]
        if not filas:
            raise NoEncontrado("No existe %s con id %s." % (cfg["etiqueta"], identificador))
        return 200, filas[0]

    if metodo == "POST":
        if identificador is not None:
            raise NoEncontrado("Ruta no encontrada.")
        valores = validar(cfg, cuerpo)
        if "procedimiento" in cfg:
            procedimiento, orden = cfg["procedimiento"]
            argumentos = tuple(valores[campo] for campo in orden)
        else:
            columnas = ", ".join(valores.keys())
            marcadores = ", ".join(["%s"] * len(valores))
            procedimiento = "INSERT INTO %s (%s) VALUES (%s)" % (
                tabla, columnas, marcadores,
            )
            argumentos = tuple(valores.values())
        try:
            resultado = ejecutar_procedimiento(procedimiento, argumentos)
            nuevo_id = resultado["ultimo_id"]
            if not nuevo_id and resultado["filas"]:
                # El SP devuelve el id recien creado como result set.
                nuevo_id = list(resultado["filas"][0].values())[0]
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            if codigo == 409 and "referenciado" in mensaje:
                mensaje = cfg["en_uso"]
            return codigo, {"error": mensaje}
        if not nuevo_id:
            return 201, {"mensaje": "Registro creado correctamente."}
        fila = ejecutar(
            "SELECT * FROM %s WHERE %s = %%s" % (tabla, pk), (nuevo_id,)
        )["filas"][0]
        return 201, fila

    if metodo == "PUT":
        if identificador is None:
            raise DatosInvalidos("Falta el identificador del registro a actualizar.")
        valores = validar(cfg, cuerpo)
        if pk in valores:
            del valores[pk]
        if not valores:
            raise DatosInvalidos("No se recibieron campos para actualizar.")
        asignaciones = ", ".join("%s = %%s" % columna for columna in valores)
        argumentos = tuple(valores.values()) + (identificador,)
        try:
            resultado = ejecutar(
                "UPDATE %s SET %s WHERE %s = %%s" % (tabla, asignaciones, pk),
                argumentos,
                traer_filas=False,
            )
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            return codigo, {"error": mensaje}
        if resultado["afectadas"] == 0:
            existe = ejecutar(
                "SELECT 1 FROM %s WHERE %s = %%s" % (tabla, pk), (identificador,)
            )["filas"]
            if not existe:
                raise NoEncontrado(
                    "No existe %s con id %s." % (cfg["etiqueta"], identificador)
                )
        fila = ejecutar(
            "SELECT * FROM %s WHERE %s = %%s" % (tabla, pk), (identificador,)
        )["filas"][0]
        return 200, fila

    if metodo == "DELETE":
        if identificador is None:
            raise DatosInvalidos("Falta el identificador del registro a eliminar.")
        try:
            resultado = ejecutar(
                "DELETE FROM %s WHERE %s = %%s" % (tabla, pk),
                (identificador,),
                traer_filas=False,
            )
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            if codigo == 409 and "referenciado" in mensaje:
                mensaje = cfg["en_uso"]
            return codigo, {"error": mensaje}
        if resultado["afectadas"] == 0:
            raise NoEncontrado(
                "No existe %s con id %s." % (cfg["etiqueta"], identificador)
            )
        return 200, {"mensaje": cfg["mensaje_eliminado"]}

    raise DatosInvalidos("Metodo %s no permitido sobre /api/%s." % (metodo, recurso))


# ----------------------------------------------------------------------------
# Ventas (pedidos)
# ----------------------------------------------------------------------------

LISTADO_VENTAS = (
    "SELECT * FROM vw_ventas ORDER BY fecha_pedido DESC, id_pedido DESC, id_videojuego"
)


def validar_venta(cuerpo):
    if not isinstance(cuerpo, dict):
        raise DatosInvalidos("El cuerpo de la peticion debe ser un JSON valido.")
    datos = {}
    for campo, tipo, minimo in (
        ("id_cliente", int, 1),
        ("id_videojuego", int, 1),
        ("cantidad", int, 1),
    ):
        if campo not in cuerpo or cuerpo[campo] in (None, ""):
            raise DatosInvalidos("El campo '%s' es obligatorio." % campo)
        try:
            valor = int(cuerpo[campo])
        except (TypeError, ValueError):
            raise DatosInvalidos("El campo '%s' no tiene un formato valido." % campo)
        if valor < minimo:
            raise DatosInvalidos("El campo '%s' debe ser mayor o igual a %s." % (campo, minimo))
        datos[campo] = valor
    return datos


def actualizar_venta(id_pedido, datos):
    """Reemplaza el contenido de un pedido: cliente, videojuego y cantidad."""
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id_pedido FROM pedido WHERE id_pedido = %s FOR UPDATE", (id_pedido,))
            if not cursor.fetchone():
                conexion.rollback()
                return False

            cursor.execute(
                "SELECT id_videojuego, cantidad FROM detalle_pedido WHERE id_pedido = %s FOR UPDATE",
                (id_pedido,),
            )
            renglones = cursor.fetchall()
            for renglon in renglones:
                cursor.execute(
                    "UPDATE videojuego SET stock = stock + %s WHERE id_videojuego = %s",
                    (renglon["cantidad"], renglon["id_videojuego"]),
                )

            cursor.execute("DELETE FROM detalle_pedido WHERE id_pedido = %s", (id_pedido,))
            cursor.execute(
                "UPDATE pedido SET id_cliente = %s WHERE id_pedido = %s",
                (datos["id_cliente"], id_pedido),
            )

            cursor.execute(
                "SELECT stock, precio FROM videojuego WHERE id_videojuego = %s FOR UPDATE",
                (datos["id_videojuego"],),
            )
            juego = cursor.fetchone()
            if not juego:
                raise DatosInvalidos("El videojuego indicado no existe.")
            if juego["stock"] < datos["cantidad"]:
                raise DatosInvalidos("Stock insuficiente para procesar la venta.")

            cursor.execute(
                "INSERT INTO detalle_pedido (id_pedido, id_videojuego, cantidad, precio_unitario) "
                "VALUES (%s, %s, %s, %s)",
                (id_pedido, datos["id_videojuego"], datos["cantidad"], juego["precio"]),
            )
            cursor.execute(
                "UPDATE videojuego SET stock = stock - %s WHERE id_videojuego = %s",
                (datos["cantidad"], datos["id_videojuego"]),
            )
        conexion.commit()
        return True
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def eliminar_venta(id_pedido):
    """Elimina un pedido y devuelve al inventario el stock descontado."""
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id_videojuego, cantidad FROM detalle_pedido WHERE id_pedido = %s FOR UPDATE",
                (id_pedido,),
            )
            renglones = cursor.fetchall()
            if not renglones:
                cursor.execute("SELECT 1 FROM pedido WHERE id_pedido = %s", (id_pedido,))
                if not cursor.fetchone():
                    conexion.rollback()
                    return False
            for renglon in renglones:
                cursor.execute(
                    "UPDATE videojuego SET stock = stock + %s WHERE id_videojuego = %s",
                    (renglon["cantidad"], renglon["id_videojuego"]),
                )
            cursor.execute("DELETE FROM pedido WHERE id_pedido = %s", (id_pedido,))
        conexion.commit()
        return True
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def crud_ventas(metodo, identificador, cuerpo):
    if metodo == "GET":
        if identificador is None:
            return 200, ejecutar(LISTADO_VENTAS)["filas"]
        filas = ejecutar(
            "SELECT * FROM vw_ventas WHERE id_pedido = %s ORDER BY id_videojuego",
            (identificador,),
        )["filas"]
        if not filas:
            raise NoEncontrado("No existe la venta con id %s." % identificador)
        return 200, filas

    if metodo == "POST":
        if identificador is not None:
            raise NoEncontrado("Ruta no encontrada.")
        datos = validar_venta(cuerpo)
        try:
            resultado = ejecutar_procedimiento(
                "CALL sp_procesar_venta(%s, %s, %s)",
                (datos["id_cliente"], datos["id_videojuego"], datos["cantidad"]),
            )
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            return codigo, {"error": mensaje}
        filas = resultado["filas"]
        id_pedido = filas[0]["id_pedido"] if filas else None
        return 201, {
            "mensaje": "Venta registrada correctamente.",
            "id_pedido": id_pedido,
        }

    if metodo == "PUT":
        if identificador is None:
            raise DatosInvalidos("Falta el identificador de la venta a actualizar.")
        datos = validar_venta(cuerpo)
        try:
            existe = actualizar_venta(identificador, datos)
        except DatosInvalidos:
            raise
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            return codigo, {"error": mensaje}
        if not existe:
            raise NoEncontrado("No existe la venta con id %s." % identificador)
        return 200, ejecutar(
            "SELECT * FROM vw_ventas WHERE id_pedido = %s ORDER BY id_videojuego",
            (identificador,),
        )["filas"]

    if metodo == "DELETE":
        if identificador is None:
            raise DatosInvalidos("Falta el identificador de la venta a eliminar.")
        try:
            existe = eliminar_venta(identificador)
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            return codigo, {"error": mensaje}
        if not existe:
            raise NoEncontrado("No existe la venta con id %s." % identificador)
        return 200, {"mensaje": "Venta eliminada correctamente."}

    raise DatosInvalidos("Metodo %s no permitido sobre /api/ventas." % metodo)


# ----------------------------------------------------------------------------
# Enrutador
# ----------------------------------------------------------------------------

def despachar(metodo, ruta, cuerpo):
    partes = [parte for parte in urlparse(ruta).path.split("/") if parte]

    if not partes or partes[0] != "api":
        raise NoEncontrado("Ruta no encontrada.")

    if len(partes) == 1:
        return 200, {"mensaje": "API de GameStore", "recursos": RECURSOS}

    recurso = partes[1]
    identificador = None

    if len(partes) > 2:
        if len(partes) > 3 or not partes[2].isdigit():
            raise NoEncontrado("Ruta no encontrada.")
        identificador = int(partes[2])

    if recurso == "ventas":
        return crud_ventas(metodo, identificador, cuerpo)

    if recurso in CONFIG:
        return crud(recurso, metodo, identificador, cuerpo)

    raise NoEncontrado("El recurso '%s' no existe." % recurso)


# ----------------------------------------------------------------------------
# Servidor HTTP
# ----------------------------------------------------------------------------

class ManejadorHTTP(BaseHTTPRequestHandler):
    server_version = "GameStoreAPI/1.0"

    def do_GET(self):
        self.atender("GET")

    def do_POST(self):
        self.atender("POST")

    def do_PUT(self):
        self.atender("PUT")

    def do_DELETE(self):
        self.atender("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.enviar_cors()
        self.end_headers()

    def enviar_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def leer_cuerpo(self):
        longitud = int(self.headers.get("Content-Length") or 0)
        if longitud <= 0:
            return None
        bruto = self.rfile.read(longitud)
        try:
            return json.loads(bruto.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise DatosInvalidos("El cuerpo de la peticion no es JSON valido.")

    def responder(self, estado, datos):
        cuerpo = json.dumps(
            datos, ensure_ascii=False, default=_serializar
        ).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.enviar_cors()
        self.end_headers()
        self.wfile.write(cuerpo)

    def atender(self, metodo):
        try:
            cuerpo = self.leer_cuerpo() if metodo in ("POST", "PUT") else None
            estado, datos = despachar(metodo, self.path, cuerpo)
        except DatosInvalidos as error:
            estado, datos = 400, {"error": str(error)}
        except NoEncontrado as error:
            estado, datos = 404, {"error": str(error)}
        except MySQLError as error:
            codigo, mensaje = traducir_error(error)
            estado, datos = codigo, {"error": mensaje}
        except Exception as error:  # noqa: BLE001
            estado, datos = 500, {"error": "Error interno del servidor: %s" % error}
        self.responder(estado, datos)

    def log_message(self, formato, *argumentos):
        print("%s - %s" % (self.address_string(), formato % argumentos), flush=True)


def _serializar(valor):
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


def principal():
    print("Esperando a la base de datos...", flush=True)
    esperar_bd()
    servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), ManejadorHTTP)
    print("API de GameStore escuchando en el puerto %s" % PUERTO, flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    principal()
