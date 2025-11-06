# Código para implementação (versão reescrita)

O documento abaixo reúne os principais módulos reescritos da aplicação. Cada seção contém o conteúdo completo do arquivo correspondente para facilitar a cópia manual, caso você queira aplicar as alterações em um ambiente fora do repositório.

## database.py

```python
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
    collation: str = "utf8mb4_unicode_ci"

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
            "collation": self.collation,
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

```

## services/produtos_service.py

```python
"""Serviços e utilidades relacionados aos produtos exibidos nos painéis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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

```

## painel_base.py

```python
"""Widgets base compartilhados pelos painéis da aplicação."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Dict, Iterable, Sequence

from PySide6 import QtCore, QtWidgets

from services.produtos_service import Produto, ProdutoStatus


STATUS_COLORS = {
    ProdutoStatus.EM_DESENVOLVIMENTO.value: "#f87171",
    ProdutoStatus.ATUALIZANDO.value: "#fbbf24",
    ProdutoStatus.PRONTO.value: "#4ade80",
}


class ProductCard(QtWidgets.QFrame):
    """Cartão visual que representa um único produto."""

    activated = QtCore.Signal(Produto)

    def __init__(self, produto: Produto, *, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._produto = produto
        self._build()
        self.update_from_produto(produto)

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self.lbl_nome = QtWidgets.QLabel()
        self.lbl_nome.setObjectName("CardTitle")
        layout.addWidget(self.lbl_nome)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("CardStatus")
        layout.addWidget(self.lbl_status)

        self.lbl_ultimo_acesso = QtWidgets.QLabel()
        layout.addWidget(self.lbl_ultimo_acesso)

        layout.addStretch(1)

        self.btn_abrir = QtWidgets.QPushButton("Abrir módulo")
        self.btn_abrir.clicked.connect(self._emit_activated)
        layout.addWidget(self.btn_abrir)

    def mouseDoubleClickEvent(self, event):  # noqa: D401 - API Qt
        self._emit_activated()
        return super().mouseDoubleClickEvent(event)

    def _emit_activated(self) -> None:
        if self.btn_abrir.isEnabled():
            self.activated.emit(self._produto)

    def update_from_produto(self, produto: Produto) -> None:
        self._produto = produto
        self.lbl_nome.setText(produto.nome)

        status = (produto.status or "Desconhecido").strip()
        cor = STATUS_COLORS.get(status, "#94a3b8")
        self.lbl_status.setText(f"Status: {status}")
        self.lbl_status.setStyleSheet(f"color: {cor}; font-weight: bold;")

        ultimo_acesso = BasePainelWindow.formatar_data(produto.ultimo_acesso)
        self.lbl_ultimo_acesso.setText(f"Último acesso: {ultimo_acesso}")

        habilitado = status.lower() == ProdutoStatus.PRONTO.value.lower()
        self.btn_abrir.setEnabled(habilitado)
        if habilitado:
            self.btn_abrir.setStyleSheet(
                f"background-color: {cor}; color: black; font-weight: bold; border-radius: 6px; padding: 8px;"
            )
        else:
            self.btn_abrir.setStyleSheet(
                "background-color: #ef4444; color: white; font-weight: bold; border-radius: 6px; padding: 8px;"
            )

    @property
    def produto(self) -> Produto:
        return self._produto


class ProductGrid(QtWidgets.QWidget):
    """Grade responsiva responsável por organizar os cartões."""

    def __init__(self, *, columns: int = 3, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._layout = QtWidgets.QGridLayout(self)
        self._layout.setSpacing(16)
        self._cards: Dict[str, ProductCard] = {}

    def set_products(self, produtos: Sequence[Produto], *, factory) -> None:
        self.clear()
        for index, produto in enumerate(produtos):
            card = factory(produto)
            self._cards[produto.cache_key] = card
            row, column = divmod(index, self._columns)
            self._layout.addWidget(card, row, column)

    def update_product(self, produto: Produto) -> None:
        card = self._cards.get(produto.cache_key)
        if card:
            card.update_from_produto(produto)

    def clear(self) -> None:
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        while self._layout.count():
            self._layout.takeAt(0)

    def cards(self) -> Iterable[ProductCard]:
        return self._cards.values()


class BasePainelWindow(QtWidgets.QMainWindow):
    """Janela base compartilhada entre os painéis do sistema."""

    GRID_COLUMNS = 3
    STYLE = """
        QWidget { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI'; }
        QLabel#TituloPainel { font-size: 24px; font-weight: bold; color: #38bdf8; }
        QLabel#RodapeStatus { font-size: 12px; color: #94a3b8; }
        QFrame#Card {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
        }
        QLabel#CardTitle { font-size: 16px; font-weight: 600; color: #e2e8f0; }
        QLabel#CardStatus { font-size: 13px; }
    """

    def __init__(self, usuario: dict, titulo: str):
        super().__init__()
        self.usuario = usuario
        self.logger = logging.getLogger(self.__class__.__name__)
        self._grid = ProductGrid(columns=self.GRID_COLUMNS)

        self.setWindowTitle(titulo)
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(self.STYLE)
        self._build_layout()

    def _build_layout(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        titulo = QtWidgets.QLabel(f"Olá, {self.usuario.get('nome', 'usuário')}!")
        titulo.setObjectName("TituloPainel")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.addWidget(self._grid)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        self._rodape = QtWidgets.QLabel("🔌 Aguardando conexão...")
        self._rodape.setObjectName("RodapeStatus")
        self._rodape.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        layout.addWidget(self._rodape)

        self.setCentralWidget(container)

    # ------------------------------------------------------------------
    # API de atualização
    # ------------------------------------------------------------------
    def renderizar_produtos(self, produtos: Sequence[Produto]) -> None:
        self._grid.set_products(produtos, factory=self.criar_card)

    def criar_card(self, produto: Produto) -> ProductCard:
        return ProductCard(produto)

    def atualizar_card(self, produto: Produto) -> None:
        self._grid.update_product(produto)

    def atualizar_rodape(self, mensagem: str) -> None:
        self._rodape.setText(mensagem)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def formatar_data(valor) -> str:
        if not valor:
            return "-"
        try:
            if isinstance(valor, datetime):
                return valor.strftime("%d/%m/%Y %H:%M")
            return datetime.fromisoformat(str(valor).split(".")[0]).strftime("%d/%m/%Y %H:%M")
        except Exception:  # pragma: no cover - melhor esforço
            return str(valor)


__all__ = ["BasePainelWindow", "ProductCard", "ProductGrid", "STATUS_COLORS"]

```

