# Ciber Assistant: RAG de políticas e procedimentos de segurança

Assistente que responde perguntas com base na **Cartilha de Segurança para Internet** (CERT.br/NIC.br, v4.0) e na **Lei Geral de Proteção de Dados** (Lei 13.709/2018). Cada resposta cita a seção ou o artigo de onde veio a informação.

O projeto usa:
- **ChromaDB** para o índice local dos documentos;
- **embeddings multilíngues** (`paraphrase-multilingual-MiniLM-L12-v2`) para a busca por significado;
- **busca híbrida**, que combina embeddings com palavras-chave ponderadas por raridade e busca direta por "artigo N" ou "seção N.N";
- **Claude** (Anthropic) para gerar a resposta, com prompt caching e medição de tokens;
- **FastAPI** para expor o assistente como API e **Streamlit** para a interface de chat.

Os parâmetros, a lógica de busca e os testes são os mesmos do notebook `notebook/Assistant_RAG_Seguranca_v3_corrigido.ipynb`, que serve de referência.

## Estrutura

```
AI_Assistent-Ciber/
├── main.py                    # chat no terminal
├── api/
│   └── main.py                # API FastAPI: /status e /perguntar
├── app/
│   └── interface.py           # tela de chat em Streamlit (consome a API)
├── src/
│   ├── config.py              # todos os parâmetros ajustáveis
│   ├── ingest.py              # leitura do PDF, correção de acentos, divisão por seção/artigo
│   ├── indexer.py             # embeddings e gravação no ChromaDB
│   ├── pergunta.py            # limpeza da pergunta (saudações, cortesias)
│   ├── retriever.py           # busca híbrida: embedding + palavras-chave + referência direta
│   ├── contexto.py            # monta o contexto enxuto dentro do orçamento de tokens
│   ├── llm_claude.py          # chamada ao Claude com prompt caching e métricas
│   └── rag.py                 # orquestra o fluxo completo
├── testes/
│   ├── perguntas_teste.py     # 100 perguntas com a seção esperada
│   ├── avaliar.py             # mede acertos por tipo de pergunta
│   └── medir.py               # compara tokens e economia entre /completo e /filtrado
├── notebook/
│   └── Assistant_RAG_Seguranca_v3_corrigido.ipynb   # versão para Colab/Jupyter
├── datos/                     # PDFs de origem (não versionar; ver "Documentos")
├── chroma_db/                 # índice gerado (não versionar)
├── requirements.txt
├── .env.example               # modelo do arquivo .env (copie e preencha)
└── .gitignore
```

## Instalação (Windows, VS Code)

Abra a pasta no VS Code e, no terminal, crie o ambiente virtual:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Na primeira execução, o modelo de embeddings (~470 MB) é baixado automaticamente.

Crie `.env` e preencha a chave:

```
ANTHROPIC_API_KEY=sua-chave
```

## Documentos

Coloque na pasta `datos/`:
- `Lei_geral_protecao_dados_pessoais.pdf`
- `cartilha-seguranca-internet.pdf`

Os PDFs não estão no repositório. Baixe a Cartilha no site do CERT.br/NIC.br e a LGPD no site da Presidência da República.

## Como usar

**Índice e chat no terminal**

```powershell
python main.py --reindexar   # cria ou atualiza o índice; use depois de trocar os PDFs
python main.py               # chat no terminal
```

No chat, `/completo` e `/filtrado` alternam o modo de busca, e `sair` encerra.

**API + tela (dois terminais)**

```powershell
uvicorn api.main:app --reload        # terminal 1: API em http://127.0.0.1:8000 (documentação em /docs)
streamlit run app/interface.py       # terminal 2: tela em http://localhost:8501
```

A API precisa estar no ar antes da tela; a barra lateral mostra se ela está online. Se a API estiver em outro endereço, defina `CIBER_API_URL`.

A tela mostra a resposta, a nota quando ela sai sem contexto dos documentos, a tabela com os trechos usados e as métricas de tokens da pergunta.

**Testes e medição**

