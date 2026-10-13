"""API FastAPI do Ciber Assistant. Carrega o assistente uma vez e atende as perguntas.

Rodar (na pasta do projeto, com o .venv ativo):
    uvicorn api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs
"""
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src import config
from src.rag import AssistenteRAG

estado = {}
trava = threading.Lock()          # uma pergunta por vez: o índice e o modelo são compartilhados


@asynccontextmanager
async def lifespan(app):
    estado['assistente'] = AssistenteRAG()
    yield
    estado.clear()


app = FastAPI(title='Ciber Assistant', version='1.0', lifespan=lifespan)


class Pergunta(BaseModel):
    pergunta: str = Field(..., min_length=2, max_length=1000)
    modo: Literal['filtrado', 'completo'] = 'filtrado'


class Trecho(BaseModel):
    documento: str
    categoria: str
    secao: str
    similaridade: float
    cobertura: float


class Metricas(BaseModel):
    tokens_entrada: int
    tokens_saida: int
    cache_escrito: int
    cache_lido: int
    custo_entrada_equivalente: float
    cache_usado: bool


class Resposta(BaseModel):
    resposta: str
    modo: str
    rota: str
    pergunta_enviada: str
    nota: str
    trechos: list[Trecho]
    metricas: Metricas


def _assistente():
    a = estado.get('assistente')
    if a is None:
        raise HTTPException(status_code=503, detail='Assistente ainda não carregado')
    return a


@app.get('/status')
def status():
    a = _assistente()
    return {'blocos_no_indice': a.colecao.count(), 'modelo_claude': config.CLAUDE_MODEL,
            'top_k': config.TOP_K, 'sim_minima': config.SIM_MINIMA, 'lex_min': config.LEX_MIN}


@app.post('/perguntar', response_model=Resposta)
def perguntar(body: Pergunta):
    a = _assistente()
    with trava:
        r = a.perguntar(body.pergunta, modo=body.modo, verbose=False)
    return Resposta(
        resposta=r['texto'],
        modo=r['modo'],
        rota=r['ruta'],
        pergunta_enviada=r['pregunta_enviada'],
        nota=r['nota'],
        trechos=[Trecho(**t) for t in r['trechos']],
        metricas=Metricas(
            tokens_entrada=r['tokens_in'],
            tokens_saida=r['tokens_out'],
            cache_escrito=r['cache_creation'],
            cache_lido=r['cache_read'],
            custo_entrada_equivalente=round(r['costo_in_eq'], 1),
            cache_usado=r['cache_usado'],
        ),
    )
