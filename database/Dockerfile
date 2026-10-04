FROM mysql:8.0

# Fuerza UTF-8 en el cliente para que la carga inicial de datos no pierda acentos.
COPY utf8.cnf /etc/mysql/conf.d/utf8.cnf
COPY init.sql /docker-entrypoint-initdb.d/init.sql
