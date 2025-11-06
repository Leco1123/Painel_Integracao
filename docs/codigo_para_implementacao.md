# Código pronto para implementação
Este arquivo reúne as versões completas dos módulos principais após as melhorias.
Copie cada trecho para o arquivo correspondente no projeto caso esteja aplicando as
alterações manualmente.

> **Dica:** Antes de substituir qualquer arquivo, faça um backup/local commit para
> garantir que seja possível voltar atrás se necessário.

---

## `database.py`
```python
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

```

## `painel_base.py`
```python
from __future__ import annotations

import logging
from typing import Callable

from PySide6 import QtWidgets
from PySide6.QtCore import Qt


class BasePainelCards(QtWidgets.QMainWindow):
    """Janela base com layout e estilo compartilhados pelos painéis."""

    GRID_COLUMNS = 3
    STYLE_SHEET = """
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
        self.setWindowTitle(title)
        self.setGeometry(400, 150, 1100, 650)
        self.setStyleSheet(self.STYLE_SHEET)
        self._build_base_ui()

    def _build_base_ui(self) -> None:
        container = QtWidgets.QWidget()
        layout_root = QtWidgets.QVBoxLayout(container)

        saudacao = QtWidgets.QLabel(f"Olá, {self.user['nome']}!")
        saudacao.setObjectName("Saudacao")
        saudacao.setAlignment(Qt.AlignCenter)
        layout_root.addWidget(saudacao)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(20)
        layout_root.addLayout(self.grid)

        rodape = QtWidgets.QLabel("🟢 Conectado ao sistema_login (MariaDB)")
        rodape.setObjectName("RodapeStatus")
        rodape.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        layout_root.addWidget(rodape)

        self.setCentralWidget(container)

    # ===============================================================
    # Utilidades de layout
    # ===============================================================
    def limpar_grade(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def posicionar_card(self, card: QtWidgets.QWidget, indice: int) -> None:
        row, col = divmod(indice, self.GRID_COLUMNS)
        self.grid.addWidget(card, row, col)

    def preencher_grade(self, produtos: list, builder: Callable[[dict], QtWidgets.QWidget]) -> None:
        self.limpar_grade()
        for indice, produto in enumerate(produtos):
            self.posicionar_card(builder(produto), indice)

    # ===============================================================
    # Utilidades gerais
    # ===============================================================
    @staticmethod
    def formatar_data(valor) -> str:
        if not valor:
            return "-"
        try:
            from datetime import datetime

            if isinstance(valor, datetime):
                return valor.strftime("%d/%m/%Y %H:%M")
            return datetime.fromisoformat(str(valor).replace("Z", "").split(".")[0]).strftime(
                "%d/%m/%Y %H:%M"
            )
        except Exception:  # pragma: no cover - fallback defensivo
            return str(valor)


```

## `services/produtos_service.py`
```python
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


```

