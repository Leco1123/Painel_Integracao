"""Funções de acesso e manipulação dos produtos do painel."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from database import conectar

LOGGER = logging.getLogger(__name__)

_PRODUTOS_FIXOS = [
    "Controle da Integração",
    "Macro da Regina",
    "Macro da Folha",
    "Macro do Fiscal",
    "Formatador de Balancete",
    "Manuais",
]

_SQL_LISTAR = """
    SELECT id, nome, status, ultimo_acesso
    FROM produtos
    WHERE nome IN (
        'Controle da Integração',
        'Macro da Regina',
        'Macro da Folha',
        'Macro do Fiscal',
        'Formatador de Balancete',
        'Manuais'
    )
    ORDER BY FIELD(
        nome,
        'Controle da Integração',
        'Macro da Regina',
        'Macro da Folha',
        'Macro do Fiscal',
        'Formatador de Balancete',
        'Manuais'
    )
"""


def _buscar_produtos(conn) -> List[Dict]:
    cursor = conn.cursor(dictionary=True)
    cursor.execute(_SQL_LISTAR)
    produtos = cursor.fetchall()
    cursor.close()
    return produtos


def _inserir_produtos(conn, nomes: Iterable[str]) -> None:
    valores = [(nome,) for nome in nomes]
    if not valores:
        return

    cursor = conn.cursor()
    cursor.executemany(
        "INSERT IGNORE INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NULL)",
        valores,
    )
    conn.commit()
    cursor.close()


def obter_produtos_principais() -> List[Dict]:
    """Retorna a lista de produtos fixos, garantindo que existam no banco."""

    try:
        with conectar() as conn:
            produtos = _buscar_produtos(conn)
            nomes_banco = {produto["nome"] for produto in produtos}
            faltando = [nome for nome in _PRODUTOS_FIXOS if nome not in nomes_banco]
            if faltando:
                LOGGER.info("Inserindo produtos faltantes: %s", ", ".join(faltando))
                _inserir_produtos(conn, faltando)
                produtos = _buscar_produtos(conn)
            return produtos
    except Exception:
        LOGGER.exception("Falha ao obter produtos principais.")
        raise


def registrar_acesso_produto(produto_id: int, usuario: str) -> None:
    if produto_id is None:
        raise ValueError("produto_id não pode ser None")

    try:
        with conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE produtos SET ultimo_acesso = NOW() WHERE id = %s", (produto_id,))
            cursor.execute(
                "INSERT INTO acessos (usuario, produto_id) VALUES (%s, %s)",
                (usuario, produto_id),
            )
            conn.commit()
            cursor.close()
    except Exception:
        LOGGER.exception("Não foi possível registrar o acesso ao produto %s", produto_id)
        raise


def atualizar_status_produto(produto_id: int, novo_status: str) -> None:
    if produto_id is None:
        raise ValueError("produto_id não pode ser None")

    try:
        with conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE produtos SET status = %s WHERE id = %s",
                (novo_status, produto_id),
            )
            conn.commit()
            cursor.close()
    except Exception:
        LOGGER.exception(
            "Falha ao atualizar o status do produto %s para '%s'", produto_id, novo_status
        )
        raise


def produtos_fixos() -> List[str]:
    """Retorna a lista de nomes fixos usada nos painéis."""

    return list(_PRODUTOS_FIXOS)

