"""Camada centralizada de acesso ao banco de dados MySQL da aplicação."""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional

from mysql.connector import Error, pooling

LOGGER = logging.getLogger(__name__)

_DEFAULT_ENV: Mapping[str, str] = {
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_USER": "root",
    "DB_PASS": "int123!",
    "DB_NAME": "sistema_login",
    "DB_POOL_SIZE": "8",
}

_ENV_FILE_CANDIDATES: Iterable[Path] = (
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
)


def _load_env_from_files(paths: Iterable[Path]) -> Dict[str, str]:
    """Carrega pares ``chave=valor`` de possíveis arquivos ``.env``."""

    env: Dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip())
        except OSError as exc:  # pragma: no cover - ambiente externo
            LOGGER.debug("Não foi possível ler %s: %s", path, exc)
    return env


@dataclass(frozen=True)
class DatabaseSettings:
    """Agrupa as configurações necessárias para montar o pool de conexões."""

    host: str
    user: str
    password: str
    database: str
    port: int = 3306
    pool_size: int = 8
    pool_name: str = "painel_pool"
    charset: str = "utf8mb4"

    @classmethod
    def load(
        cls,
        *,
        env: MutableMapping[str, str] | None = None,
        search_paths: Iterable[Path] | None = None,
    ) -> "DatabaseSettings":
        """Constrói a configuração final combinando defaults, ``.env`` e ambiente."""

        if env is None:
            env = os.environ

        search_paths = tuple(search_paths or _ENV_FILE_CANDIDATES)
        for key, value in _load_env_from_files(search_paths).items():
            env.setdefault(key, value)

        data: Dict[str, str] = {key: env.get(key, default) for key, default in _DEFAULT_ENV.items()}

        missing = [key for key in ("DB_HOST", "DB_USER", "DB_PASS", "DB_NAME") if not data.get(key)]
        if missing:
            LOGGER.warning(
                "Variáveis de ambiente ausentes: %s. Usando valores padrão.",
                ", ".join(missing),
            )

        port = _safe_int(data.get("DB_PORT"), fallback=3306, name="DB_PORT")
        pool_size = max(1, _safe_int(data.get("DB_POOL_SIZE"), fallback=8, name="DB_POOL_SIZE"))

        return cls(
            host=data.get("DB_HOST", "localhost"),
            user=data.get("DB_USER", "root"),
            password=data.get("DB_PASS", ""),
            database=data.get("DB_NAME", "sistema_login"),
            port=port,
            pool_size=pool_size,
        )

    @property
    def masked_dsn(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database}"

    def as_mysql_kwargs(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
            "charset": self.charset,
        }


def _safe_int(value: Optional[str], *, fallback: int, name: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):  # pragma: no cover - validado dinamicamente
        LOGGER.warning("Valor inválido para %s (%s); usando %s.", name, value, fallback)
        return fallback


class ConnectionHandle(contextlib.AbstractContextManager):
    """Wrapper que garante fechamento adequado das conexões do pool."""

    def __init__(self, pool: Optional[pooling.MySQLConnectionPool]):
        self._pool = pool
        self._conn = None

    def __enter__(self):
        if self._conn is None:
            if self._pool is None:
                raise RuntimeError("Pool de conexões não inicializado.")
            self._conn = self._pool.get_connection()
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        if self._conn is not None:
            try:
                if self._conn.is_connected():  # type: ignore[attr-defined]
                    self._conn.close()
            finally:
                self._conn = None
        return False


@dataclass
class Database:
    """Gerencia o pool de conexões reutilizado pela aplicação."""

    settings: DatabaseSettings
    _pool: Optional[pooling.MySQLConnectionPool] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._initialise_pool()

    def _initialise_pool(self) -> None:
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name=self.settings.pool_name,
                pool_size=self.settings.pool_size,
                pool_reset_session=True,
                **self.settings.as_mysql_kwargs(),
            )
        except Error:
            LOGGER.exception("Falha ao inicializar o pool de conexões para %s", self.settings.masked_dsn)
            self._pool = None
        else:
            LOGGER.info(
                "Pool de conexões inicializado (%s conexões) para %s",
                self.settings.pool_size,
                self.settings.masked_dsn,
            )

    def connection(self) -> ConnectionHandle:
        return ConnectionHandle(self._pool)

    def ping(self) -> bool:
        try:
            with self.connection() as conn:
                conn.ping(reconnect=True, attempts=1, delay=0)  # type: ignore[attr-defined]
            return True
        except Exception:  # pragma: no cover - depende do servidor MySQL
            LOGGER.exception("Não foi possível efetuar ping no banco de dados.")
            return False


SETTINGS = DatabaseSettings.load()
DATABASE = Database(SETTINGS)


def conectar() -> ConnectionHandle:
    """Retorna um ``context manager`` para uso em ``with conectar() as conn``."""

    return DATABASE.connection()


__all__ = ["SETTINGS", "DATABASE", "Database", "DatabaseSettings", "conectar"]