```powershell
python -m testes.avaliar            # mede a busca nas 100 perguntas (acertos por tipo e falhas)
python -m testes.medir              # tokens e economia: 6 perguntas de exemplo
python -m testes.medir --n 20       # tokens e economia: primeiras 20 perguntas do teste
```

`testes.medir` chama a API duas vezes por pergunta (um modo por vez), então gera custo real. Ele salva a tabela em `medicao_tokens.csv`.

## Como funciona

1. **Pergunta**: saudações e cortesias são removidas. "Oi, poderia me dizer o que é phishing?" vira "O que é phishing?".
2. **Busca**:
   - Se a pergunta cita um artigo ou seção ("artigo 48", "seção 2.3"), o bloco correspondente é buscado direto.
   - Caso contrário, combina a similaridade de embeddings com a cobertura de palavras-chave.
   - Se nenhum bloco passa nos filtros, a pergunta vai ao Claude sem contexto, e a resposta traz a nota de que não veio dos documentos.
3. **Contexto**: seções inteiras, com rótulo `[Documento › Capítulo › Seção]`, dentro de `PRESUPUESTO_CONTEXTO`.
4. **Claude**: responde em português, cita a seção e diz quando a resposta não consta nos trechos.

## Resultados

**Qualidade da busca** (100 perguntas, Top-4, parâmetros atuais):

| Tipo | Acertos |
|---|---|
| fora do escopo | 6/6 |
| referência (artigo/seção) | 4/4 |
| multi-documento | 1/1 |
| paráfrase | 74/81 |
| ruído | 7/8 |
| **total** | **92/100 (92%)** |

Falhas conhecidas:
- **Artigos longos da LGPD com muitos incisos** (arts. 1, 3, 5, 6 e 7): o bloco com o conceito fica diluído no ranqueamento.
- **Seções 9.x da Cartilha** (criptografia): "criptografia" e "cuidados" aparecem em várias seções, e a 9.1 perde para seções sobre senhas.
- **Pergunta sobre a seção 2.4**: o resultado é a subseção 2.4.1. O teste conta só o número exato, então esse caso conta como erro, mas a resposta é relevante.

**Economia de tokens** (medição com `/completo` x `/filtrado`):
- Entrada: cerca de **44% menos** tokens no total (9.893 → 5.552).
- Saída: cerca de **30% menos** tokens (3.343 → 2.336).
- Nas perguntas que usaram os documentos, a economia média de entrada é de **39,7%**.

## Calibração

Os parâmetros ficam em `src/config.py`:
- `SIM_MINIMA` e `LEX_MIN`: se a busca devolve pouco contexto para perguntas que deveriam ter resposta, baixe; se devolve trechos irrelevantes, suba.
- `TOP_K` e `PRESUPUESTO_CONTEXTO`: quantidade de blocos e tamanho máximo do contexto.
- `DESACTIVAR_THINKING`: deixe `True` para o modelo não gastar saída com raciocínio oculto.

## Cuidados

- **Licença da Cartilha**: CC BY-NC-ND 3.0 Brasil. Permite uso não comercial com atribuição, mas **proíbe obras derivadas**. Por isso, os PDFs e as saídas do notebook com trechos da Cartilha não devem ser publicados.
- **Chave da API**: fica só no `.env`, que está no `.gitignore`. A chave nunca vai para a tela.
- **Acesso à API**: a API não tem autenticação. Ela escuta só em `127.0.0.1`, então serve para uso no seu computador. Antes de publicar, adicione uma forma de autenticação.
- **Versões dos textos**: a Cartilha é a versão 4.0 (2012), e a LGPD tem edição atualizada até junho de 2024. Confira a versão vigente antes de usar as respostas em decisões reais.
- **Consumo**: `testes.avaliar` e `testes.medir` chamam a API. Use com cuidado, porque gastam créditos.

## Próximos passos

- Diagnosticar a divisão dos artigos longos da LGPD para subir o acerto acima de 92%.
- Fazer a API responder com erro HTTP quando a Anthropic falhar, em vez de devolver o texto de erro como resposta.
- Adicionar autenticação à API antes de qualquer publicação.
- Acrescentar documentos de políticas internas (DOCX ou PDF).
