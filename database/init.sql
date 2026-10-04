-- ============================================================================
-- GAMESTORE - Esquema de base de datos MySQL (diseño normalizado, 3FN)
-- Se ejecuta automaticamente la primera vez que el contenedor de MySQL arranca.
-- ============================================================================

-- Garantiza que los acentos y la ñ del archivo se interpreten como UTF-8.
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS gamestore
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE gamestore;

-- ----------------------------------------------------------------------------
-- TABLAS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS plataforma (
  id_plataforma INT NOT NULL AUTO_INCREMENT,
  nombre        VARCHAR(80) NOT NULL,
  fabricante    VARCHAR(80) NOT NULL,
  PRIMARY KEY (id_plataforma),
  UNIQUE KEY uq_plataforma_nombre (nombre)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS proveedor (
  id_proveedor   INT NOT NULL AUTO_INCREMENT,
  nombre_empresa VARCHAR(100) NOT NULL,
  contacto       VARCHAR(100) NOT NULL,
  telefono       VARCHAR(30) NOT NULL,
  PRIMARY KEY (id_proveedor),
  UNIQUE KEY uq_proveedor_empresa (nombre_empresa)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS videojuego (
  id_videojuego  INT NOT NULL AUTO_INCREMENT,
  titulo         VARCHAR(120) NOT NULL,
  id_plataforma  INT NOT NULL,
  id_proveedor   INT NOT NULL,
  precio         DECIMAL(10,2) NOT NULL,
  stock          INT NOT NULL DEFAULT 0,
  desarrollador  VARCHAR(100) NOT NULL,
  PRIMARY KEY (id_videojuego),
  UNIQUE KEY uq_videojuego_titulo_plataforma (titulo, id_plataforma),
  KEY idx_videojuego_plataforma (id_plataforma),
  KEY idx_videojuego_proveedor (id_proveedor),
  CONSTRAINT fk_videojuego_plataforma FOREIGN KEY (id_plataforma)
    REFERENCES plataforma (id_plataforma) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_videojuego_proveedor FOREIGN KEY (id_proveedor)
    REFERENCES proveedor (id_proveedor) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cliente (
  id_cliente INT NOT NULL AUTO_INCREMENT,
  nombre     VARCHAR(100) NOT NULL,
  email      VARCHAR(120) NOT NULL,
  direccion  VARCHAR(200) NOT NULL,
  PRIMARY KEY (id_cliente),
  UNIQUE KEY uq_cliente_email (email)
) ENGINE=InnoDB;

-- Una venta (pedido) puede tener uno o varios renglones: se separa en dos tablas
-- para no duplicar datos del cliente ni de la fecha en cada renglon (3FN).
CREATE TABLE IF NOT EXISTS pedido (
  id_pedido    INT NOT NULL AUTO_INCREMENT,
  id_cliente   INT NOT NULL,
  fecha_pedido DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_pedido),
  KEY idx_pedido_cliente (id_cliente),
  CONSTRAINT fk_pedido_cliente FOREIGN KEY (id_cliente)
    REFERENCES cliente (id_cliente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS detalle_pedido (
  id_pedido       INT NOT NULL,
  id_videojuego   INT NOT NULL,
  cantidad        INT NOT NULL,
  precio_unitario DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (id_pedido, id_videojuego),
  KEY idx_detalle_videojuego (id_videojuego),
  CONSTRAINT fk_detalle_pedido FOREIGN KEY (id_pedido)
    REFERENCES pedido (id_pedido) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_detalle_videojuego FOREIGN KEY (id_videojuego)
    REFERENCES videojuego (id_videojuego) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- VISTA: historial de ventas (une pedido + detalle + cliente + videojuego)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW vw_ventas AS
SELECT
  d.id_pedido,
  p.id_cliente,
  c.nombre    AS cliente,
  d.id_videojuego,
  v.titulo    AS videojuego,
  d.cantidad,
  (d.cantidad * d.precio_unitario) AS total,
  p.fecha_pedido
FROM detalle_pedido d
INNER JOIN pedido p      ON p.id_pedido   = d.id_pedido
INNER JOIN cliente c     ON c.id_cliente  = p.id_cliente
INNER JOIN videojuego v  ON v.id_videojuego = d.id_videojuego;

-- ----------------------------------------------------------------------------
-- STORED PROCEDURES
-- ----------------------------------------------------------------------------

DELIMITER $$

-- Alta de cliente (lo usa el formulario "Guardar Cliente (SP)")
CREATE PROCEDURE sp_registrar_cliente(
  IN p_nombre VARCHAR(100),
  IN p_email VARCHAR(120),
  IN p_direccion VARCHAR(200)
)
BEGIN
  INSERT INTO cliente (nombre, email, direccion)
  VALUES (p_nombre, p_email, p_direccion);

  SELECT LAST_INSERT_ID() AS id_cliente;
END$$

-- Procesamiento de una venta (lo usa el formulario "Procesar Venta").
-- Valida stock, crea el pedido, registra el detalle y descuenta inventario
-- dentro de una sola transaccion.
CREATE PROCEDURE sp_procesar_venta(
  IN p_id_cliente INT,
  IN p_id_videojuego INT,
  IN p_cantidad INT
)
BEGIN
  DECLARE v_stock INT;
  DECLARE v_precio DECIMAL(10,2);
  DECLARE v_clientes INT;
  DECLARE v_id_pedido INT;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;

  SELECT COUNT(*) INTO v_clientes
  FROM cliente
  WHERE id_cliente = p_id_cliente;

  IF v_clientes = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El cliente indicado no existe';
  END IF;

  IF p_cantidad < 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La cantidad debe ser mayor a cero';
  END IF;

  SELECT stock, precio INTO v_stock, v_precio
  FROM videojuego
  WHERE id_videojuego = p_id_videojuego
  FOR UPDATE;

  IF v_stock IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El videojuego indicado no existe';
  END IF;

  IF v_stock < p_cantidad THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Stock insuficiente para procesar la venta';
  END IF;

  INSERT INTO pedido (id_cliente) VALUES (p_id_cliente);
  SET v_id_pedido = LAST_INSERT_ID();

  INSERT INTO detalle_pedido (id_pedido, id_videojuego, cantidad, precio_unitario)
  VALUES (v_id_pedido, p_id_videojuego, p_cantidad, v_precio);

  UPDATE videojuego
  SET stock = stock - p_cantidad
  WHERE id_videojuego = p_id_videojuego;

  COMMIT;

  SELECT v_id_pedido AS id_pedido;
END$$

DELIMITER ;

-- ----------------------------------------------------------------------------
-- DATOS DE EJEMPLO (migrados desde los arreglos JSON del frontend original)
-- ----------------------------------------------------------------------------

INSERT INTO plataforma (id_plataforma, nombre, fabricante) VALUES
  (1, 'PlayStation 5', 'Sony'),
  (2, 'Xbox Series X', 'Microsoft'),
  (3, 'Nintendo Switch', 'Nintendo');

INSERT INTO proveedor (id_proveedor, nombre_empresa, contacto, telefono) VALUES
  (1, 'GameDistro S.A.', 'Carlos Pérez', '555-0192'),
  (2, 'Pixel Import', 'María López', '555-0183');

INSERT INTO videojuego (id_videojuego, titulo, id_plataforma, id_proveedor, precio, stock, desarrollador) VALUES
  (1, 'Elden Ring', 1, 1, 59.99, 12, 'FromSoftware'),
  (2, 'Halo Infinite', 2, 2, 49.99, 5, '343 Industries');

INSERT INTO cliente (id_cliente, nombre, email, direccion) VALUES
  (1, 'Juan Pérez', 'juan.perez@email.com', 'Av. Reforma 123, CDMX'),
  (2, 'Ana Gómez', 'ana.gomez@email.com', 'Calle Juárez 456, Guadalajara');

INSERT INTO pedido (id_pedido, id_cliente, fecha_pedido) VALUES
  (1, 1, NOW()),
  (2, 2, NOW());

INSERT INTO detalle_pedido (id_pedido, id_videojuego, cantidad, precio_unitario) VALUES
  (1, 1, 1, 59.99),
  (2, 2, 2, 49.99);
