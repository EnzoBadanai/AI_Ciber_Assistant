"""Mede a busca nas 100 perguntas de teste (mesma lógica da célula 31 do notebook).

Uso (na pasta do projeto, com o .venv ativo):
    python -m testes.avaliar
"""
import re

import pandas as pd

from src import config
from src.pergunta import comprimir_pregunta
from src.rag import AssistenteRAG
from testes.perguntas_teste import PERGUNTAS_TESTE


def referencia_de(r):
    # referência a partir do rótulo da seção: "Art. 48" -> 48, "2.3 Phishing" -> 2.3
    s = r['seccion'] or ''
    m = re.match(r'^Art\.\s*(\d+)', s) or re.match(r'^(\d+(?:\.\d+)*)\s', s)
    return m.group(1) if m else ''


def acertou(recuperados, doc, esperado):
    for r in recuperados:
        if doc and not r['titulo'].startswith(doc):
            continue
        if referencia_de(r) in esperado:
            return True
    return False


def main():
    assistente = AssistenteRAG()
    recuperador = assistente.recuperador
    resultados = []
    for p in PERGUNTAS_TESTE:
        q = comprimir_pregunta(p['pergunta'])
        rec = recuperador.recuperar(q, config.TOP_K)
        if p['tipo'] == 'fora-do-escopo':
            ok = len(rec) == 0
        else:
            ok = acertou(rec, p['doc'], p['esperado'])
        obtido = [f"{r['titulo'][:12]} {referencia_de(r) or r['seccion'][:20]}" for r in rec] or ['(nada)']
        resultados.append({'id': p['id'], 'tipo': p['tipo'], 'ok': ok, 'pergunta': p['pergunta'],
                           'esperado': ', '.join(p['esperado']) or 'nada', 'obtido': ' | '.join(obtido)})

    df = pd.DataFrame(resultados)
    total_ok, total = int(df['ok'].sum()), len(df)
    print(f"Top-{config.TOP_K}: {total_ok}/{total} acertos ({100 * total_ok / total:.0f}%)\n")
    print(df.groupby('tipo')['ok'].agg(['sum', 'count']).rename(columns={'sum': 'acertos', 'count': 'total'}))
    falhas = df[~df['ok']]
    if len(falhas):
        print('\nFalhas:')
        for _, f in falhas.iterrows():
            print(f"#{f['id']} {f['pergunta']}\n    esperado: {f['esperado']} | obtido: {f['obtido']}")


if __name__ == '__main__':
    main()
