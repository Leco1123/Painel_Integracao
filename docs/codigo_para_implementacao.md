# Código para implementação (versão reescrita)

Este documento reúne os principais módulos reescritos da aplicação para facilitar a cópia e a verificação manual das alterações.

## database.py

```python
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

```

## services/produtos_service.py

```python
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

```

## utils.py

```python
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

```

## painel_base.py

```python
"""Componentes base compartilhados entre os painéis de usuário e administrador."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Dict, Sequence

from PySide6 import QtCore, QtWidgets

from services.produtos_service import Produto


_STATUS_COLORS = {
    "Em Desenvolvimento": "#ff5555",
    "Atualizando": "#ffaa00",
    "Pronto": "#4ecca3",
}


class PainelCard(QtWidgets.QFrame):
    """Widget visual responsável por exibir um único produto."""

    activated = QtCore.Signal(Produto)

    def __init__(self, produto: Produto, *, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._produto = produto
        self._build_ui()
        self.update_from_produto(produto)

    # ------------------------------------------------------------------
    # Construção visual
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        self.lbl_nome = QtWidgets.QLabel()
        self.lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self.lbl_nome)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("StatusLabel")
        layout.addWidget(self.lbl_status)

        self.lbl_acesso = QtWidgets.QLabel()
        layout.addWidget(self.lbl_acesso)

        self.btn_abrir = QtWidgets.QPushButton("Abrir")
        self.btn_abrir.clicked.connect(self._emit_activated)
        layout.addWidget(self.btn_abrir)

    # ------------------------------------------------------------------
    # Atualizações
    # ------------------------------------------------------------------
    def update_from_produto(self, produto: Produto) -> None:
        self._produto = produto
        self.lbl_nome.setText(produto.nome)
        status = (produto.status or "Desconhecido").strip()
        cor = _STATUS_COLORS.get(status, "#888888")
        self.lbl_status.setText(f"Status: {status}")
        self.lbl_status.setStyleSheet(f"color: {cor}; font-weight:bold;")

        acesso = BasePainelWindow.formatar_data(produto.ultimo_acesso)
        self.lbl_acesso.setText(f"Último acesso: {acesso}")

        habilitado = status.lower() == "pronto"
        self.btn_abrir.setEnabled(habilitado)
        if habilitado:
            self.btn_abrir.setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")
        else:
            self.btn_abrir.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _emit_activated(self) -> None:
        if self.btn_abrir.isEnabled():
            self.activated.emit(self._produto)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt API)
        self._emit_activated()
        return super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @property
    def produto(self) -> Produto:
        return self._produto


class BasePainelWindow(QtWidgets.QMainWindow):
    """Janela base que encapsula layout, estilo e utilitários comuns."""

    GRID_COLUMNS = 3
    STYLE = """
        QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
        QLabel#Saudacao {
            font-size: 22px;
            font-weight: bold;
            color: #4ecca3;
            margin: 15px;
        }
        QFrame#Card {
            background-color: #1b1e2b;
            border-radius: 10px;
            border: 1px solid #2a2a4a;
            padding: 16px;
            margin: 8px;
        }
        QLabel { font-size: 13px; color: #ffffff; }
        QLabel.StatusLabel { font-size: 13px; font-weight: bold; }
        QPushButton {
            font-weight: bold;
            border-radius: 6px;
            padding: 6px;
        }
        QLabel#RodapeStatus {
            font-size: 12px;
            color: #ffffff;
        }
    """

    def __init__(self, user: dict, title: str):
        super().__init__()
        self.user = user
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cards: Dict[str, PainelCard] = {}

        self.setWindowTitle(title)
        self.setGeometry(400, 150, 1100, 650)
        self.setStyleSheet(self.STYLE)
        self._build_base_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_base_layout(self) -> None:
        container = QtWidgets.QWidget()
        layout_root = QtWidgets.QVBoxLayout(container)

        saudacao = QtWidgets.QLabel(f"Olá, {self.user.get('nome', 'usuário')}!")
        saudacao.setObjectName("Saudacao")
        saudacao.setAlignment(QtCore.Qt.AlignCenter)
        layout_root.addWidget(saudacao)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(20)
        layout_root.addLayout(self.grid)

        rodape = QtWidgets.QLabel("🟢 Conectado ao sistema_login (MariaDB)")
        rodape.setObjectName("RodapeStatus")
        rodape.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        layout_root.addWidget(rodape)

        self.setCentralWidget(container)

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------
    def renderizar_produtos(self, produtos: Sequence[Produto]) -> None:
        self._limpar_grade()
        self.cards.clear()

        for indice, produto in enumerate(produtos):
            card = self.criar_card(produto)
            self.cards[produto.cache_key] = card
            row, col = divmod(indice, self.GRID_COLUMNS)
            self.grid.addWidget(card, row, col)

    def criar_card(self, produto: Produto) -> PainelCard:
        return PainelCard(produto)

    def atualizar_card(self, produto: Produto) -> None:
        card = self.cards.get(produto.cache_key)
        if card:
            card.update_from_produto(produto)

    def _limpar_grade(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

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


__all__ = ["BasePainelWindow", "PainelCard", "_STATUS_COLORS"]

```

