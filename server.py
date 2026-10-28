"""
==============================================================================
SERVIDOR MCP DIDÁTICO: SUPABASE & DOCUMENTOS LOCAIS
==============================================================================
Servidor Model Context Protocol (MCP) desenvolvido para fins didáticos.
Demonstra a tríade fundamental do MCP:
  - Resources (Contexto passivo / Schemas e Metadados)
  - Tools (Ações ativas / Consultas SQL analíticas e Listagens)
  - Prompts (Instruções guiadas de raciocínio para o Agente)

Capacidades integradas:
  1. Banco de Dados Remoto (Supabase): Consultas relacionais e Text-to-SQL analítico.
  2. Sistema de Arquivos Local (Pipeline): Monitoramento das pastas raw, silver e gold.
==============================================================================
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

# ------------------------------------------------------------------------------
# 1. CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ------------------------------------------------------------------------------

# Carrega as variáveis do arquivo .env
load_dotenv(Path(__file__).with_name(".env"), override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_REF_PROJECT = os.getenv("SUPABASE_REF_PROJECT")
SUPABASE_API_TOKEN = os.getenv("SUPABASE_API_TOKEN")

def obter_pasta_documentos() -> Path:
    """
    Localiza o diretório de documentos do pipeline (dados/documentos).
    Funciona tanto no ambiente local quanto montado dentro do container Docker.
    """
    # 1. Variável de ambiente explícita
    env_dir = os.getenv("DOCUMENTS_DIR") or os.getenv("RAW_DOCUMENTS_DIR")
    if env_dir:
        caminho = Path(env_dir)
        if caminho.name.lower() == "raw":
            return caminho.parent
        return caminho

    # 2. Caminhos relativos padrão no projeto
    candidatos = [
        Path(r"..\dados\documentos"),
        Path(__file__).resolve().parent.parent.parent / "dados" / "documentos",
        Path(__file__).resolve().parent.parent / "dados" / "documentos",
        Path("/data/documentos"),
    ]
    for c in candidatos:
        if c.exists():
            return c

    # Fallback padrão
    return Path(r"..\dados\documentos")

PASTA_DOCUMENTOS = obter_pasta_documentos()

# Instância do servidor MCP
mcp = MCPServer("supabase")


# ------------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES (CONEXÃO COM SUPABASE E SEGURANÇA SQL)
# ------------------------------------------------------------------------------

def executar_query_supabase(sql: str) -> list:
    """
    Envia uma instrução SQL para o endpoint de query do Supabase.
    A API é chamada com 'read_only: True' para segurança.
    """
    if not SUPABASE_URL or not SUPABASE_API_TOKEN or not SUPABASE_REF_PROJECT:
        raise ValueError("Configurações do Supabase ausentes no arquivo .env!")

    url = f"{SUPABASE_URL}/{SUPABASE_REF_PROJECT}/database/query"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SUPABASE_API_TOKEN}"
    }
    payload = {
        "query": sql,
        "read_only": True
    }

    resposta = requests.post(url, headers=headers, json=payload, timeout=30)
    resposta.raise_for_status()
    return resposta.json()


def validar_sql_somente_leitura(sql: str) -> tuple[bool, str]:
    """
    Validação didática de segurança:
    Garante que apenas instruções SELECT ou WITH (CTE) sejam executadas,
    bloqueando tentativas de alteração de dados (DROP, DELETE, UPDATE, etc).
    """
    sql_limpo = sql.strip().upper()

    # Deve iniciar com SELECT ou WITH
    if not (sql_limpo.startswith("SELECT") or sql_limpo.startswith("WITH")):
        return False, "Apenas consultas de leitura iniciadas com SELECT ou WITH são permitidas."

    # Palavras proibidas de alteração estrutural ou remoção
    palavras_proibidas = [
        "INSERT ", "UPDATE ", "DELETE ", "DROP ",
        "ALTER ", "TRUNCATE ", "CREATE ", "GRANT ", "REVOKE "
    ]
    for palavra in palavras_proibidas:
        if palavra in sql_limpo:
            return False, f"Comando restrito detectado ({palavra.strip()}). Use apenas consultas analíticas."

    return True, "SQL válido."


# ------------------------------------------------------------------------------
# 3. CAPACIDADES MCP: SUPABASE (BANCO DE DADOS RELACIONAL)
# ------------------------------------------------------------------------------

# --- RESOURCE: O "Mapa" dos Dados (Schema e Dicionário Semântico) ---
@mcp.resource("supabase://documentos/schema")
def obter_schema_documentos() -> str:
    """
    Retorna a estrutura técnica da tabela public.documentos junto ao dicionário
    de campos explicativo, permitindo ao Agente formular queries assertivas.
    """
    sql_schema = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'documentos'
        ORDER BY ordinal_position;
    """
    try:
        colunas_banco = executar_query_supabase(sql_schema)
    except Exception as erro:
        colunas_banco = f"Não foi possível obter information_schema: {str(erro)}"

    dicionario = {
        "tabela": "public.documentos",
        "descricao": "Armazena metadados dos documentos processados pelo pipeline de IA.",
        "colunas_tecnicas": colunas_banco,
        "dicionario_semantico": {
            "id": "Identificador único do registro (UUID)",
            "nome_arquivo": "Nome original do arquivo (ex: 'NF_1042_TechByte.pdf')",
            "categoria": "Tipo do documento (ex: 'Notas Fiscais', 'Contratos')",
            "total_campos": "Total de campos esperados na extração de dados",
            "campos_preenchidos": "Quantidade de campos preenchidos com sucesso",
            "campos_nulos": "Quantidade de campos que ficaram sem valor",
            "percentual_sucesso": "Porcentagem de assertividade da extração (0.00 a 100.00)",
            "status": "Situação do processamento ('PROCESSADO', 'PARCIAL', 'PENDENTE', 'ERRO')",
            "criado_em": "Data e hora do registro no banco de dados"
        }
    }
    return json.dumps(dicionario, indent=4, ensure_ascii=False)


