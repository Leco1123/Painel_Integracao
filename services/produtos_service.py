"""Serviço de domínio responsável pela gestão dos produtos exibidos nos painéis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

from mysql.connector.cursor import MySQLCursor, MySQLCursorDict

from database import conectar

LOGGER = logging.getLogger(__name__)

_DEFAULT_PRODUCTS: Sequence[str] = (
    "Controle da Integração",
    "Macro da Regina",
    "Macro da Folha",
    "Macro do Fiscal",
    "Formatador de Balancete",
    "Manuais",
)

_STATUS_ORDER = "", "Em Desenvolvimento", "Atualizando", "Pronto"


@dataclass
class Produto:
    id: Optional[int]
    nome: str
    status: str
    ultimo_acesso: Optional[datetime]

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
                ultimo_acesso = None
        return cls(
            id=row.get("id"),
            nome=row.get("nome", ""),
            status=row.get("status") or "Desconhecido",
            ultimo_acesso=ultimo_acesso,
        )


class ProdutoService:
    """API de alto nível para operações relacionadas aos produtos."""

    def __init__(self):
        self._connection_factory = conectar

    # ---------------------------------------------------------------
    # Leitura
    # ---------------------------------------------------------------
    def listar_principais(self) -> List[Produto]:
        with self._connection_factory() as conn:
            cursor: MySQLCursorDict = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT id, nome, status, ultimo_acesso
                    FROM produtos
                    WHERE nome IN (%s, %s, %s, %s, %s, %s)
                    ORDER BY FIELD(
                        nome,
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                    tuple(_DEFAULT_PRODUCTS) * 2,
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

            produtos = [Produto.from_row(row) for row in rows]
            faltantes = [nome for nome in _DEFAULT_PRODUCTS if nome not in {p.nome for p in produtos}]
            if faltantes:
                LOGGER.info("Inserindo produtos padrão ausentes: %s", ", ".join(faltantes))
                self._criar_produtos(faltantes)
                return self.listar_principais()
            return produtos

    # ---------------------------------------------------------------
    # Escrita
    # ---------------------------------------------------------------
    def registrar_acesso(self, produto_id: int, usuario: str) -> None:
        if produto_id is None:
            raise ValueError("produto_id deve ser informado")

        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW() WHERE id = %s", (produto_id,))
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id) VALUES (%s, %s)",
                    (usuario, produto_id),
                )
                conn.commit()
            finally:
                cursor.close()

    def registrar_acesso_global(self, usuario: str) -> None:
        """Marca o último acesso para todos os produtos disponíveis."""

        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW()")
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id) SELECT %s, id FROM produtos",
                    (usuario,),
                )
                conn.commit()
            finally:
                cursor.close()

    def atualizar_status(self, produto_id: int, novo_status: str) -> None:
        if produto_id is None:
            raise ValueError("produto_id deve ser informado")

        status_normalizado = novo_status.strip()
        if status_normalizado not in _STATUS_ORDER:
            LOGGER.warning("Status inválido '%s' fornecido; aplicando valor literal.", novo_status)

        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE produtos SET status = %s WHERE id = %s",
                    (status_normalizado, produto_id),
                )
                conn.commit()
            finally:
                cursor.close()

    # ---------------------------------------------------------------
    # Internos
    # ---------------------------------------------------------------
    def _criar_produtos(self, nomes: Iterable[str]) -> None:
        valores = [(nome,) for nome in nomes]
        if not valores:
            return

        with self._connection_factory() as conn:
            cursor: MySQLCursor = conn.cursor()
            try:
                cursor.executemany(
                    "INSERT IGNORE INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NULL)",
                    valores,
                )
                conn.commit()
            finally:
                cursor.close()


__all__ = ["Produto", "ProdutoService", "_DEFAULT_PRODUCTS"]
