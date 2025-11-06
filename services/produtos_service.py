"""Serviços e utilidades relacionados aos produtos exibidos nos painéis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple

from mysql.connector.cursor import MySQLCursor, MySQLCursorDict

from database import conectar

LOGGER = logging.getLogger(__name__)


class ProdutoStatus(str, Enum):
    """Enum auxiliar para manter consistência na escrita dos status."""

    EM_DESENVOLVIMENTO = "Em Desenvolvimento"
    ATUALIZANDO = "Atualizando"
    PRONTO = "Pronto"

    @classmethod
    def ordenados(cls) -> Tuple[str, ...]:
        return tuple(status.value for status in cls)


_DEFAULT_PRODUCTS: Sequence[str] = (
    "Controle da Integração",
    "Macro da Regina",
    "Macro da Folha",
    "Macro do Fiscal",
    "Formatador de Balancete",
    "Manuais",
)


@dataclass(frozen=True)
class Produto:
    id: Optional[int]
    nome: str
    status: str
    ultimo_acesso: Optional[datetime]

    def with_status(self, novo_status: str) -> "Produto":
        return replace(self, status=novo_status)

    @property
    def cache_key(self) -> str:
        return f"{self.id or 'virtual'}::{self.nome}"

    @classmethod
    def from_row(cls, row: dict) -> "Produto":
        ultimo_acesso = row.get("ultimo_acesso")
        if isinstance(ultimo_acesso, str) and ultimo_acesso:
            try:
                ultimo_acesso = datetime.fromisoformat(ultimo_acesso.replace("Z", ""))
            except ValueError:
                LOGGER.debug("Valor inválido para ultimo_acesso (%s)", ultimo_acesso)
                ultimo_acesso = None
        return cls(
            id=row.get("id"),
            nome=row.get("nome", ""),
            status=row.get("status") or "Desconhecido",
            ultimo_acesso=ultimo_acesso,
        )


class ProdutoRepository:
    """Camada de acesso direto ao banco para operações com ``produtos``."""

    def __init__(self, connection_factory=conectar):
        self._connection_factory = connection_factory

    # ---------------------------------------------------------------
    # Leituras
    # ---------------------------------------------------------------
    def buscar_por_nomes(self, nomes: Sequence[str]) -> List[Produto]:
        if not nomes:
            return []

        with self._connection_factory() as conn:
            cursor: MySQLCursorDict = conn.cursor(dictionary=True)
            try:
                marcadores = ", ".join(["%s"] * len(nomes))
                cursor.execute(
                    f"""
                    SELECT id, nome, status, ultimo_acesso
                      FROM produtos
                     WHERE nome IN ({marcadores})
                  ORDER BY FIELD(nome, {marcadores})
                    """,
                    tuple(nomes) * 2,
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

        return [Produto.from_row(row) for row in rows]

    def listar_todos(self) -> List[Produto]:
        with self._connection_factory() as conn:
            cursor: MySQLCursorDict = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, nome, status, ultimo_acesso
                      FROM produtos
                  ORDER BY nome
                    """
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [Produto.from_row(row) for row in rows]

    # ---------------------------------------------------------------
    # Escritas
    # ---------------------------------------------------------------
    def registrar_acesso(self, produto_id: int, usuario: str) -> None:
        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW() WHERE id = %s", (produto_id,))
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id, momento) VALUES (%s, %s, NOW())",
                    (usuario, produto_id),
                )
                conn.commit()
            finally:
                cursor.close()

    def registrar_acesso_global(self, usuario: str) -> None:
        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW()")
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id, momento) SELECT %s, id, NOW() FROM produtos",
                    (usuario,),
                )
                conn.commit()
            finally:
                cursor.close()

    def atualizar_status(self, produto_id: int, status: str) -> None:
        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE produtos SET status = %s WHERE id = %s",
                    (status, produto_id),
                )
                conn.commit()
            finally:
                cursor.close()

    def criar_produtos(self, nomes: Iterable[str]) -> None:
        valores = [(nome,) for nome in nomes]
        if not valores:
            return

        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.executemany(
                    """
                    INSERT INTO produtos (nome, status, ultimo_acesso)
                    VALUES (%s, %s, NULL)
                    ON DUPLICATE KEY UPDATE nome = VALUES(nome)
                    """,
                    [(nome, ProdutoStatus.PRONTO.value) for (nome,) in valores],
                )
                conn.commit()
            finally:
                cursor.close()


class ProdutoService:
    """Coordena leitura e escrita de produtos exibidos nos painéis."""

    def __init__(self, repository: Optional[ProdutoRepository] = None):
        self._repository = repository or ProdutoRepository()

    def garantir_produtos_padrao(self) -> None:
        existentes = {produto.nome for produto in self._repository.buscar_por_nomes(_DEFAULT_PRODUCTS)}
        faltantes = [nome for nome in _DEFAULT_PRODUCTS if nome not in existentes]
        if faltantes:
            LOGGER.info("Criando produtos padrão ausentes: %s", ", ".join(faltantes))
            self._repository.criar_produtos(faltantes)

    def listar_principais(self) -> List[Produto]:
        self.garantir_produtos_padrao()
        produtos = self._repository.buscar_por_nomes(_DEFAULT_PRODUCTS)
        if not produtos:
            # Em cenários com base vazia retornamos a lista após recriação
            produtos = self._repository.buscar_por_nomes(_DEFAULT_PRODUCTS)
        return produtos

    def registrar_acesso(self, produto_id: int, usuario: str) -> None:
        if produto_id is None:
            raise ValueError("produto_id deve ser informado")
        if not usuario:
            raise ValueError("usuario deve ser informado")
        self._repository.registrar_acesso(produto_id, usuario)

    def registrar_acesso_global(self, usuario: str) -> None:
        if not usuario:
            raise ValueError("usuario deve ser informado")
        self._repository.registrar_acesso_global(usuario)

    def atualizar_status(self, produto_id: int, novo_status: str) -> None:
        if produto_id is None:
            raise ValueError("produto_id deve ser informado")

        status_limpo = novo_status.strip() or ProdutoStatus.EM_DESENVOLVIMENTO.value
        if status_limpo not in ProdutoStatus.ordenados():
            LOGGER.warning("Status '%s' não é padrão; aplicando mesmo assim.", novo_status)
        self._repository.atualizar_status(produto_id, status_limpo)


__all__ = [
    "Produto",
    "ProdutoRepository",
    "ProdutoService",
    "ProdutoStatus",
    "_DEFAULT_PRODUCTS",
]
