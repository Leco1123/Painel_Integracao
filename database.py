# database.py
import os
from mysql.connector import pooling, Error

# -----------------------------------------
# Config
# -----------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", "int123!"),
    "database": os.getenv("DB_NAME", "sistema_login"),
    "port": int(os.getenv("DB_PORT", 3306)),
}

# -----------------------------------------
# Pool
# -----------------------------------------
try:
    _POOL = pooling.MySQLConnectionPool(
        pool_name="painel_pool",
        pool_size=5,
        pool_reset_session=True,
        **DB_CONFIG
    )
    print("[DB] Pool de conexões iniciado.")
except Error as e:
    print(f"[ERRO BANCO] Falha ao criar pool: {e}")
    _POOL = None


# -----------------------------------------
# Proxy que funciona com e sem 'with'
# -----------------------------------------
class _ConnectionProxy:
    """
    - Suporta uso com 'with conectar() as conn'
    - Suporta uso direto: conn = conectar(); conn.cursor()
    - Encaminha atributos para a conexão real (lazy)
    """
    def __init__(self, pool):
        self._pool = pool
        self._conn = None

    def _ensure(self):
        if self._conn is None:
            if not self._pool:
                raise RuntimeError("Pool de conexões não inicializado.")
            self._conn = self._pool.get_connection()

    # Context manager
    def __enter__(self):
        self._ensure()
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._conn and self._conn.is_connected():
                self._conn.close()  # devolve ao pool
        finally:
            self._conn = None

    # Encaminha qualquer atributo/método para a conexão real
    def __getattr__(self, name):
        self._ensure()
        return getattr(self._conn, name)

    # Para casos como: if conn: ...
    def __bool__(self):
        self._ensure()
        return bool(self._conn)


# -----------------------------------------
# API pública
# -----------------------------------------
def conectar():
    """
    Retorna um proxy de conexão.
    Pode ser usado de duas formas:

        # 1) Context manager (recomendado)
        with conectar() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT 1")
            conn.commit()

        # 2) Direto (compatibilidade)
        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.commit()
        conn.close()
    """
    return _ConnectionProxy(_POOL)
