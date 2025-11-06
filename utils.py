"""Serviços de autenticação e utilidades auxiliares dos painéis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import bcrypt

from database import conectar
from services.produtos_service import ProdutoService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Usuario:
    id: int
    usuario: str
    nome: str
    tipo: str
    senha_hash: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario": self.usuario,
            "nome": self.nome,
            "tipo": self.tipo,
            "senha_hash": self.senha_hash,
        }


class AuthService:
    """Executa autenticação de usuários contra a base de dados."""

    def __init__(self, produtos_service: Optional[ProdutoService] = None):
        self._connection_factory = conectar
        self._produtos_service = produtos_service or ProdutoService()

    def authenticate(self, username: str, password: str, *, registrar_acesso: bool = True) -> Optional[Usuario]:
        if not username or not password:
            raise ValueError("Usuário e senha devem ser preenchidos.")

        with self._connection_factory() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (username,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if not row:
            return None

        senha_hash = row.get("senha_hash") or ""
        if not isinstance(senha_hash, str) or not senha_hash:
            LOGGER.warning("Usuário '%s' não possui hash de senha cadastrado.", username)
            return None

        if not bcrypt.checkpw(password.encode("utf-8"), senha_hash.encode("utf-8")):
            return None

        usuario = Usuario(
            id=row.get("id", 0),
            usuario=row.get("usuario", ""),
            nome=row.get("nome", ""),
            tipo=row.get("tipo", "usuario"),
            senha_hash=senha_hash,
        )

        if registrar_acesso:
            try:
                self._produtos_service.registrar_acesso_global(usuario.usuario)
            except Exception:
                LOGGER.exception(
                    "Falha ao registrar acesso global para o usuário '%s'", usuario.usuario
                )

        return usuario


def verificar_login(usuario: str, senha: str) -> Optional[dict]:
    """Mantido por compatibilidade com código legado."""

    service = AuthService()
    autenticado = service.authenticate(usuario, senha)
    return autenticado.to_dict() if autenticado else None


def registrar_acesso(usuario: str) -> None:
    ProdutoService().registrar_acesso_global(usuario)


__all__ = ["AuthService", "Usuario", "verificar_login", "registrar_acesso"]