## painel_admin.py

```python
"""Painel administrativo com atualizações assíncronas e gerenciamento de produtos."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable, Iterable, List

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QPoint, QRunnable, QThreadPool

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from painel_base import BasePainelWindow, PainelCard
from services.produtos_service import Produto, ProdutoService

LOGGER = logging.getLogger(__name__)


class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)


class ServiceWorker(QRunnable):
    def __init__(self, fn: Callable[[], Iterable[Produto]]):
        super().__init__()
        self._fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:  # pragma: no cover - executado em thread de trabalho
        try:
            resultado = list(self._fn())
        except Exception as exc:  # pragma: no cover - propagado via sinal
            LOGGER.exception("Worker de serviço falhou")
            self.signals.failed.emit(str(exc))
        else:
            self.signals.finished.emit(resultado)


class PainelAdmin(BasePainelWindow):
    """Janela principal utilizada pelos administradores."""

    REFRESH_INTERVAL_MS = 3000

    def __init__(self, user: dict):
        super().__init__(user, "Painel do Administrador")
        self._service = ProdutoService()
        self._pool = QThreadPool.globalInstance()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._schedule_refresh)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self._schedule_refresh)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel do Administrador inicializado para %s", self.user.get("usuario"))
        self._janela_admin = None
        self._janela_integracao = None
        self._schedule_refresh()
        self._timer.start()

    # ------------------------------------------------------------------
    # Fetch assíncrono
    # ------------------------------------------------------------------
    def _schedule_refresh(self) -> None:
        worker = ServiceWorker(self._fetch_produtos)
        worker.signals.finished.connect(self._apply_produtos)
        worker.signals.failed.connect(self._handle_error)
        self._pool.start(worker)

    def _fetch_produtos(self) -> List[Produto]:
        return self._service.listar_principais()

    def _apply_produtos(self, produtos: List[Produto]) -> None:
        itens = list(produtos)
        if not any(produto.nome == "Painel de Administração" for produto in itens):
            itens.append(Produto(id=None, nome="Painel de Administração", status="Pronto", ultimo_acesso=None))
        self.renderizar_produtos(itens)

    def _handle_error(self, mensagem: str) -> None:
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{mensagem}",
        )

    # ------------------------------------------------------------------
    # Criação e atualização dos cards
    # ------------------------------------------------------------------
    def criar_card(self, produto: Produto) -> PainelCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        card.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda _pos, c=card: self._abrir_menu(c))
        if produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color:#00aaff; color:black; border-radius:6px; padding:6px;")
        return card

    def atualizar_card(self, produto: Produto) -> None:
        super().atualizar_card(produto)
        card = self.cards.get(produto.cache_key)
        if card and produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color:#00aaff; color:black; border-radius:6px; padding:6px;")

    def _abrir_menu(self, card: PainelCard) -> None:
        produto = card.produto
        if produto.id is None:
            QtWidgets.QMessageBox.information(self, "Informação", "Este card não possui ID no banco de dados.")
            return

        menu = QtWidgets.QMenu(card)
        for status in ("Em Desenvolvimento", "Atualizando", "Pronto"):
            action = menu.addAction(status)
            action.triggered.connect(lambda _checked=False, s=status, p=produto: self._alterar_status(p, s))
        menu.exec(card.mapToGlobal(QPoint(10, 10)))

    def _alterar_status(self, produto: Produto, novo_status: str) -> None:
        try:
            if produto.id is not None:
                self._service.atualizar_status(produto.id, novo_status)
                atualizado = replace(produto, status=novo_status)
                self.atualizar_card(atualizado)
        except Exception as exc:
            self.logger.exception("Falha ao alterar status do produto %s", produto.id)
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao atualizar status",
                f"Não foi possível atualizar o status:\n{exc}",
            )

    # ------------------------------------------------------------------
    # Navegação entre módulos
    # ------------------------------------------------------------------
    def _abrir_modulo(self, produto: Produto) -> None:
        nome = produto.nome
        self.logger.info("Abrindo módulo %s", nome)

        if produto.id is not None:
            try:
                self._service.registrar_acesso(produto.id, self.user.get("usuario", ""))
            except Exception:
                self.logger.exception("Falha ao registrar acesso ao produto %s", produto.id)

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Painel de Administração":
            self._abrir_painel_administracao()
        elif nome == "Controle da Integração":
            self._abrir_controle_integracao()
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{nome}' ainda não foi conectado.",
            )

    def _abrir_painel_administracao(self) -> None:
        janela = PainelAdministracao()
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_admin = janela

    def _abrir_controle_integracao(self) -> None:
        janela = ControleIntegracao(self.user)
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_integracao = janela

    # ------------------------------------------------------------------
    # Otimizações
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
"""Painel destinado aos usuários finais com consulta periódica dos produtos."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_base import BasePainelWindow, PainelCard
from services.produtos_service import Produto, ProdutoService


class PainelUser(BasePainelWindow):
    REFRESH_INTERVAL_MS = 3000

    def __init__(self, user: dict):
        super().__init__(user, "Painel do Usuário")
        self._service = ProdutoService()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh_produtos)

        self.logger.info("Painel do Usuário inicializado para %s", self.user.get("usuario"))
        self._janela_integracao = None
        self._refresh_produtos()
        self._timer.start()

    def criar_card(self, produto: Produto) -> PainelCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        return card

    def _refresh_produtos(self) -> None:
        try:
            produtos = self._service.listar_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            return

        self.renderizar_produtos(produtos)

    def _abrir_modulo(self, produto: Produto) -> None:
        nome = produto.nome
        self.logger.info("Usuário acionou módulo %s", nome)

        if produto.id is not None:
            try:
                self._service.registrar_acesso(produto.id, self.user.get("usuario", ""))
            except Exception:
                self.logger.exception(
                    "Falha ao registrar acesso do usuário %s ao produto %s",
                    self.user.get("usuario"),
                    produto.id,
                )
                return

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Controle da Integração":
            janela = ControleIntegracao(self.user)
            janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            janela.show()
            self._janela_integracao = janela
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{nome}' ainda não foi conectado.",
            )


__all__ = ["PainelUser"]

```

