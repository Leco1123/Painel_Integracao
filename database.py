# database.py
import logging
import os
from pathlib import Path
from typing import Dict

from mysql.connector import Error, pooling

LOGGER = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Carrega um arquivo .env localizado ao lado do projeto, se existir."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _build_db_config() -> Dict[str, object]:
    _load_dotenv()

    defaults = {
        "DB_HOST": "localhost",
        "DB_USER": "root",
        "DB_PASS": "int123!",
        "DB_NAME": "sistema_login",
        "DB_PORT": "3306",
    }

    missing_values = [key for key in defaults if not os.getenv(key)]
    for key in missing_values:
        os.environ.setdefault(key, defaults[key])

    if missing_values:
        LOGGER.warning(
            "Variáveis de ambiente ausentes (%s); usando valores padrão.",
            ", ".join(sorted(missing_values)),
        )

    config: Dict[str, object] = {
        "host": os.environ["DB_HOST"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASS"],
        "database": os.environ["DB_NAME"],
        "port": int(os.environ.get("DB_PORT", defaults["DB_PORT"])),
    }
    return config


DB_CONFIG = _build_db_config()


# -----------------------------------------
# Pool
# -----------------------------------------
try:
    _POOL = pooling.MySQLConnectionPool(
        pool_name="painel_pool",
        pool_size=5,
        pool_reset_session=True,
        **DB_CONFIG,
    )
    LOGGER.info("Pool de conexões iniciado com sucesso.")
except Error as exc:
    LOGGER.exception("Falha ao criar pool de conexões.")
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
