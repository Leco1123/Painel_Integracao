"""Serviços utilitários compartilhados por diferentes partes da aplicação."""

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

    @classmethod
    def from_row(cls, row: dict) -> "Usuario":
        return cls(
            id=row.get("id", 0),
            usuario=row.get("usuario", ""),
            nome=row.get("nome", ""),
            tipo=row.get("tipo", "usuario"),
            senha_hash=row.get("senha_hash", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario": self.usuario,
            "nome": self.nome,
            "tipo": self.tipo,
            "senha_hash": self.senha_hash,
        }


class UsuarioRepository:
    """Realiza operações de consulta relacionadas à tabela ``usuarios``."""

    def __init__(self, connection_factory=conectar):
        self._connection_factory = connection_factory

    def buscar_por_usuario(self, username: str) -> Optional[Usuario]:
        with self._connection_factory() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id, usuario, nome, tipo, senha_hash FROM usuarios WHERE usuario = %s",
                    (username,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()

        return Usuario.from_row(row) if row else None


class AuthService:
    """Responsável por autenticar usuários e registrar seus acessos."""

    def __init__(
        self,
        *,
        usuario_repository: Optional[UsuarioRepository] = None,
        produto_service: Optional[ProdutoService] = None,
    ) -> None:
        self._usuarios = usuario_repository or UsuarioRepository()
        self._produtos = produto_service or ProdutoService()

    def authenticate(self, username: str, password: str, *, registrar_acesso: bool = True) -> Optional[Usuario]:
        if not username or not password:
            raise ValueError("Usuário e senha devem ser preenchidos.")

        usuario = self._usuarios.buscar_por_usuario(username)
        if not usuario or not usuario.senha_hash:
            return None

        if not bcrypt.checkpw(password.encode("utf-8"), usuario.senha_hash.encode("utf-8")):
            return None

        if registrar_acesso:
            try:
                self._produtos.registrar_acesso_global(usuario.usuario)
            except Exception:
                LOGGER.exception(
                    "Falha ao registrar acesso global para o usuário '%s'", usuario.usuario
                )

        return usuario


def verificar_login(usuario: str, senha: str) -> Optional[dict]:
    autenticado = AuthService().authenticate(usuario, senha)
    return autenticado.to_dict() if autenticado else None


def registrar_acesso(usuario: str) -> None:
    ProdutoService().registrar_acesso_global(usuario)


__all__ = [
    "AuthService",
    "Usuario",
    "UsuarioRepository",
    "verificar_login",
    "registrar_acesso",
]
