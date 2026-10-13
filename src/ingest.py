"""Leitura, limpeza e divisão dos documentos (células 9 e 11 do notebook).

Cada seção da Cartilha ou artigo da LGPD vira um bloco. Texto sem numeração
cai no divisor de texto corrido.
"""
import glob
import os
import re
import unicodedata
from collections import Counter

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config

CHUNK_SIZE = config.CHUNK_SIZE
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
    keep_separator='end',
)


MODIF_DEPOIS = {'\u02dc': '\u0303', '\u02c6': '\u0302', '\u00b4': '\u0301', '`': '\u0300'}


def corrigir_acentos(texto):
    # a Cartilha grava cedilha e til como marcas separadas (c¸ ˜ao): junta cada marca à letra certa
    texto = texto.replace('\u0131', 'i')
    texto = re.sub(r'(\S)\u00b8', lambda m: unicodedata.normalize('NFC', m.group(1) + '\u0327'), texto)
    texto = re.sub(r'([\u02dc\u02c6\u00b4`])([A-Za-z])',
                   lambda m: unicodedata.normalize('NFC', m.group(2) + MODIF_DEPOIS[m.group(1)]), texto)
    return unicodedata.normalize('NFKC', texto)


def quitar_encabezados_pdf(paginas):
    # remove linhas de borda (2 primeiras/2 últimas) que se repetem em >= metade das páginas
    if len(paginas) < 3:
        return paginas
    mascara = lambda l: re.sub(r'\d+', '#', l.strip())

    def indices_borde(p):
        ls = p.split('\n')
        idx = [i for i, l in enumerate(ls) if l.strip()]
        return set(idx[:2] + idx[-2:]) if len(idx) >= 8 else set()

    cuenta = Counter()
    for p in paginas:
        ls = p.split('\n')
        cuenta.update({mascara(ls[i]) for i in indices_borde(p)})
    repetidas = {l for l, c in cuenta.items() if c >= max(2, len(paginas) // 2)}

    salida = []
    for p in paginas:
        ls, bordes = p.split('\n'), indices_borde(p)
        salida.append('\n'.join(l for i, l in enumerate(ls) if not (i in bordes and mascara(l) in repetidas)))
    return salida


def limpiar(texto):
    texto = texto.replace('\r\n', '\n')
    texto = re.sub(r'</?(?:b|i|u|strong|em|br|p|span|div|font|sup|sub)\b[^>]*>', '', texto, flags=re.I)   # tags HTML de formatação
    texto = re.sub(r'(?im)^[^\n]{0,80}[•|–—-]\s*p[áa]g(?:ina)?\.?\s*\d+\s*$', '', texto)              # "Título • Página 3"
    texto = re.sub(r'(\w)-\n(\w)', r'\1\2', texto)                                   # hifenização de PDF
    texto = re.sub(r'[A-Za-z0-9+/=]{200,}', '[blob-removido]', texto)                # base64 e similares
    texto = re.sub(r'(?im)^\s*(p[áa]g(ina)?\.?|page)?\s*\d+(\s*(/|de|of)\s*\d+)?\s*$', '', texto)  # nº de página
    texto = re.sub(r'(?m)^\s*([-_=*]{3,}|\.{4,})\s*$', '', texto)                     # linhas decorativas
    texto = re.sub(r'(?<![.!?:;\n])\n(?=[a-zà-ÿ])', ' ', texto)                       # junta quebra "dura" de PDF

    # colapsa linhas consecutivas idênticas (logs repetitivos)
    lineas, previa, rep = [], None, 0
    for l in texto.split('\n'):
        if l.strip() and l == previa:
            rep += 1
            continue
        if rep:
            lineas[-1] += f'  [repetida {rep + 1}x]'
            rep = 0
        lineas.append(l)
        previa = l
    if rep:
        lineas[-1] += f'  [repetida {rep + 1}x]'
    texto = '\n'.join(lineas)

    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def extraer_texto(ruta):
    # PDF: página a página (como no exemplo) já sem cabeçalhos/rodapés repetidos; demais formatos: texto puro
    if ruta.lower().endswith('.pdf'):
        with pymupdf.open(ruta) as pdf:
            paginas = [p.get_text() for p in pdf]
        return '\n\n'.join(quitar_encabezados_pdf(paginas))
    with open(ruta, encoding='utf-8', errors='replace') as f:
        return f.read()


RE_ART = re.compile(r'^Art\.\s*(\d{1,3})\s*(?:[º°o]\b)?')


RE_SECAO = re.compile(r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([^\n.]{3,80}?)\s*$')


RE_NUMERO_SOZINHO = re.compile(r'^\d{1,2}(?:\.\d{1,2}){0,2}$')


RE_CAPITULO = re.compile(r'^CAP[ÍI]TULO\s+([IVXLC]+)\b.*$', re.I)


def titulo_valido(t):
    # título curto, sem ponto (descarta sumário "...... 12" e frases de referência)
    return 3 <= len(t) <= 80 and '.' not in t and not t[0].isdigit()


def sequencia_crescente(cands):
    # maior subsequência com números crescentes: descarta referências fora de ordem
    n = len(cands)
    if n == 0:
        return []
    tam, ant = [1] * n, [-1] * n
    for j in range(n):
        for i in range(j):
            if cands[i][1] < cands[j][1] and tam[i] + 1 > tam[j]:
                tam[j], ant[j] = tam[i] + 1, i
    fim = max(range(n), key=lambda k: tam[k])
    saida = []
    while fim != -1:
        saida.append(cands[fim])
        fim = ant[fim]
    return saida[::-1]


def achar_secoes(linhas):
    # devolve [(linha, chave, titulo, categoria)] ou None se houver menos de 3 seções
    cands, categoria, i = [], '', 0
    while i < len(linhas):
        s = linhas[i].strip()
        i += 1
        if RE_CAPITULO.match(s):
            categoria = s
            continue
        m_art = RE_ART.match(s)
        if m_art:
            chave, titulo, inicio = (int(m_art.group(1)),), f"Art. {m_art.group(1)}", i - 1
        elif RE_NUMERO_SOZINHO.match(s):
            prox = next((x.strip() for x in linhas[i:i + 2] if x.strip()), '')
            if not titulo_valido(prox):
                continue
            chave, titulo, inicio = tuple(int(x) for x in s.split('.')), f"{s} {prox}", i - 1
        else:
            m_sec = RE_SECAO.match(s)
            if not m_sec or not titulo_valido(m_sec.group(2).strip()):
                continue
            chave = tuple(int(x) for x in m_sec.group(1).split('.'))
            titulo, inicio = f"{m_sec.group(1)} {m_sec.group(2).strip()}", i - 1
        cands.append((inicio, chave, titulo, categoria))
    marcas = sequencia_crescente(cands)
    return marcas if len(marcas) >= 3 else None


def dividir_documento(texto, nome):
    linhas = texto.split('\n')
    marcas = achar_secoes(linhas)
    registros = []
    if marcas is None:                                   # sem seções: texto corrido
        for orden, bloque in enumerate(text_splitter.split_text(texto)):
            registros.append({'titulo': nome, 'seccion': '', 'categoria': '', 'referencia': '', 'tipo': 'texto',
                              'orden': orden, 'texto': bloque})
        return registros

    orden = 0
    prefacio = '\n'.join(linhas[:marcas[0][0]]).strip()
    for bloque in text_splitter.split_text(prefacio) if prefacio else []:
        registros.append({'titulo': nome, 'seccion': 'Apresentação', 'categoria': '', 'referencia': '', 'tipo': 'texto',
                          'orden': orden, 'texto': bloque})
        orden += 1
    limites = [m[0] for m in marcas] + [len(linhas)]
    for k, (i, chave, titulo, categoria) in enumerate(marcas):
        corpo = '\n'.join(linhas[i:limites[k + 1]]).strip()
        ref = '.'.join(str(x) for x in chave)
        partes = [corpo] if len(corpo) <= CHUNK_SIZE * 2.5 else text_splitter.split_text(corpo)
        for j, parte in enumerate(partes):
            registros.append({'titulo': nome, 'seccion': titulo, 'categoria': categoria, 'referencia': ref,
                              'tipo': 'seccion', 'orden': orden,
                              'texto': parte if j == 0 else f"{titulo} (cont.)\n{parte}"})
            orden += 1
    return registros


def ler_documentos(pasta):
    """Devolve [(titulo, texto)] de todos os PDF, TXT, MD e LOG da pasta, já limpos."""
    archivos = sorted(
        f for ext in ('pdf', 'txt', 'md', 'log')
        for f in glob.glob(os.path.join(str(pasta), f'*.{ext}'))
    )
    return [(os.path.splitext(os.path.basename(r))[0], limpiar(corrigir_acentos(extraer_texto(r))))
            for r in archivos]


def montar_registros(documentos):
    registros = []
    for titulo, texto in documentos:
        registros += dividir_documento(texto, titulo)
    return registros
