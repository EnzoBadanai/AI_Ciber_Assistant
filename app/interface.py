"""Interface Streamlit do Ciber Assistant. Conversa com a API FastAPI.

Rodar (com a API ligada e o .venv ativo, em outro terminal):
    streamlit run app/interface.py
"""
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv('CIBER_API_URL', 'http://127.0.0.1:8000')

st.set_page_config(page_title='Ciber Assistant', page_icon='🛡️', layout='wide')


def chamar_api(pergunta, modo):
    r = requests.post(f'{API}/perguntar', json={'pergunta': pergunta, 'modo': modo}, timeout=180)
    r.raise_for_status()
    return r.json()


def status_api():
    try:
        r = requests.get(f'{API}/status', timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def mostrar_detalhes(d):
    if d.get('nota'):
        st.info(d['nota'])
    if d['trechos']:
        with st.expander(f"Trechos usados ({len(d['trechos'])})"):
            st.dataframe(pd.DataFrame(d['trechos']), hide_index=True)
    m = d['metricas']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Tokens de entrada', m['tokens_entrada'])
    c2.metric('Tokens de saída', m['tokens_saida'])
    c3.metric('Custo de entrada equivalente', round(m['custo_entrada_equivalente']))
    c4.metric('Resposta', 'com contexto' if d['rota'] == 'contexto' else 'sem contexto')
    st.caption(f"Modo: {d['modo']} · pergunta enviada: {d['pergunta_enviada']} · "
               f"cache {'usado' if m['cache_usado'] else 'não usado'}")


if 'historico' not in st.session_state:
    st.session_state.historico = []

with st.sidebar:
    st.title('Ciber Assistant')
    modo = st.radio('Modo de busca', ['filtrado', 'completo'],
                    help='filtrado: busca com filtros e contexto enxuto. completo: top-k por embedding, sem filtros.')
    s = status_api()
    if s:
        st.success(f"API online · {s['blocos_no_indice']} blocos no índice")
    else:
        st.error(f'API offline em {API}. Rode: uvicorn api.main:app --reload')
    if st.button('Limpar conversa'):
        st.session_state.historico = []
        st.rerun()

st.header('Pergunte sobre a Cartilha de Segurança e a LGPD')

for item in st.session_state.historico:
    with st.chat_message(item['papel']):
        st.markdown(item['texto'])
        if item['papel'] == 'assistant':
            mostrar_detalhes(item['dados'])

pergunta = st.chat_input('Ex.: Como criar uma senha forte?')
if pergunta:
    st.session_state.historico.append({'papel': 'user', 'texto': pergunta})
    with st.chat_message('user'):
        st.markdown(pergunta)
    with st.chat_message('assistant'):
        with st.spinner('Consultando os documentos...'):
            try:
                dados = chamar_api(pergunta, modo)
                st.markdown(dados['resposta'])
                mostrar_detalhes(dados)
                st.session_state.historico.append({'papel': 'assistant', 'texto': dados['resposta'], 'dados': dados})
            except requests.RequestException as e:
                st.error(f'Não consegui falar com a API: {e}')
