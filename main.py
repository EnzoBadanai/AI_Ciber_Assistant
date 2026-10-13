"""Interface de linha de comando.

Uso:
    python main.py              # sincroniza o índice com a pasta datos/ e abre o chat
    python main.py --reindexar  # recalcula todos os embeddings do zero
"""
import argparse

from src.rag import AssistenteRAG


def main():
    parser = argparse.ArgumentParser(description="Ciber Assistant: RAG de políticas e procedimentos de segurança")
    parser.add_argument("--reindexar", action="store_true", help="recalcula todo o índice")
    args = parser.parse_args()

    assistente = AssistenteRAG(reindexar=args.reindexar)
    modo = "filtrado"
    print("\nDigite sua pergunta. Comandos: /completo, /filtrado, sair\n")
    while True:
        pergunta = input(f"[{modo}] Pergunta: ").strip()
        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "salir"):
            break
        if pergunta in ("/completo", "/filtrado"):
            modo = pergunta[1:]
            print(f"Modo alterado para {modo}.")
            continue
        assistente.perguntar(pergunta, modo=modo)


if __name__ == "__main__":
    main()