## painel_admin.py

```python
"""Painel administrativo responsável por orquestrar os módulos internos."""

from __future__ import annotations

import logging
from typing import Callable, List

from PySide6 import QtCore, QtGui, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from painel_base import BasePainelWindow, ProductCard
from services.produtos_service import Produto, ProdutoService, ProdutoStatus

LOGGER = logging.getLogger(__name__)


class _WorkerSignals(QtCore.QObject):
    succeeded = QtCore.Signal(list)
    failed = QtCore.Signal(object)


class _Worker(QtCore.QRunnable):
    def __init__(self, task: Callable[[], List[Produto]]):
        super().__init__()
        self._task = task
        self.signals = _WorkerSignals()

    def run(self) -> None:  # pragma: no cover - executado fora da thread principal
        try:
            resultado = list(self._task())
        except Exception as exc:  # pragma: no cover - repassado ao Qt
            LOGGER.exception("Worker de produtos falhou")
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(resultado)


class PainelAdmin(BasePainelWindow):
    REFRESH_INTERVAL_MS = 3500

    def __init__(self, usuario: dict):
        super().__init__(usuario, "Painel do Administrador")
        self._service = ProdutoService()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._schedule_refresh)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self._schedule_refresh)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel administrativo inicializado para %s", self.usuario.get("usuario"))
        self._janela_admin = None
        self._janela_integracao = None

        self._schedule_refresh()
        self._timer.start()

    # ------------------------------------------------------------------
    # Atualização dos produtos
    # ------------------------------------------------------------------
    def _schedule_refresh(self) -> None:
        worker = _Worker(self._service.listar_principais)
        worker.signals.succeeded.connect(self._on_refresh_success)
        worker.signals.failed.connect(self._on_refresh_error)
        self.atualizar_rodape("🔄 Atualizando lista de produtos...")
        self._thread_pool.start(worker)

    @QtCore.Slot(list)
    def _on_refresh_success(self, produtos: List[Produto]) -> None:
        lista = list(produtos)
        if not any(prod.nome == "Painel de Administração" for prod in lista):
            lista.append(Produto(id=None, nome="Painel de Administração", status=ProdutoStatus.PRONTO.value, ultimo_acesso=None))
        self.renderizar_produtos(lista)
        self.atualizar_rodape("🟢 Conectado ao banco de dados")

    @QtCore.Slot(object)
    def _on_refresh_error(self, erro: Exception) -> None:
        self.logger.exception("Erro ao atualizar produtos", exc_info=erro)
        self.atualizar_rodape("🔴 Falha ao consultar produtos")
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{erro}",
        )

    # ------------------------------------------------------------------
    # Personalização dos cards
    # ------------------------------------------------------------------
    def criar_card(self, produto: Produto) -> ProductCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        card.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, c=card: self._mostrar_menu_status(c, pos))
        if produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color: #38bdf8; color: black; font-weight: bold; border-radius: 6px; padding: 8px;")
        return card

    # ------------------------------------------------------------------
    # Manipulação de status
    # ------------------------------------------------------------------
    def _mostrar_menu_status(self, card: ProductCard, pos: QtCore.QPoint) -> None:
        produto = card.produto
        if produto.id is None:
            return

        menu = QtWidgets.QMenu(card)
        for status in ProdutoStatus.ordenados():
            action = menu.addAction(status)
            action.triggered.connect(lambda _checked=False, s=status, p=produto: self._alterar_status(p, s))
        menu.exec(card.mapToGlobal(pos))

    def _alterar_status(self, produto: Produto, novo_status: str) -> None:
        try:
            self._service.atualizar_status(produto.id, novo_status)  # type: ignore[arg-type]
        except Exception as exc:
            self.logger.exception("Falha ao alterar status do produto %s", produto.id)
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao atualizar status",
                f"Não foi possível atualizar o status:\n{exc}",
            )
        else:
            self._schedule_refresh()

    # ------------------------------------------------------------------
    # Navegação entre módulos
    # ------------------------------------------------------------------
    def _registrar_acesso(self, produto: Produto) -> None:
        if produto.id is None:
            return
        try:
            self._service.registrar_acesso(produto.id, self.usuario.get("usuario", ""))
        except Exception:
            self.logger.exception("Não foi possível registrar acesso ao produto %s", produto.id)

    def _abrir_modulo(self, produto: Produto) -> None:
        self.logger.info("Abrindo módulo %s", produto.nome)
        self._registrar_acesso(produto)

        if produto.nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif produto.nome == "Painel de Administração":
            self._abrir_painel_administracao()
        elif produto.nome == "Controle da Integração":
            self._abrir_controle_integracao()
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{produto.nome}' ainda não foi conectado.",
            )

    def _abrir_painel_administracao(self) -> None:
        janela = PainelAdministracao()
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_admin = janela

    def _abrir_controle_integracao(self) -> None:
        janela = ControleIntegracao(self.usuario)
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_integracao = janela

    # ------------------------------------------------------------------
    # Ciclo de vida da janela
    # ------------------------------------------------------------------
    def event(self, event):  # noqa: D401 - assinatura Qt
        if event.type() == QtCore.QEvent.WindowActivate and not self._timer.isActive():
            self._timer.start(self.REFRESH_INTERVAL_MS)
        elif event.type() == QtCore.QEvent.WindowDeactivate and self._timer.isActive():
            self._timer.stop()
        return super().event(event)


__all__ = ["PainelAdmin"]

```