# --- TOOL 1: Execução de SQL Analítico Dinâmico ---
@mcp.tool()
def executar_sql_analitico(sql: str) -> list:
    """
    Executa uma consulta SQL analítica (leitura) na tabela public.documentos do Supabase.
    Permite comandos como COUNT, AVG, SUM, GROUP BY, ORDER BY, WHERE para responder perguntas analíticas.
    Exemplo: 'SELECT categoria, status, count(*), round(avg(percentual_sucesso::numeric), 2) as media FROM public.documentos GROUP BY categoria, status;'
    """
    # 1. Validação de segurança
    valido, motivo = validar_sql_somente_leitura(sql)
    if not valido:
        raise ValueError(f"Consulta rejeitada: {motivo}")

    # 2. Proteção de contexto: se não houver LIMIT, aplica LIMIT 50 por padrão
    sql_exec = sql.strip().rstrip(";")
    if "LIMIT" not in sql_exec.upper():
        sql_exec = f"{sql_exec} LIMIT 50"

    return executar_query_supabase(sql_exec)


# --- TOOL 2: Obter Amostra de Registros ---
@mcp.tool()
def amostra_documentos_supabase(limite: int = 3) -> list:
    """
    Retorna uma amostra de registros recentes da tabela public.documentos.
    Permite ao Agente inspecionar exemplos reais de dados antes de formular consultas complexas.
    """
    if not 1 <= limite <= 10:
        limite = 3

    sql = f"""
        SELECT id, nome_arquivo, categoria, status, percentual_sucesso, criado_em
        FROM public.documentos
        ORDER BY criado_em DESC
        LIMIT {limite};
    """
    return executar_query_supabase(sql)


