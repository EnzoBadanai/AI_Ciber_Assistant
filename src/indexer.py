"""Embeddings multilíngues e gravação no ChromaDB (células 7 e 11 do notebook)."""
import hashlib
import re

import chromadb
from sentence_transformers import SentenceTransformer

from . import config


def nome_colecao():
    # o modelo entra no nome: nunca mistura embeddings de dimensões diferentes
    return 'documentos_pdf_' + re.sub(r'[^a-zA-Z0-9]+', '_', config.EMBED_MODEL).strip('_')


def carregar_modelo():
    return SentenceTransformer(config.EMBED_MODEL)


def abrir_colecao(reiniciar=False):
    cliente = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    if reiniciar:
        try:
            cliente.delete_collection(nome_colecao())
        except Exception:
            pass
    return cliente.get_or_create_collection(name=nome_colecao(), metadata={'hnsw:space': 'cosine'})


def indexar(colecao, modelo, registros):
    # o id é um hash do conteúdo: blocos iguais não são recalculados; os que saíram são removidos
    ids = [hashlib.sha1(f"{r['titulo']}|{r['seccion']}|{r['texto']}".encode()).hexdigest()[:20] for r in registros]
    existentes = set(colecao.get()['ids'])
    obsoletos = list(existentes - set(ids))
    if obsoletos:
        colecao.delete(ids=obsoletos)
    nuevos = [i for i, id_ in enumerate(ids) if id_ not in existentes]
    if nuevos:
        colecao.upsert(
            ids=[ids[i] for i in nuevos],
            embeddings=modelo.encode([registros[i]['texto'] for i in nuevos], normalize_embeddings=True).tolist(),
            documents=[registros[i]['texto'] for i in nuevos],
            metadatas=[{k: registros[i][k] for k in ('titulo', 'seccion', 'categoria', 'referencia', 'tipo', 'orden')}
                       for i in nuevos],
        )
    return {'blocos': len(registros), 'novos': len(nuevos), 'removidos': len(obsoletos),
            'total': colecao.count()}