## `painel_admin.py`
```python
import logging

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QPoint

from painel_base import BasePainelCards
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from controle_integracao.controle_integracao import ControleIntegracao
from services.produtos_service import (
    atualizar_status_produto,
    obter_produtos_principais,
    registrar_acesso_produto,
)


# ==========================
# 1) Worker assíncrono (fetch do DB)
# ==========================
class ProdutosFetcherSignals(QObject):
    done = Signal(list)
    error = Signal(str)

class ProdutosFetcher(QRunnable):
    def __init__(self, fetch_fn):
        super().__init__()
        self.fetch_fn = fetch_fn
        self.signals = ProdutosFetcherSignals()
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        try:
            produtos = self.fetch_fn()
            self.signals.done.emit(produtos)
        except Exception as e:
            self.logger.exception("Falha ao buscar produtos no worker.")
            self.signals.error.emit(str(e))


class PainelAdmin(BasePainelCards):
    def __init__(self, user):
        super().__init__(user, "Painel do Administrador")
        self._card_cache = {}  # {nome: {"frame":..., "lbl_status":..., "lbl_acesso":..., "btn":...}}

        # Pool global para os workers
        self.pool = QThreadPool.globalInstance()

        # 3) Atalhos
        QtWidgets.QShortcut(QtCore.QKeySequence("Ctrl+R"), self, self._agendar_refresh_async)
        QtWidgets.QShortcut(QtCore.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel do Administrador inicializado para %s", self.user["usuario"])
        # Primeira carga (assíncrona)
        self._agendar_refresh_async(first_build=True)

        # Atualização automática dos cards (assíncrona)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._agendar_refresh_async)
        self.timer.start(3000)

    # ===============================================================
    # 1) Refresh assíncrono
    # ===============================================================
    def _agendar_refresh_async(self, first_build: bool = False):
        self.logger.debug("Agendando refresh dos produtos (first_build=%s)", first_build)
        worker = ProdutosFetcher(self._buscar_produtos_fixos)
        worker.signals.done.connect(lambda produtos: self._aplicar_produtos(produtos, first_build))
        worker.signals.error.connect(self._exibir_erro_fetch)
        self.pool.start(worker)

    def _exibir_erro_fetch(self, mensagem: str) -> None:
        self.logger.error("Erro ao atualizar lista de produtos: %s", mensagem)
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{mensagem}",
        )

    def _aplicar_produtos(self, produtos: list, first_build: bool = False):
        # Garante o "Painel de Administração"
        if not any((p.get("nome", "").lower() == "painel de administração") for p in produtos):
            produtos.append({
                "id": -1,
                "nome": "Painel de Administração",
                "status": "Pronto",
                "ultimo_acesso": None
            })

        if first_build or not self._card_cache:
            # Limpa grade e monta do zero
            while self.grid.count():
                item = self.grid.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._card_cache.clear()

            for idx, produto in enumerate(produtos):
                row, col = divmod(idx, 3)
                card_info = self._criar_card(produto)
                self._card_cache[produto["nome"]] = card_info
                self.grid.addWidget(card_info["frame"], row, col)
            return

        # Atualização incremental
        for produto in produtos:
            nome = produto["nome"]
            if nome in self._card_cache:
                self._atualizar_card(self._card_cache[nome], produto)
            else:
                idx = len(self._card_cache)
                row, col = divmod(idx, 3)
                card_info = self._criar_card(produto)
                self._card_cache[nome] = card_info
                self.grid.addWidget(card_info["frame"], row, col)

    # ===============================================================
    # 4) Buscar produtos (compatível com pool em database.conectar)
    # ===============================================================
    def _buscar_produtos_fixos(self):
        return obter_produtos_principais()

    # ===============================================================
    # Cards + 2) Menu de contexto
    # ===============================================================
    def _criar_card(self, produto):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setSpacing(6)

        lbl_nome = QtWidgets.QLabel(produto["nome"])
        lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        lay.addWidget(lbl_nome)

        status = (produto["status"] or "Desconhecido").strip()
        cor_status = {"Em Desenvolvimento": "#ff5555", "Atualizando": "#ffaa00", "Pronto": "#4ecca3"}.get(status, "#888")
        lbl_status = QtWidgets.QLabel(f"Status: {status}")
        lbl_status.setObjectName("StatusLabel")
        lbl_status.setStyleSheet(f"color:{cor_status}; font-weight:bold;")
        lay.addWidget(lbl_status)

        lbl_acesso = QtWidgets.QLabel(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )
        lay.addWidget(lbl_acesso)

        btn = QtWidgets.QPushButton("Abrir")
        if status.lower() != "pronto" and produto["nome"].lower() != "painel de administração":
            btn.setEnabled(False)
            btn.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            cor = "#00aaff" if produto["nome"].lower() == "painel de administração" else cor_status
            btn.setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")
        btn.clicked.connect(lambda _, p=produto: self._abrir_modulo(p))
        lay.addWidget(btn)

        # Duplo clique abre
        frame.mouseDoubleClickEvent = lambda ev, p=produto: self._abrir_modulo(p)

        # 2) Menu de contexto
        frame.setContextMenuPolicy(Qt.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, p=produto, f=frame: self._abrir_menu_card(f, p))

        return {"frame": frame, "lbl_status": lbl_status, "lbl_acesso": lbl_acesso, "btn": btn}

    def _abrir_menu_card(self, widget, produto):
        menu = QtWidgets.QMenu(widget)
        for novo in ["Em Desenvolvimento", "Atualizando", "Pronto"]:
            action = menu.addAction(novo)
            action.triggered.connect(lambda _, n=novo, p=produto: self._atualizar_status_produto(p, n))
        # abre no canto superior do card (ponto fixo evita problemas de layout)
        menu.exec(widget.mapToGlobal(QPoint(10, 10)))

    def _atualizar_card(self, card, produto):
        status = (produto["status"] or "Desconhecido").strip()
        cor_status = {"Em Desenvolvimento": "#ff5555", "Atualizando": "#ffaa00", "Pronto": "#4ecca3"}.get(status, "#888")
        card["lbl_status"].setText(f"Status: {status}")
        card["lbl_status"].setStyleSheet(f"color:{cor_status}; font-weight:bold;")
        card["lbl_acesso"].setText(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )

        if status.lower() != "pronto" and produto["nome"].lower() != "painel de administração":
            card["btn"].setEnabled(False)
            card["btn"].setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            cor = "#00aaff" if produto["nome"].lower() == "painel de administração" else cor_status
            card["btn"].setEnabled(True)
            card["btn"].setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")

    def _atualizar_status_produto(self, produto, novo_status):
        try:
            if produto.get("id", -1) == -1:
                QtWidgets.QMessageBox.information(self, "Aviso", "Este card é virtual e não possui ID no banco.")
                return
            atualizar_status_produto(produto["id"], novo_status)
            # feedback visual imediato
            produto["status"] = novo_status
            card = self._card_cache.get(produto["nome"])
            if card:
                self._atualizar_card(card, produto)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Não foi possível atualizar o status:\n{e}")
            self.logger.exception("Falha ao atualizar status do produto %s", produto.get("id"))

    # ===============================================================
    # Roteamento
    # ===============================================================
    def _abrir_modulo(self, produto):
        nome = produto["nome"]
        self.logger.info("Ação de abrir módulo: %s", nome)

        try:
            if produto.get("id", -1) != -1:
                registrar_acesso_produto(produto["id"], self.user["usuario"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
            self.logger.exception("Falha ao registrar acesso do módulo %s", produto.get("id"))
            return

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Painel de Administração":
            self.janela_admin = PainelAdministracao()
            self.janela_admin.show()
        elif nome == "Controle da Integração":
            self.janela_integracao = ControleIntegracao(self.user)
            self.janela_integracao.show()
        else:
            QtWidgets.QMessageBox.information(self, "Ainda não implementado",
                                              f"O módulo '{nome}' ainda não foi conectado.")

    # ===============================================================
    # 1) Bônus: pausa o timer quando perde foco (economiza recursos)
    # ===============================================================
    def event(self, e):
        if e.type() == QtCore.QEvent.WindowActivate:
            if not self.timer.isActive():
                self.timer.start(3000)
        elif e.type() == QtCore.QEvent.WindowDeactivate:
            if self.timer.isActive():
                self.timer.stop()
        return super().event(e)

```

