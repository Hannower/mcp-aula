# Servidor MCP Didático: Supabase & Pipeline de Documentos

Servidor construído com o **Model Context Protocol (MCP)** para apoiar o laboratório de IA e agentes inteligentes.

O servidor conecta o Agente de IA a duas fontes fundamentais:
1. **Banco Relacional Remoto (Supabase)**: permite ao agente atuar como um analista de dados (Text-to-SQL analítico e seguro) sobre a tabela `public.documentos`.
2. **Sistema de Arquivos Local / Container (`dados/documentos`)**: permite ao agente inspecionar o status das etapas do pipeline de ingestão (`raw`, `silver` e `gold`).

---

## 1. A Tríade do MCP: Conceitos Fundamentais

Para que os alunos compreendam o papel de cada componente na arquitetura de um Agente de IA:

| Capacidade MCP | O que representa para o Agente | Como está implementado neste Servidor |
| :--- | :--- | :--- |
| **Resources** *(O Mapa)* | **Contexto Passivo / Metadados**.<br>O agente lê para entender o ambiente e os dados sem precisar executar ações ativas. | • `supabase://documentos/schema`: Estrutura técnica e dicionário semântico com o significado de cada coluna.<br>• `local://documentos/status`: Resumo quantitativo de arquivos em `raw`, `silver` e `gold`. |
| **Tools** *(Os Músculos)* | **Ações Ativas / Dinâmicas**.<br>Funções com parâmetros que o LLM decide invocar para consultar ou operar no ambiente. | • `executar_sql_analitico(sql)`: Executa consultas analíticas `SELECT` com segurança e limites.<br>• `amostra_documentos_supabase(limite)`: Retorna exemplos reais de registros.<br>• `listar_documentos_locais(etapa)`: Lista os arquivos de uma pasta do pipeline. |
| **Prompts** *(O Playbook / Raciocínio)* | **Templates de Instrução**.<br>Guias que ensinam o agente a raciocinar passo a passo sobre um objetivo. | • `analisar_documentos_supabase(pergunta)`: Ensina o ciclo: inspecionar schema -> criar SQL analítico -> interpretar resultados.<br>• `consultar_pasta_local(pergunta)`: Orienta a verificação dos arquivos pendentes de ingestão no RAG. |

---

## 2. Fluxo de Raciocínio do Agente (Text-to-SQL Didático)

Quando o aluno faz uma pergunta em linguagem natural no chat ou no Inspector:

```
[Aluno / Usuário]
       │
       ▼  "Qual a média de sucesso dos documentos por categoria?"
┌──────────────┐
│  Agente LLM  │
└──────┬───────┘
       │ 1. Lê o Resource: supabase://documentos/schema
       ▼
┌─────────────────────────┐
│ Dicionário de Campos    │ -> Entende que 'percentual_sucesso' é a coluna de assertividade
└─────────────────────────┘
       │ 2. Formula a query SQL analítica
       ▼
┌─────────────────────────┐
│ SELECT categoria,       │
│ AVG(percentual_sucesso) │
└──────┬──────────────────┘
       │ 3. Invoca a Tool: executar_sql_analitico(sql)
       ▼
┌─────────────────────────┐
│   Validação de Segurança│ -> Valida se inicia com SELECT (somente leitura)
└──────┬──────────────────┘
       │ 4. Executa no Supabase (read_only=True)
       ▼
┌─────────────────────────┐
│   Dados Consolidados    │ -> Retorna as agregações
└──────┬──────────────────┘
       │ 5. Analisa os números e formula a resposta final
       ▼
[Resposta Explicativa para o Aluno]
```

---

## 3. Baixar e iniciar com Docker Desktop

### Pré-requisitos

- Git, Docker Desktop em execução e Docker Compose.
- Um clone do laboratório `laboratorio-ia-docker` e um projeto Supabase com a tabela `public.documentos`.
- Um token pessoal da **Management API** do Supabase com acesso adequado ao projeto. Ele não é a chave `anon`, `publishable` ou `service_role` da API de dados.
- Os arquivos `Dockerfile`, `.dockerignore`, `server.py`, `server_http.py` e `requirements.txt` no clone do MCP. Caso o repositório remoto ainda não contenha os arquivos Docker, eles precisam ser enviados para lá ou criados no clone antes do build.

Para usar o container, não é necessário instalar Python nem criar um `venv` no Windows: o Dockerfile instala as bibliotecas do `requirements.txt` dentro da imagem.

### 1. Clonar na pasta `apps`

No PowerShell, a partir da raiz do seu laboratório, execute:

```powershell
cd "D:\workspace\Digital College\Professor\docker\laboratorio-ia-docker\apps"
git clone https://github.com/proftheosilva/mcp.git
cd ..
```

Adapte o caminho à localização do laboratório no seu computador. Se `apps/mcp` já existe, não execute novamente o clone nessa mesma pasta. A pasta `apps/mcp` conterá os arquivos do servidor; o `compose.yaml` fica na raiz do laboratório.

### 2. Criar o `.env`

Crie `apps/mcp/.env` com as variáveis apresentadas na seção 4. O `.env` não acompanha o clone por conter credenciais. Mantenha-o privado e fora do Git; o `.dockerignore` também o exclui do contexto de build. O Compose lê o arquivo para fornecer as variáveis ao container.

### 3. Configurar o serviço no Compose

O template do laboratório pode conter inicialmente apenas o n8n. Nesse caso, adicione o serviço abaixo dentro de `services:` no `compose.yaml` da raiz. Se já existir um serviço `mcp`, confira sua configuração sem criar uma entrada duplicada:

```yaml
  mcp:
    build:
      context: ./apps/mcp
      dockerfile: Dockerfile
    container_name: laboratorio-mcp
    restart: unless-stopped
    env_file:
      - ./apps/mcp/.env
    environment:
      RAW_DOCUMENTS_DIR: /data/documentos/raw
    ports:
      - "127.0.0.1:8001:8001"
    volumes:
      - ./apps/mcp:/app
      - ./dados/documentos:/data/documentos
    working_dir: /app
    command: ["python", "server_http.py"]
    networks:
      - aula
```

Mantenha a declaração da rede `aula` no nível principal do Compose. O caminho do Windows `dados/documentos` é compartilhado com o container como `/data/documentos`; a aplicação identifica `raw`, `silver` e `gold` a partir dele. `silver` pode não existir ainda. O volume de código permite editar os arquivos no Windows, mas mudanças no `requirements.txt` exigem reconstrução da imagem.

### 4. Construir e iniciar

Na raiz do laboratório, onde está `compose.yaml`:

```powershell
docker compose config --quiet
docker compose up -d --build mcp
docker compose ps
docker compose logs -f mcp
```

O primeiro comando verifica a configuração; o segundo constrói a imagem e inicia o MCP. Para deixar de acompanhar os logs, pressione `Ctrl+C`: o container continua ativo. Se alterar o `.env`, recrie o serviço com `docker compose up -d --force-recreate mcp`, pois um simples `restart` não recarrega o arquivo de variáveis do Compose.

### 5. Conectar e testar

- Em um cliente no Windows ou no MCP Inspector: **Streamable HTTP**, `http://localhost:8001/mcp`.
- Em outro serviço na mesma rede Docker, como o n8n: `http://mcp:8001/mcp`.
- No Inspector, conecte ao servidor, liste as Tools e teste `amostra_documentos_supabase` ou `listar_documentos_locais`. O acesso direto à URL pelo navegador não substitui um cliente MCP compatível.
- Para parar somente este servidor, na raiz do laboratório, use `docker compose stop mcp`; para iniciá-lo novamente, use `docker compose up -d mcp`.

Se o servidor não iniciar, confira `docker compose logs mcp`, o `.env`, o token e o acesso ao Supabase. Um erro HTTP 401 do Supabase indica falha de autenticação; revise o token sem divulgá-lo. A porta está vinculada ao `localhost` no exemplo; não exponha o servidor publicamente sem autenticação e proteção adequadas.

---

## 4. Configuração Local (.env)

O arquivo `.env` na pasta deste projeto contém as credenciais para acesso à Management API do Supabase:

```dotenv
SUPABASE_URL=https://api.supabase.com/v1/projects
SUPABASE_REF_PROJECT=seu_project_ref
SUPABASE_API_TOKEN=seu_token_de_acesso
```

---

## 5. Capacidades Disponíveis no Servidor

### A. Banco de Dados (Supabase)

1. **`supabase://documentos/schema`** (Resource):
   - Retorna as colunas de `public.documentos` (`id`, `nome_arquivo`, `categoria`, `total_campos`, `campos_preenchidos`, `campos_nulos`, `percentual_sucesso`, `status`, `criado_em`) acompanhadas da explicação em linguagem natural do que cada campo significa.

2. **`executar_sql_analitico(sql)`** (Tool):
   - Permite consultas analíticas usando `SELECT`, `WHERE`, `GROUP BY`, `ORDER BY`, `COUNT(*)`, `AVG()`.
   - **Camada de Segurança**: Bloqueia comandos destrutivos (`DROP`, `DELETE`, `UPDATE`, `INSERT`, etc.) e aplica `LIMIT 50` por padrão caso o usuário/agente não especifique.

3. **`amostra_documentos_supabase(limite)`** (Tool):
   - Retorna de 1 a 10 linhas da tabela para visualização imediata do formato dos registros.

4. **`analisar_documentos_supabase(pergunta)`** (Prompt):
   - Instrução estruturada para conduzir o agente na análise de dados.

### B. Pasta Local de Documentos (`..\dados\documentos`)

1. **`local://documentos/status`** (Resource):
   - Exibe a contagem de arquivos e os primeiros nomes nas pastas `raw`, `silver` e `gold`.

2. **`listar_documentos_locais(etapa)`** (Tool):
   - Lista todos os arquivos presentes em uma etapa específica (`raw`, `silver` ou `gold`).

3. **`consultar_pasta_local(pergunta)`** (Prompt):
   - Template para orientar o agente no monitoramento dos arquivos brutos antes da ingestão no RAG.

---

## 6. Exemplos de Consultas Didáticas para Teste

No **MCP Inspector** ou no chat com o Agente, experimente testar:

### Contagem por Status:
```sql
SELECT status, count(*) AS total 
FROM public.documentos 
GROUP BY status;
```

### Média de Sucesso por Categoria:
```sql
SELECT categoria, round(avg(percentual_sucesso::numeric), 2) AS media_sucesso, count(*) AS total_docs
FROM public.documentos
GROUP BY categoria;
```

### Documentos com Menor Assertividade:
```sql
SELECT nome_arquivo, categoria, percentual_sucesso, campos_nulos
FROM public.documentos
ORDER BY percentual_sucesso::numeric ASC
LIMIT 5;
```

---

## 7. Estrutura de Arquivos

```
apps/mcp/
├── server.py         # Código-fonte principal com Resources, Tools e Prompts
├── server_http.py    # Inicializador para transporte HTTP (acesso via rede Docker)
├── Dockerfile        # Constrói a imagem Python deste servidor
├── .dockerignore     # Exclui segredos e arquivos desnecessários do build
├── requirements.txt  # Lista de dependências Python
├── .env              # Variáveis de ambiente e credenciais locais
└── README.md         # Documentação e guia conceitual para os alunos
```
