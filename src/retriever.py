"""Busca híbrida: embedding + cobertura de palavras-chave + referência direta (célula 13 do notebook)."""
import math
import re
import unicodedata
from collections import Counter

from . import config

sin_acentos = lambda s: ''.join(ch for ch in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(ch) != 'Mn')


STOP = set(sin_acentos(w) for w in """a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sobre que e é ou se ao aos
qual quais como são ser foi tem ter mais meu minha seu sua isso esse essa este esta você voce me te vc pode poderia fazer faz
preciso queria quero gostaria saber diga olá oi the of and to in is are for on with""".split())


RE_REFERENCIA = re.compile(r'\b(?:artigo|art\.?|receita|seção|secao|item|n[º°o]\.?|número|numero|#)\s*(?:n[úu]mero|n[º°o]\.?|#)?\s*(\d{1,3}(?:\.\d{1,2}){0,2})\b', re.I)


QUIERE_LISTA = re.compile(r'\b(quais|lista|liste|listar|todas|todos|quantas|quantos)\b', re.I)


IDF_TECHO = 3.5


def terminos(texto):
    texto = sin_acentos(texto).replace('wi-fi', 'wifi').replace('wi fi', 'wifi')   # 'Wi-Fi' não some por ter 2 letras
    palavras = re.findall(r'[a-z0-9]+', texto)
    return {w.rstrip('s')[:6] for w in palavras if len(w) > 2 and w not in STOP}


class Recuperador:
    """Mesma lógica da célula 13: referência direta, depois embedding + palavras-chave, com dedupe por seção."""

    def __init__(self, colecao, modelo):
        self.colecao = colecao
        self.modelo = modelo
        self.doc_lex = {}
        self.idf = {}
        self.idf_desconocido = 0.0

    def preparar_lexico(self):
        datos = self.colecao.get(include=['documents', 'metadatas'])
        self.doc_lex = {id_: terminos(f"{m.get('seccion', '')} {m.get('categoria', '')} {d}")
                        for id_, d, m in zip(datos['ids'], datos['documents'], datos['metadatas'])}
        N = max(1, len(self.doc_lex))
        df = Counter(t for s in self.doc_lex.values() for t in s)
        self.idf = {t: math.log((N + 1) / (c + 0.5)) for t, c in df.items()}
        self.idf_desconocido = math.log((N + 1) / 0.5)

    def cobertura(self, q_terms, id_):
        if not q_terms:
            return 1.0
        pesos = {t: min(self.idf.get(t, self.idf_desconocido), IDF_TECHO) for t in q_terms}
        total = sum(pesos.values())
        if total < 0.5:                       # só palavras genéricas, presentes em quase todos os blocos
            return 1.0
        return sum(w for t, w in pesos.items() if t in self.doc_lex.get(id_, ())) / total

    @staticmethod
    def _rec(id_, doc, meta, sim, cov=0.0, score=0.0):
        return {'id': id_, 'texto': doc, 'titulo': meta['titulo'], 'seccion': meta.get('seccion', ''),
                'categoria': meta.get('categoria', ''), 'orden': meta.get('orden', 0),
                'tipo': meta.get('tipo', 'texto'), 'similitud': sim, 'cobertura': cov, 'score': score}

    def puntuar(self, pregunta):
        n = min(config.POOL_CANDIDATOS, self.colecao.count())
        res = self.colecao.query(query_embeddings=self.modelo.encode([pregunta], normalize_embeddings=True).tolist(),
                                 n_results=n, include=['documents', 'metadatas', 'distances'])
        q_terms, lista = terminos(pregunta), bool(QUIERE_LISTA.search(pregunta))
        cands = []
        for id_, d, m, dist in zip(res['ids'][0], res['documents'][0], res['metadatas'][0], res['distances'][0]):
            sim, cov = 1 - dist, self.cobertura(q_terms, id_)
            bonus = 0.25 if (lista and m.get('tipo') == 'indice') else 0.0
            cands.append(self._rec(id_, d, m, sim, cov, sim + config.PESO_LEXICO * cov + bonus))
        return sorted(cands, key=lambda c: c['score'], reverse=True)

    def recuperar(self, pregunta, top_k=config.TOP_K, hibrido=True):
        if self.colecao.count() == 0:
            return []
        if not hibrido:                       # como no exemplo simples: sempre devolve os top-k por embedding
            res = self.colecao.query(query_embeddings=self.modelo.encode([pregunta], normalize_embeddings=True).tolist(),
                                     n_results=min(top_k, self.colecao.count()),
                                     include=['documents', 'metadatas', 'distances'])
            return [self._rec(i, d, m, 1 - dist) for i, d, m, dist in
                    zip(res['ids'][0], res['documents'][0], res['metadatas'][0], res['distances'][0])]

        m = RE_REFERENCIA.search(pregunta)    # "artigo 48", "seção 2.3": consulta direta pelos metadados
        if m:
            datos = self.colecao.get(where={'$and': [{'referencia': m.group(1)}, {'tipo': 'seccion'}]},
                                     include=['documents', 'metadatas'])
            if datos['ids']:
                return [self._rec(i, d, md_, 1.0, 1.0, 2.0)
                        for i, d, md_ in zip(datos['ids'], datos['documents'], datos['metadatas'])][:top_k]

        cands = self.puntuar(pregunta)
        lista = bool(QUIERE_LISTA.search(pregunta))
        ok = [c for c in cands if (c['similitud'] >= config.SIM_MINIMA and c['cobertura'] >= config.LEX_MIN)
              or c['similitud'] >= config.SIM_ALTA
              or (lista and c['tipo'] == 'indice' and c['cobertura'] >= config.LEX_MIN
                  and c['similitud'] >= config.SIM_MINIMA / 2)]
        if not ok:
            return []
        vistos, unicos = set(), []
        for c in ok:                          # no máximo um bloco por seção, na ordem de relevância
            chave = (c['titulo'], c['seccion']) if c['seccion'] else c['id']
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(c)
        return [c for c in unicos if c['score'] >= unicos[0]['score'] - config.MARGEN_RELATIVO][:top_k]
