"""Orquestra o fluxo completo: pergunta -> busca -> contexto -> Claude (células 7 a 21 do notebook)."""
import os

import anthropic

from . import config
from .contexto import comprimir_en_topicos
from .indexer import abrir_colecao, carregar_modelo, indexar
from .ingest import ler_documentos, montar_registros
from .llm_claude import ClienteClaude
from .pergunta import comprimir_pregunta
from .retriever import Recuperador

NOTA_SEM_CONTEXTO = ('Nenhum trecho dos documentos passou nos filtros: '
                     'resposta do conhecimento geral do Claude, não do manual.')


class AssistenteRAG:
    def __init__(self, reindexar=False):
        chave = os.getenv('ANTHROPIC_API_KEY')
        if not chave:
            raise SystemExit('ANTHROPIC_API_KEY não encontrada. Preencha o arquivo .env (veja .env.example).')
        self.claude = ClienteClaude(anthropic.Anthropic(api_key=chave))
        self.modelo = carregar_modelo()
        self.colecao = abrir_colecao(reiniciar=reindexar)

        documentos = ler_documentos(config.DOCS_DIR)
        if documentos:
            config.CHARS_POR_TOKEN = self.claude.calibrar_tokens('\n\n'.join(t for _, t in documentos))
            print(f"Calibração: {config.CHARS_POR_TOKEN} caracteres por token")
            print(f"Documentos carregados: {len(documentos)}")
            for titulo, texto in documentos:
                print(f"  - {titulo}")
            r = indexar(self.colecao, self.modelo, montar_registros(documentos))
            print(f"Blocos: {r['blocos']} | novos: {r['novos']} | removidos: {r['removidos']} | "
                  f"total no índice: {r['total']}")
        else:
            print(f"[Aviso] Nenhum documento em {config.DOCS_DIR}. Coloque os PDFs nessa pasta.")
        if self.colecao.count() == 0:
            print('[Aviso] Índice vazio: as respostas sairão sem contexto dos documentos.')

        self.recuperador = Recuperador(self.colecao, self.modelo)
        self.recuperador.preparar_lexico()

    def perguntar(self, pergunta, modo='filtrado', top_k=config.TOP_K, verbose=True):
        if modo == 'filtrado':
            q = comprimir_pregunta(pergunta)
            rec = self.recuperador.recuperar(q, top_k)
            contexto = comprimir_en_topicos(rec, q, self.modelo) if rec else ''
        elif modo == 'completo':
            q = pergunta
            rec = self.recuperador.recuperar(q, top_k, hibrido=False)
            contexto = '\n\n'.join(r['texto'] for r in rec)
        else:
            raise ValueError('modo deve ser "filtrado" ou "completo"')

        ruta = 'contexto' if contexto else 'direta'
        nota = NOTA_SEM_CONTEXTO if (ruta == 'direta' and self.colecao.count() > 0) else ''
        if verbose:
            print(f"Rota: {ruta} | pergunta enviada: {q!r}")
            for r in rec:
                print(f"  - {r['categoria'] + ' › ' if r['categoria'] else ''}{r['seccion'] or r['titulo']} "
                      f"(sim={r['similitud']:.2f}, cobertura={r['cobertura']:.2f})")

        res = self.claude.gerar(q, contexto)
        if verbose:
            if contexto:
                print('\n--- CONTEXTO ENVIADO ---')
                print(contexto)
            print(f"\n--- RESPOSTA DO CLAUDE ({modo}) ---")
            if nota:
                print(f"[Nota] {nota}\n")
            print(res['texto'])
            print(f"\n--- Métricas --- prompt total={res['tokens_in']} | saída={res['tokens_out']} | "
                  f"cache escrito={res['cache_creation']} | cache lido={res['cache_read']} | "
                  f"custo de entrada equivalente={res['costo_in_eq']:.0f} | cache marcado={res['cache_usado']}")
            if 'thinking' in res['bloques']:
                print('[Aviso] A resposta tem bloco de raciocínio (thinking), que conta na saída: '
                      'ajuste CLAUDE_MAX_TOKENS ou DESACTIVAR_THINKING.')
            if res['cortada']:
                print('[Aviso] Resposta cortada por max_tokens: suba CLAUDE_MAX_TOKENS ou peça uma resposta mais curta.')
        trechos = [{'documento': r['titulo'], 'categoria': r['categoria'], 'secao': r['seccion'],
                    'similaridade': round(r['similitud'], 3), 'cobertura': round(r['cobertura'], 2)} for r in rec]
        return {**res, 'modo': modo, 'ruta': ruta, 'pregunta_enviada': q, 'nota': nota, 'trechos': trechos}