## painel_user.py

```python
"""Painel destinado aos usuários finais do sistema."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_base import BasePainelWindow, ProductCard
from services.produtos_service import Produto, ProdutoService


class PainelUser(BasePainelWindow):
    REFRESH_INTERVAL_MS = 4000

    def __init__(self, usuario: dict):
        super().__init__(usuario, "Painel do Usuário")
        self._service = ProdutoService()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._atualizar_produtos)

        self.logger.info("Painel do usuário inicializado para %s", self.usuario.get("usuario"))
        self._janela_integracao = None
        self._atualizar_produtos()
        self._timer.start()

    def criar_card(self, produto: Produto) -> ProductCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        return card

    def _atualizar_produtos(self) -> None:
        try:
            produtos = self._service.listar_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            self.atualizar_rodape("🔴 Falha ao buscar produtos")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            return

        self.renderizar_produtos(produtos)
        self.atualizar_rodape("🟢 Conectado ao banco de dados")

    def _registrar_acesso(self, produto: Produto) -> None:
        if produto.id is None:
            return
        try:
            self._service.registrar_acesso(produto.id, self.usuario.get("usuario", ""))
        except Exception:
            self.logger.exception(
                "Falha ao registrar acesso do usuário %s ao produto %s",
                self.usuario.get("usuario"),
                produto.id,
            )

    def _abrir_modulo(self, produto: Produto) -> None:
        self.logger.info("Usuário acionou módulo %s", produto.nome)
        self._registrar_acesso(produto)

        if produto.nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif produto.nome == "Controle da Integração":
            janela = ControleIntegracao(self.usuario)
            janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            janela.show()
            self._janela_integracao = janela
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{produto.nome}' ainda não foi conectado.",
            )


__all__ = ["PainelUser"]

```

