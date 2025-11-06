# Guia de conexão das tabelas do banco de dados

Este guia complementa a reescrita do código explicando como preparar e conectar todas as tabelas utilizadas pela aplicação. A sequência abaixo cobre a configuração das credenciais, a criação das tabelas e como validar a conectividade antes de executar a interface gráfica.

## 1. Configurar as credenciais do banco

1. Defina as variáveis de ambiente exigidas pelo módulo `database.py` (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME` e opcionalmente `DB_POOL_SIZE`).
2. Como alternativa, crie um arquivo `.env` na raiz do projeto com o conteúdo abaixo:

   ```bash
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASS=int123!
   DB_NAME=sistema_login
   DB_POOL_SIZE=8
   ```

3. O código carrega automaticamente o `.env` e abre um pool de conexões. Utilize valores reais condizentes com o seu ambiente (produção, testes, etc.).

## 2. Estrutura das tabelas necessárias

Crie as tabelas no banco `sistema_login` (ou outro nome configurado) utilizando os comandos a seguir. Todas as instruções assumem MySQL/MariaDB.

### 2.1. Tabela `usuarios`

Registra os usuários com hash Bcrypt das senhas.

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(60) NOT NULL UNIQUE,
    nome VARCHAR(120) NOT NULL,
    tipo ENUM('admin', 'usuario') NOT NULL DEFAULT 'usuario',
    senha_hash VARCHAR(200) NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.2. Tabela `produtos`

Armazena os módulos exibidos nos painéis.

```sql
CREATE TABLE IF NOT EXISTS produtos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(120) NOT NULL UNIQUE,
    status VARCHAR(60) NOT NULL DEFAULT 'Pronto',
    ultimo_acesso DATETIME NULL,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.3. Tabela `acessos`

Registra cada abertura de módulo, vinculada ao usuário.

```sql
CREATE TABLE IF NOT EXISTS acessos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(60) NOT NULL,
    produto_id INT NOT NULL,
    momento DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.4. Tabela `historico_manuais` (opcional)

Mantida para compatibilidade com o módulo de manuais, caso você utilize esse recurso.

```sql
CREATE TABLE IF NOT EXISTS historico_manuais (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(60) NOT NULL,
    arquivo VARCHAR(255) NOT NULL,
    aberto_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 3. Popular dados iniciais

1. Gere o hash da senha utilizando `python gerar_hash.py` e informe a senha desejada. Insira o resultado na coluna `senha_hash` da tabela `usuarios`.
2. Não é necessário inserir manualmente os produtos padrão: o `ProdutoService` cria as entradas ausentes automaticamente na primeira execução.

## 4. Validar a conexão

1. Execute `python teste_db.py` para confirmar que a conexão com o banco está funcionando.
2. Verifique os logs gerados em `logs/` para confirmar o sucesso da criação do pool de conexões (mensagens como `Pool de conexões inicializado`).

## 5. Dicas adicionais

- Caso deseje utilizar outro banco ou usuário, ajuste apenas o `.env` sem alterar o código.
- O campo `momento` na tabela `acessos` é utilizado para exibir o histórico ordenado; mantenha-o com `DEFAULT CURRENT_TIMESTAMP` para registrar automaticamente a data/hora de cada acesso.
- Em ambientes de produção, conceda privilégios mínimos ao usuário do banco: `SELECT`, `INSERT`, `UPDATE` nas tabelas acima são suficientes para o painel.

Seguindo estas etapas, todas as dependências de banco de dados estarão preparadas para que os painéis funcionem corretamente.
