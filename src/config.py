"""Configuração do assistente. Tudo o que se ajusta fica aqui (espelha a célula 5 do notebook)."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# --- Pastas ---
DOCS_DIR = Path(os.getenv("DOCS_DIR", RAIZ / "datos"))          # PDF, TXT, MD e LOG
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", RAIZ / "chroma_db"))  # índice local (não versionar)

# --- Embeddings (multilíngue: pt/es/en) ---
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# --- Chunking (texto corrido; cada seção ou artigo vira 1 bloco) ---
CHUNK_SIZE = 1000             # caracteres
CHUNK_OVERLAP = 0             # sobreposição repete texto (e tokens)

# --- Busca híbrida ---
TOP_K = 4
SIM_MINIMA = 0.40             # similaridade mínima (0.30 deixava passar "política de férias")
LEX_MIN = 0.30                # cobertura mínima das palavras-chave (ponderada por raridade)
SIM_ALTA = 0.80               # acima disso aceita mesmo com baixa cobertura (paráfrases)
PESO_LEXICO = 0.5
MARGEN_RELATIVO = 0.30        # descarta blocos muito piores que o melhor
POOL_CANDIDATOS = 40

# --- Contexto enxuto ---
PRESUPUESTO_CONTEXTO = 900    # tokens estimados de contexto enviados ao Claude
ELIMINAR_ARTICULOS = False    # True = telegráfico (economiza pouco, lê pior)

# --- Claude ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
CLAUDE_MAX_TOKENS = 1000
TEMPERATURA = None            # ex.: 0 para respostas mais estáveis
DESACTIVAR_THINKING = True    # envia thinking={'type': 'disabled'}

# --- Prompt caching ---
CACHE_MODO = "auto"           # "auto" | "siempre" | "nunca"
CACHE_MIN_TOKENS = 1200

CHARS_POR_TOKEN = 2.5         # estimativa inicial; recalibrada com count_tokens na inicialização