## utils.py

```python
"""Serviços de autenticação e utilidades auxiliares dos painéis."""

from __future__ import annotations

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

```

## main.py

```python
"""Ponto de entrada principal da aplicação PySide6."""

from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from painel_admin import PainelAdmin
from painel_user import PainelUser
from utils import AuthService, Usuario

os.environ.setdefault("QT_OPENGL", "software")


class LoginWindow(QtWidgets.QMainWindow):
    """Tela inicial responsável pelo fluxo de autenticação."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service or AuthService()
        self._painel_aberto: Optional[QtWidgets.QWidget] = None

        self.setWindowTitle("Painel de Integração - Login")
        self.setFixedSize(460, 340)
        self.setWindowIcon(QtGui.QIcon())
        self._configurar_estilos()
        self._montar_interface()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 24px; font-weight: bold; color: #38bdf8; }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px;
                color: #e2e8f0;
            }
            QPushButton {
                background-color: #38bdf8;
                color: #020617;
                font-weight: 600;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover { background-color: #0ea5e9; }
            QLabel#StatusMensagem { color: #f87171; font-size: 12px; }
            QToolButton { border: none; background: transparent; }
            """
        )

    def _montar_interface(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(14)

        titulo = QtWidgets.QLabel("Acesse o sistema")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

        self.input_usuario = QtWidgets.QLineEdit()
        self.input_usuario.setPlaceholderText("Usuário")
        layout.addWidget(self.input_usuario)

        senha_layout = QtWidgets.QHBoxLayout()
        self.input_senha = QtWidgets.QLineEdit()
        self.input_senha.setPlaceholderText("Senha")
        self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)
        senha_layout.addWidget(self.input_senha)

        self.btn_toggle_senha = QtWidgets.QToolButton()
        self.btn_toggle_senha.setIcon(self._icone_senha())
        self.btn_toggle_senha.setCheckable(True)
        self.btn_toggle_senha.setToolTip("Mostrar/ocultar senha")
        self.btn_toggle_senha.clicked.connect(self._alternar_senha)
        senha_layout.addWidget(self.btn_toggle_senha)
        layout.addLayout(senha_layout)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("StatusMensagem")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.btn_login = QtWidgets.QPushButton("Entrar")
        self.btn_login.clicked.connect(self._tentar_login)
        layout.addWidget(self.btn_login)

        layout.addStretch(1)
        self.setCentralWidget(container)

        self.input_usuario.returnPressed.connect(self._tentar_login)
        self.input_senha.returnPressed.connect(self._tentar_login)
        self.input_usuario.setFocus()

    # ------------------------------------------------------------------
    # Eventos e interações
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: D401 - assinatura Qt
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._tentar_login()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._painel_aberto is not None:
            self._painel_aberto.close()
        event.accept()

    def _alternar_senha(self) -> None:
        modo = self.input_senha.echoMode()
        self.input_senha.setEchoMode(
            QtWidgets.QLineEdit.Normal if modo == QtWidgets.QLineEdit.Password else QtWidgets.QLineEdit.Password
        )

    def _icone_senha(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(18, 18)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#38bdf8"), 2))
        painter.drawEllipse(2, 5, 14, 8)
        painter.end()
        return QtGui.QIcon(pixmap)

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------
    def _tentar_login(self) -> None:
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            self._exibir_status("Informe usuário e senha.", erro=True)
            return

        self.btn_login.setEnabled(False)
        self._exibir_status("Validando credenciais...", erro=False)

        try:
            autenticado = self._auth.authenticate(usuario, senha)
        except ValueError as exc:
            self._exibir_status(str(exc), erro=True)
            self.btn_login.setEnabled(True)
            return
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Falha ao autenticar:\n{exc}")
            self._exibir_status("Não foi possível concluir o login.", erro=True)
            self.btn_login.setEnabled(True)
            return

        if not autenticado:
            self._exibir_status("Usuário ou senha inválidos.", erro=True)
            self.btn_login.setEnabled(True)
            return

        self._abrir_painel(autenticado)
        self.btn_login.setEnabled(True)

    def _exibir_status(self, mensagem: str, *, erro: bool) -> None:
        self.lbl_status.setText(mensagem)
        cor = "#f87171" if erro else "#38bdf8"
        self.lbl_status.setStyleSheet(f"color: {cor};")

    def _abrir_painel(self, usuario: Usuario) -> None:
        if self._painel_aberto is not None:
            self._painel_aberto.close()

        painel: QtWidgets.QWidget
        destino = usuario.tipo.lower()
        if destino == "admin":
            painel = PainelAdmin(usuario.to_dict())
        else:
            painel = PainelUser(usuario.to_dict())

        painel.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        painel.show()
        painel.closeEvent = self._retornar_para_login  # type: ignore[assignment]

        self._painel_aberto = painel
        self.hide()
        QtWidgets.QMessageBox.information(self, "Login realizado", f"Bem-vindo, {usuario.nome}!")

    def _retornar_para_login(self, event: QtGui.QCloseEvent) -> None:
        self._painel_aberto = None
        self.show()
        self._exibir_status("Sessão encerrada. Faça login novamente.", erro=False)
        event.accept()


def run() -> None:
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon())
    janela = LoginWindow()
    janela.show()
    app.exec()


if __name__ == "__main__":
    run()

```

## login.py

```python
"""Ponto de acesso alternativo para iniciar a aplicação de login."""

from __future__ import annotations

from main import run


if __name__ == "__main__":
    run()

```