## main.py

```python
"""Ponto de entrada da aplicação PySide6 responsável pelo fluxo de login."""

from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from painel_admin import PainelAdmin
from painel_user import PainelUser
from utils import AuthService, Usuario

os.environ.setdefault("QT_OPENGL", "software")


class LoginWindow(QtWidgets.QMainWindow):
    """Janela de autenticação que direciona o usuário para o painel adequado."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self.auth_service = auth_service or AuthService()
        self._painel_atual: Optional[QtWidgets.QWidget] = None

        self.setWindowTitle("Login - Sistema de Painéis")
        self.setFixedSize(420, 320)
        self.setWindowIcon(QtGui.QIcon())
        self._configurar_estilos()
        self._construir_interface()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 22px; font-weight: bold; color: #4ecca3; }
            QLineEdit {
                background-color: #1b1e2b;
                border: 1px solid #3a3f58;
                border-radius: 6px;
                padding: 8px;
                color: white;
            }
            QPushButton {
                background-color: #4ecca3;
                color: black;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #6eecc1; }
            QToolButton {
                border: none;
                background: transparent;
            }
            """
        )

    def _construir_interface(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        titulo = QtWidgets.QLabel("Acesso ao Sistema")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)
        layout.addSpacing(20)

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
        self.btn_toggle_senha.setToolTip("Mostrar/Ocultar senha")
        self.btn_toggle_senha.clicked.connect(self._alternar_senha)
        senha_layout.addWidget(self.btn_toggle_senha)
        layout.addLayout(senha_layout)

        layout.addSpacing(20)

        self.btn_login = QtWidgets.QPushButton("Entrar")
        self.btn_login.clicked.connect(self._executar_login)
        layout.addWidget(self.btn_login)

        self.setCentralWidget(container)

        self.input_usuario.returnPressed.connect(self._executar_login)
        self.input_senha.returnPressed.connect(self._executar_login)
        self.input_usuario.setFocus()

    # ------------------------------------------------------------------
    # Eventos de UI
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: D401 - assinatura Qt
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._executar_login()
        else:
            super().keyPressEvent(event)

    def _alternar_senha(self) -> None:
        if self.input_senha.echoMode() == QtWidgets.QLineEdit.Password:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)

    def _icone_senha(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#4ecca3"), 2))
        painter.drawEllipse(2, 4, 12, 8)
        painter.end()
        return QtGui.QIcon(pixmap)

    # ------------------------------------------------------------------
    # Lógica de autenticação
    # ------------------------------------------------------------------
    def _executar_login(self) -> None:
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Preencha todos os campos.")
            return

        try:
            autenticado = self.auth_service.authenticate(usuario, senha)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Dados inválidos", str(exc))
            return
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao validar login:\n{exc}")
            return

        if not autenticado:
            QtWidgets.QMessageBox.warning(self, "Erro", "Usuário ou senha inválidos.")
            return

        QtWidgets.QMessageBox.information(self, "Sucesso", f"Bem-vindo, {autenticado.nome}!")
        self._abrir_painel(autenticado)

    def _abrir_painel(self, usuario: Usuario) -> None:
        if self._painel_atual is not None:
            self._painel_atual.close()

        painel: QtWidgets.QWidget
        if usuario.tipo.lower() == "admin":
            painel = PainelAdmin(usuario.to_dict())
        else:
            painel = PainelUser(usuario.to_dict())

        painel.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        painel.show()
        painel.closeEvent = self._retornar_para_login  # type: ignore[assignment]

        self._painel_atual = painel
        self.hide()

    def _retornar_para_login(self, event: QtGui.QCloseEvent) -> None:
        self._painel_atual = None
        self.show()
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

