# Painel_Integracao

Sistema desenvolvido em Python (PySide6) para controle e automação de tarefas internas da Franco. Integra dashboards, pop-ups e conexões com banco MySQL, permitindo gerenciar fluxos, prioridades e status em uma interface moderna e responsiva.

## Como executar o projeto sem erros

1. **Instale as dependências Python.** O projeto foi testado com Python 3.9+. Instale os pacotes necessários:

   ```bash
   pip install PySide6 mysql-connector-python bcrypt python-dotenv
   ```

2. **Configure as credenciais do banco.** O módulo [`database.py`](database.py) carrega variáveis de ambiente e arquivos `.env` automaticamente. Crie um arquivo `.env` na raiz do projeto (ou exporte variáveis no seu shell) com, no mínimo, os campos abaixo. Ajuste os valores para o seu servidor MySQL.

   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=seu_usuario
   DB_PASS=sua_senha
   DB_NAME=sistema_login
   DB_POOL_SIZE=8
   ```

3. **Prepare as tabelas.** O guia [`docs/conexao_tabelas.md`](docs/conexao_tabelas.md) contém os comandos `CREATE TABLE` para `usuarios`, `produtos`, `acessos` e `historico_manuais`. Execute esses scripts no banco configurado. Não é necessário inserir os produtos manualmente; eles são criados na primeira execução.

4. **Crie um usuário inicial.** Utilize `python gerar_hash.py` para gerar o hash Bcrypt de uma senha, depois insira o usuário na tabela `usuarios` com o hash retornado. Certifique-se de marcar o campo `tipo` como `admin` para validar o painel administrativo.

5. **Valide a conexão com o banco.** Antes da interface, execute `python teste_db.py`. O script confirma que o pool de conexões está funcional e registra eventuais erros no diretório `logs/`.

6. **Execute a aplicação.** Com o banco preparado, rode `python main.py`. Informe o usuário e senha cadastrados. Dependendo do valor do campo `tipo`, a aplicação abrirá o painel do administrador ou do usuário.

Se desejar copiar todo o código atualizado manualmente ou revisar a arquitetura, consulte [`docs/codigo_para_implementacao.md`](docs/codigo_para_implementacao.md).