## `painel_user.py`
```python
from PySide6 import QtWidgets, QtCore

from painel_base import BasePainelCards
from manuais_bridge import abrir_manuais_via_qt
from controle_integracao.controle_integracao import ControleIntegracao  # 🔗 integração total
from services.produtos_service import obter_produtos_principais, registrar_acesso_produto


class PainelUser(BasePainelCards):
    def __init__(self, user):
        super().__init__(user, "Painel do Usuário")
        self.logger.info("Painel do Usuário inicializado para %s", self.user["usuario"])
        self._preencher_cards()

        # Atualização automática dos cards
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._preencher_cards)
        self.timer.start(3000)

    # ===============================================================
    # Atualiza os cards
    # ===============================================================
    def _preencher_cards(self):
        try:
            produtos = obter_produtos_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            produtos = []

        self.preencher_grade(produtos, self._criar_card)

    # ===============================================================
    # Criação dos cards
    # ===============================================================
    def _criar_card(self, produto):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setSpacing(6)

        # Nome
        lbl_nome = QtWidgets.QLabel(produto["nome"])
        lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        lay.addWidget(lbl_nome)

        # Status
        status_texto = produto["status"] or "Desconhecido"
        cor_status = {
            "Em Desenvolvimento": "#ff5555",
            "Atualizando": "#ffaa00",
            "Pronto": "#4ecca3",
        }.get(status_texto, "#888888")

        lbl_status = QtWidgets.QLabel(f"Status: {status_texto}")
        lbl_status.setObjectName("StatusLabel")
        lbl_status.setStyleSheet(f"color: {cor_status}; font-weight:bold;")
        lay.addWidget(lbl_status)

        # Último acesso
        lbl_acesso = QtWidgets.QLabel(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )
        lay.addWidget(lbl_acesso)

        # Botão
        btn_abrir = QtWidgets.QPushButton("Abrir")
        status_norm = status_texto.strip().lower()

        if status_norm != "pronto":
            btn_abrir.setEnabled(False)
            btn_abrir.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            btn_abrir.setStyleSheet(f"background-color:{cor_status}; color:black; border-radius:6px; padding:6px;")

        btn_abrir.clicked.connect(lambda _, p=produto: self._abrir_modulo(p))
        lay.addWidget(btn_abrir)
        return frame

    # ===============================================================
    # Roteamento dos módulos
    # ===============================================================
    def _abrir_modulo(self, produto):
        nome_modulo = produto["nome"]
        status_modulo = (produto["status"] or "").strip().lower()
        self.logger.info("Usuário solicitou módulo '%s' (status=%s)", nome_modulo, status_modulo)

        # Log de acesso
        try:
            registrar_acesso_produto(produto["id"], self.user["usuario"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
            self.logger.exception(
                "Falha ao registrar acesso do usuário %s ao produto %s",
                self.user["usuario"],
                produto.get("id"),
            )
            return

        # Abre os módulos
        if nome_modulo == "Manuais":
            abrir_manuais_via_qt(self)
            return

        if nome_modulo == "Controle da Integração":
            self.janela_integracao = ControleIntegracao(self.user)
            self.janela_integracao.show()
            return

        QtWidgets.QMessageBox.information(
            self, "Ainda não implementado",
            f"O módulo '{nome_modulo}' ainda não foi conectado."
        )

```

## `utils.py`
```python
import logging

import bcrypt

from database import conectar

LOGGER = logging.getLogger(__name__)

def verificar_login(usuario, senha):
    try:
        with conectar() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
                user = cursor.fetchone()
            finally:
                cursor.close()

        if user and bcrypt.checkpw(senha.encode("utf-8"), user["senha_hash"].encode("utf-8")):
            registrar_acesso(user["usuario"])
            return user
    except Exception:
        LOGGER.exception("Erro ao verificar login do usuário '%s'", usuario)
        raise

    return None

def registrar_acesso(usuario):
    """Atualiza o último acesso de todos os produtos e registra o log."""

    try:
        with conectar() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW()")
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id) SELECT %s, id FROM produtos",
                    (usuario,),
                )
                conn.commit()
            finally:
                cursor.close()
    except Exception:
        LOGGER.exception("Erro ao registrar acesso em massa do usuário '%s'", usuario)
        raise

```

