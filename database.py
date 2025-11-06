"""Infraestrutura de acesso ao banco de dados MySQL utilizada pelos painéis."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from mysql.connector import Error, pooling

LOGGER = logging.getLogger(__name__)

_ENV_FILE_CANDIDATES: Iterable[Path] = (
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
)


@dataclass(frozen=True)
class DatabaseSettings:
    """Representa a configuração necessária para montar o pool de conexões."""

    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = "int123!"
    database: str = "sistema_login"

    @classmethod
    def load(cls) -> "DatabaseSettings":
        """Carrega as configurações a partir do ambiente e de arquivos ``.env``."""

        env_file_values = _load_env_files()
        for key, value in env_file_values.items():
            os.environ.setdefault(key, value)

        merged: Dict[str, Optional[str]] = {
            "DB_HOST": cls.host,
            "DB_USER": cls.user,
            "DB_PASS": cls.password,
            "DB_NAME": cls.database,
            "DB_PORT": str(cls.port),
        }
        for key in merged.keys():
            value = os.environ.get(key)
            if value:
                merged[key] = value

        missing = [key for key in ("DB_HOST", "DB_USER", "DB_PASS", "DB_NAME") if not merged.get(key)]
        if missing:
            LOGGER.warning(
                "Variáveis de ambiente não fornecidas: %s. Utilizando valores padrão.",
                ", ".join(missing),
            )

        try:
            port = int(merged["DB_PORT"])
        except (TypeError, ValueError):
            LOGGER.warning(
                "Valor inválido para DB_PORT (%s); utilizando %s.",
                merged.get("DB_PORT"),
                cls.port,
            )
            port = cls.port

        return cls(
            host=str(merged["DB_HOST"]),
            user=str(merged["DB_USER"]),
            password=str(merged["DB_PASS"]),
            database=str(merged["DB_NAME"]),
            port=port,
        )

    def to_mysql_kwargs(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
        }


def _load_env_files() -> Dict[str, str]:
    """Retorna um dicionário com valores extraídos de eventuais arquivos ``.env``."""

    data: Dict[str, str] = {}
    for path in _ENV_FILE_CANDIDATES:
        if not path or not path.exists():
            continue
        try:
            for raw_line in path.read_text().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                data.setdefault(key.strip(), value.strip())
        except OSError as exc:
            LOGGER.debug("Não foi possível ler %s: %s", path, exc)
    return data


class _ConnectionHandle:
    """Proxy amigável que funciona tanto com ``with`` quanto em uso direto."""

    def __init__(self, pool: Optional[pooling.MySQLConnectionPool]):
        self._pool = pool
        self._conn = None

    def _ensure_connection(self):
        if self._conn is None:
            if not self._pool:
                raise RuntimeError("Pool de conexões não inicializado.")
            self._conn = self._pool.get_connection()
        return self._conn

    # API compatível com ``with conectar() as conn``
    def __enter__(self):
        return self._ensure_connection()

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # Encaminhamento para o objeto real
    def __getattr__(self, item):
        connection = self._ensure_connection()
        return getattr(connection, item)

    def __bool__(self):
        return self._conn is not None

    def close(self):
        if self._conn is not None:
            try:
                if self._conn.is_connected():
                    self._conn.close()
            finally:
                self._conn = None


SETTINGS = DatabaseSettings.load()

try:
    _POOL: Optional[pooling.MySQLConnectionPool] = pooling.MySQLConnectionPool(
        pool_name="painel_pool",
        pool_reset_session=True,
        pool_size=5,
        **SETTINGS.to_mysql_kwargs(),
    )
    LOGGER.info(
        "Pool de conexões criado: %s@%s:%s/%s",
        SETTINGS.user,
        SETTINGS.host,
        SETTINGS.port,
        SETTINGS.database,
    )
except Error:
    LOGGER.exception("Falha ao inicializar o pool de conexões com o MySQL.")
    _POOL = None


def conectar() -> _ConnectionHandle:
    """Retorna um proxy de conexão reutilizável."""

    return _ConnectionHandle(_POOL)


__all__ = ["SETTINGS", "conectar", "DatabaseSettings"]
