"""Contexto enxuto dentro do orçamento de tokens (célula 17 do notebook)."""
import re

from . import config

ELIMINAR_ARTICULOS = config.ELIMINAR_ARTICULOS


def tokens_aprox(texto):
    # CHARS_POR_TOKEN é calibrado com a API na inicialização (ver llm_claude.py)
    return max(1, int(len(texto) / config.CHARS_POR_TOKEN))


MULETILLAS = [
    r'al[ée]m disso', r'ademais', r'por outro lado', r'em outras palavras', r'em resumo', r'basicamente', r'de modo geral',
    r'vale (a pena )?(destacar|ressaltar|mencionar|lembrar) que', r'é importante (notar|destacar|ressaltar|lembrar) que',
    r'cabe (destacar|ressaltar) que', r'(observe|note) que', r'como (mencionado|dito) (anteriormente|acima)',
    r'además', r'por otro lado', r'en otras palabras', r'en resumen', r'básicamente', r'en general',
    r'cabe (destacar|señalar) que', r'es importante (notar|destacar|señalar|recordar) que',
    r'moreover', r'furthermore', r'in addition', r'in other words', r'basically', r'it is important to note that',
]


RE_MULETILLAS = re.compile(r'^(?:' + '|'.join(MULETILLAS) + r')\b[,:]?\s*', re.I)


RE_ARTICULOS = re.compile(r'\b(o|os|as|um|uma|uns|umas|el|los|las|un|una|unos|unas|the|an)\b\s*', re.I)


def limpiar_linea(linea):
    linea = re.sub(r'^\s*[•*]\s*', '- ', linea.strip())
    if not re.match(r'^(-|\d+[.)])\s', linea):                   # muletas só em linhas de prosa
        linea = RE_MULETILLAS.sub('', linea).strip()
        linea = linea[:1].upper() + linea[1:]
    if ELIMINAR_ARTICULOS:
        linea = RE_ARTICULOS.sub('', linea)
    return re.sub(r'\s+', ' ', linea).strip()


def etiqueta(r):
    return '[' + ' › '.join(x for x in (r['titulo'], r.get('categoria', ''), r.get('seccion', '')) if x) + ']'


def comprimir_secciones(chunks_rec, presupuesto):
    # Seções inteiras, com rótulo; duplicatas curtas só dentro da mesma seção, longas em todo o contexto.
    largas_vistas, bloques = set(), []
    for r in chunks_rec:
        vistas, lineas = set(), []
        for l in r['texto'].split('\n'):
            l = limpiar_linea(l)
            clave = re.sub(r'\W+', ' ', l).strip().lower()
            if not l or (len(clave) < 60 and clave in vistas) or (len(clave) >= 60 and clave in largas_vistas):
                continue
            (largas_vistas if len(clave) >= 60 else vistas).add(clave)
            lineas.append(l)
        texto = etiqueta(r) + '\n' + '\n'.join(lineas)
        bloques.append((texto, tokens_aprox(texto)))
    elegidos, usado = [], 0
    for texto, costo in bloques:                                # já vêm por relevância
        if not elegidos or usado + costo <= presupuesto:
            elegidos.append(texto)
            usado += costo
    return '\n\n'.join(elegidos)


def dividir_frases(texto):
    frases = []
    for linea in texto.split('\n'):
        linea = re.sub(r'^\s*(#{1,6}|[-*•]|\d+[.)])\s*', '', linea).strip()
        if not linea:
            continue
        partes = re.split(r'(?<=[.!?;])\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇÑ¿¡"“(\d])', linea)
        frases += [p.strip() for p in partes if len(p.strip()) > 2]
    return frases


def comprimir_frases(chunks_rec, pregunta, presupuesto, modelo):
    # Texto corrido: frases limpas, sem duplicatas; se não couber, as mais parecidas com a pergunta.
    rango_doc, items, vistas = {}, [], set()
    for r in chunks_rec:
        rango_doc.setdefault(r['titulo'], len(rango_doc))
        for i, f in enumerate(dividir_frases(r['texto'])):
            f = RE_MULETILLAS.sub('', f).strip()
            f = f[:1].upper() + f[1:]
            clave = re.sub(r'\W+', ' ', f).strip().lower()
            if not f or clave in vistas:
                continue
            vistas.add(clave)
            items.append({'titulo': r['titulo'], 'orden': r['orden'], 'i': i, 'frase': f})
    costo = lambda it: tokens_aprox(it['frase']) + 2
    if sum(costo(it) for it in items) > presupuesto:
        vq = modelo.encode([pregunta], normalize_embeddings=True)[0]
        vf = modelo.encode([it['frase'] for it in items], normalize_embeddings=True)
        for it, s in zip(items, vf @ vq):
            it['sim'] = float(s)
        usado, elegidos = 0, []
        for it in sorted(items, key=lambda x: x['sim'], reverse=True):
            if usado + costo(it) <= presupuesto:
                elegidos.append(it)
                usado += costo(it)
        items = elegidos
    items.sort(key=lambda it: (rango_doc[it['titulo']], it['orden'], it['i']))
    salida, actual = [], None
    for it in items:
        if it['titulo'] != actual:
            salida.append(f"[{it['titulo']}]")
            actual = it['titulo']
        salida.append(f"- {it['frase']}")
    return '\n'.join(salida)


def comprimir_en_topicos(chunks_rec, pregunta, modelo, presupuesto=config.PRESUPUESTO_CONTEXTO):
    if not chunks_rec:
        return ''
    if all(r.get('seccion') for r in chunks_rec):
        return comprimir_secciones(chunks_rec, presupuesto)
    return comprimir_frases(chunks_rec, pregunta, presupuesto, modelo)
