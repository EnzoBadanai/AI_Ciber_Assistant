"""Limpeza da pergunta antes da busca: saudações e cortesias saem, o sentido fica (célula 16)."""
import re


RELLENO_INICIO = [
    r'^\s*(olá|ola|oi|bom dia|boa tarde|boa noite)\b[,!.\s]*',                                    # saudações
    r'^\s*((você|voce|vc)\s+)?(poderia|poderias|pode|podes)\s+(me\s+)?'
    r'(dizer|explicar|informar|ajudar(?:\s+a)?|mostrar|indicar)\s+',                              # "poderia me dizer..."
    r'^\s*((você|voce|vc)\s+)?(consegue|conseguiria|conseguem)\s+(me\s+)?'
    r'(dizer|explicar|informar|mostrar|ajudar(?:\s+a)?|encontrar)\s+',                            # "você consegue me mostrar..."
    r'^\s*(eu\s+)?(gostaria|queria|quero|desejo)\s+(de\s+)?(saber|entender|descobrir|verificar)\s+(se\s+)?',   # "gostaria de saber..."
    r'^\s*me\s+(diga|diz|fale|fala|explique|explica|informe|informa|mostre|mostra)\s+',           # "me diga..."
    r'^\s*(eu\s+)?(gostaria|queria|quero)\s+(que\s+)?(você|voce|vc)\s+(me\s+)?'
    r'(dissesse|explicasse|informasse|mostrasse)\s+',                                             # "gostaria que você explicasse..."
    r'^\s*(você|voce|vc)?\s*(pode|poderia|consegue)\s+me\s+ajudar\s+(a\s+)?',                     # "pode me ajudar a..."
]


RELLENO_EM_MEIO = (r'\b(por favor|por gentileza|por obséquio|se possível|desde já agradeço|'
                   r'muito obrigad[oa]|obrigad[oa])\b[,.!]?\s*')


RELLENO_FIM = [
    r'\s*[,.!]?\s*(por favor|por gentileza)\s*[.!?]*$',
    r'\s*[,.!]?\s*(obrigado|obrigada|valeu|agradeço)\s*[.!?]*$',
    r'\s*[.!]?\s*(desde já agradeço|muito obrigado|muito obrigada)\s*[.!?]*$',
]


FRASES_VAZIAS = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "obrigado", "obrigada", "valeu", "tudo bem"}


INTERROGATIVOS = ('como', 'qual', 'quais', 'quanto', 'quantos', 'quantas', 'quando', 'onde', 'por que', 'o que', 'quem')


def limpar_pergunta(texto):
    if not isinstance(texto, str):
        return ""
    texto = re.sub(r'<[^>]+>', ' ', texto.strip())
    for _ in range(3):                                    # repete: "Oi! Por favor, poderia me dizer..." precisa de mais de uma passada
        antes = texto
        for padrao in RELLENO_INICIO:
            texto = re.sub(padrao, '', texto, flags=re.IGNORECASE)
        texto = re.sub(RELLENO_EM_MEIO, ' ', texto, flags=re.IGNORECASE).strip(' ,;')
        if texto == antes:
            break
    texto = re.sub(RELLENO_EM_MEIO, ' ', texto, flags=re.IGNORECASE)
    for padrao in RELLENO_FIM:
        texto = re.sub(padrao, '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'\s+([,.!?;:])', r'\1', texto)
    texto = re.sub(r'([!?.,])\1+', r'\1', texto)          # pontuação repetida -> uma só
    texto = re.sub(r'\s*,\s*([?!.])', r'\1', texto)       # "cenoura,?" -> "cenoura?"
    return texto.strip(' ,;')


def pergunta_valida(texto):
    return bool(texto) and texto.lower().strip() not in FRASES_VAZIAS and len(texto.split()) >= 2


def comprimir_pregunta(pergunta):
    if not isinstance(pergunta, str):
        return ""
    original = pergunta.strip()
    q = limpar_pergunta(original)
    if not pergunta_valida(q):                            # limpeza destruiu a pergunta: fica com a original
        return original
    pedia_saber = re.search(r'\b(saber|entender|descobrir|verificar)\b', original, re.I)
    if (pedia_saber or q.lower().startswith(INTERROGATIVOS)) and not q.endswith('?'):
        q = q.rstrip('.!,') + '?'                         # mantém o sentido interrogativo
    return q[0].upper() + q[1:]