# --- PROMPT: Guia de Raciocínio para Análise no Supabase ---
@mcp.prompt()
def analisar_documentos_supabase(pergunta: str) -> str:
    """
    Orienta o Agente no fluxo completo de análise de dados no Supabase:
    1. Inspecionar o schema e o dicionário de campos.
    2. Construir o SQL analítico adequado.
    3. Interpretar os resultados e responder com clareza.
    """
    return f"""
    Você é um Assistente Especialista em Análise de Dados e Banco Relacional (Supabase).
    Pergunta solicitada pelo usuário: "{pergunta}"

    Siga rigorosamente este fluxo de raciocínio:
    1. Consulte o recurso 'supabase://documentos/schema' para conhecer os campos e o significado de cada coluna.
    2. Formule uma consulta SQL analítica (SELECT) adequada para responder à pergunta.
       Dicas:
       - Para médias de sucesso, converta para numérico: AVG(percentual_sucesso::numeric).
       - Utilize GROUP BY e COUNT(*) para sumarizar dados por categoria ou status.
    3. Execute a query através da tool 'executar_sql_analitico'.
    4. Apresente ao usuário uma resposta concisa, factual e bem formatada com os dados obtidos.
    """


# ------------------------------------------------------------------------------
# 4. CAPACIDADES MCP: PASTA LOCAL (PIPELINE DE DOCUMENTOS)
# ------------------------------------------------------------------------------

# --- RESOURCE: Status do Pipeline Local (Contagem de Arquivos) ---
@mcp.resource("local://documentos/status")
def status_documentos_locais() -> str:
    """
    Retorna o status quantitativo das pastas locais do pipeline RAG:
    - raw: documentos recebidos aguardando ingestão.
    - silver: documentos em processamento/extração.
    - gold: documentos finalizados com sucesso.
    """
    etapas = ["raw", "silver", "gold"]
    resumo = {
        "pasta_base": str(PASTA_DOCUMENTOS),
        "etapas": {}
    }

    for etapa in etapas:
        pasta_etapa = PASTA_DOCUMENTOS / etapa
        if pasta_etapa.exists() and pasta_etapa.is_dir():
            arquivos = [f for f in os.listdir(pasta_etapa) if not f.startswith(".")]
            resumo["etapas"][etapa] = {
                "quantidade": len(arquivos),
                "amostra_arquivos": arquivos[:5]
            }
        else:
            resumo["etapas"][etapa] = {
                "quantidade": 0,
                "aviso": "Pasta ainda não criada ou inacessível"
            }

    return json.dumps(resumo, indent=4, ensure_ascii=False)


# --- TOOL: Listar Arquivos Locais por Etapa ---
@mcp.tool()
def listar_documentos_locais(etapa: str = "raw") -> list[str]:
    """
    Lista os nomes dos arquivos presentes na pasta local de uma etapa do pipeline.
    Opções válidas de etapa: 'raw' (brutos), 'silver' (processando) ou 'gold' (concluídos).
    """
    etapa_limpa = etapa.lower().strip()
    if etapa_limpa not in ["raw", "silver", "gold"]:
        raise ValueError("A etapa informada deve ser 'raw', 'silver' ou 'gold'.")

    pasta_alvo = PASTA_DOCUMENTOS / etapa_limpa
    if not pasta_alvo.exists() or not pasta_alvo.is_dir():
        return []

    return [f for f in os.listdir(pasta_alvo) if not f.startswith(".")]


# --- PROMPT: Guia para Monitoramento dos Arquivos Locais ---
@mcp.prompt()
def consultar_pasta_local(pergunta: str) -> str:
    """
    Orienta o Agente a verificar o status e o fluxo de arquivos locais do pipeline RAG.
    """
    return f"""
    Você é um assistente encarregado de verificar o pipeline de arquivos locais do RAG.
    Pergunta do usuário: "{pergunta}"

    Diretrizes:
    1. Consulte o recurso 'local://documentos/status' para obter o panorama das pastas (raw, silver, gold).
    2. Se for necessário detalhar nomes específicos de arquivos, use a tool 'listar_documentos_locais(etapa)'.
    3. Responda em português de forma clara e direta sobre a situação dos arquivos.
    """


# ------------------------------------------------------------------------------
# 5. INICIALIZAÇÃO DO SERVIDOR MCP
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Inicia o servidor via stdio para integração direta com clientes MCP
    mcp.run(transport="stdio")
