"""Mede tokens e economia: compara /completo e /filtrado para as mesmas perguntas (célula 25 do notebook).

Uso (na pasta do projeto, com o .venv ativo):
    python -m testes.medir              # 6 perguntas de exemplo
    python -m testes.medir --n 20       # primeiras 20 perguntas do conjunto de teste

Atenção: cada pergunta chama a API duas vezes (uma por modo), então gera custo real.
O resultado sai no terminal e em medicao_tokens.csv (abre no Excel).
"""
import argparse

import pandas as pd

from src import config
from src.rag import AssistenteRAG
from testes.perguntas_teste import PERGUNTAS_TESTE

PERGUNTAS_EXEMPLO = [
    "Olá, poderia me dizer quais são as bases legais para tratamento de dados?",
    "Você pode me explicar o que é phishing, por favor?",
    "Eu gostaria de saber quais são os direitos do titular de dados.",
    "Por favor, qual é o artigo 46?",
    "Oi! Quero saber quais cuidados tomar com a segurança de redes Wi-Fi.",
    "Qual a política de férias da empresa?",
]


def main():
    parser = argparse.ArgumentParser(description="Economia de tokens: /completo x /filtrado")
    parser.add_argument("--n", type=int, default=0, help="usa as primeiras N perguntas do conjunto de teste")
    args = parser.parse_args()

    perguntas = [p['pergunta'] for p in PERGUNTAS_TESTE[:args.n]] if args.n else PERGUNTAS_EXEMPLO
    assistente = AssistenteRAG()

    filas = []
    for i, p in enumerate(perguntas, 1):
        print(f"[{i}/{len(perguntas)}] {p[:60]}")
        c = assistente.perguntar(p, modo='completo', verbose=False)
        f = assistente.perguntar(p, modo='filtrado', verbose=False)
        ahorro = 100 * (1 - f['costo_in_eq'] / c['costo_in_eq']) if c['costo_in_eq'] else 0.0
        filas.append({
            'pergunta': p[:55],
            'rota_filtrado': f['ruta'],
            'entrada_completo': round(c['costo_in_eq']),
            'entrada_filtrado': round(f['costo_in_eq']),
            'economia_%': round(ahorro, 1),
            'saida_completo': c['tokens_out'],
            'saida_filtrado': f['tokens_out'],
            'cortada_filtrado': f['cortada'],
        })

    df = pd.DataFrame(filas)
    print('\n' + df.to_string(index=False))
    print(f"\nEconomia média no custo de entrada: {df['economia_%'].mean():.1f}%")
    print(f"Saída média: completo {df['saida_completo'].mean():.0f} | filtrado {df['saida_filtrado'].mean():.0f} tokens")
    caminho = config.RAIZ / 'medicao_tokens.csv'
    df.to_csv(caminho, index=False, encoding='utf-8-sig')
    print(f"\nTabela salva em: {caminho}")


if __name__ == '__main__':
    main()
