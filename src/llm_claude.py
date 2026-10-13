"""Chamada ao Claude com prompt caching e métricas (células 19 e 21 do notebook)."""
import hashlib

from . import config
from .contexto import tokens_aprox


SISTEMA_CLAUDE = (
    'Responda em português, de forma direta (até ~200 palavras). '
    'Pode vir um CONTEXTO com trechos de documentos de segurança e privacidade, cada um precedido de [Documento › Categoria › Seção]. '
    'Se o contexto responder à pergunta, baseie-se nele e cite a seção (por exemplo, "art. 48 da LGPD" ou "seção 8.2 da Cartilha"). '
    'Se a pergunta for claramente sobre os documentos e o contexto não trouxer a resposta, diga primeiro que isso não consta '
    'nos trechos recuperados e marque qualquer complemento como conhecimento geral. '
    'Não invente artigos, prazos, obrigações ou procedimentos. '
    'Se a pergunta não depender dos documentos, responda normalmente, sem mencionar o contexto.'
)


class ClienteClaude:
    def __init__(self, api):                  # api: instância de anthropic.Anthropic
        self.api = api
        self._hash_anterior = None

    def calibrar_tokens(self, texto, n=15000):
        # compara caracteres x tokens reais de uma amostra (count_tokens não gera nem cobra saída)
        muestra = texto[:n]
        if len(muestra) < 500:
            return config.CHARS_POR_TOKEN
        try:
            r = self.api.messages.count_tokens(model=config.CLAUDE_MODEL,
                                               messages=[{'role': 'user', 'content': muestra}])
            config.CHARS_POR_TOKEN = round(len(muestra) / max(1, r.input_tokens - 10), 2)
        except Exception as e:
            print(f'[Aviso] count_tokens indisponível ({e}); mantendo {config.CHARS_POR_TOKEN} caracteres/token.')
        return config.CHARS_POR_TOKEN

    def _decidir_cache(self, contexto, forzar=None):
        if not contexto or config.CACHE_MODO == 'nunca':
            return False
        if forzar is not None:
            return forzar
        if config.CACHE_MODO == 'siempre':
            return True
        h = hashlib.sha1(contexto.encode()).hexdigest()    # 'auto': grande E repetido
        repetido = (h == self._hash_anterior)
        self._hash_anterior = h
        return repetido and tokens_aprox(contexto) >= config.CACHE_MIN_TOKENS

    def gerar(self, pergunta, contexto='', max_tokens=config.CLAUDE_MAX_TOKENS, forzar_cache=None):
        usar_cache = self._decidir_cache(contexto, forzar_cache)
        if contexto:
            bloque_ctx = {'type': 'text', 'text': f'Baseie-se no contexto abaixo quando for relevante:\n\n{contexto}'}
            if usar_cache:
                bloque_ctx['cache_control'] = {'type': 'ephemeral'}
            contenido = [bloque_ctx, {'type': 'text', 'text': f'Pergunta do utilizador: {pergunta}'}]
        else:
            contenido = pergunta

        kwargs = dict(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=SISTEMA_CLAUDE,
                      messages=[{'role': 'user', 'content': contenido}])
        if config.TEMPERATURA is not None:
            kwargs['temperature'] = config.TEMPERATURA
        if config.DESACTIVAR_THINKING:
            kwargs['thinking'] = {'type': 'disabled'}
        try:
            resp = self.api.messages.create(**kwargs)
        except Exception as e:
            return {'texto': f'[Erro ao chamar o Claude: {e}]', 'tokens_in': 0, 'tokens_out': 0,
                    'cache_creation': 0, 'cache_read': 0, 'costo_in_eq': 0.0, 'cache_usado': usar_cache,
                    'cortada': False, 'bloques': []}

        u = resp.usage
        normal = u.input_tokens
        creacion = getattr(u, 'cache_creation_input_tokens', 0) or 0
        lectura = getattr(u, 'cache_read_input_tokens', 0) or 0
        return {
            'texto': ''.join(b.text for b in resp.content if b.type == 'text'),
            'tokens_in': normal + creacion + lectura,               # total do prompt
            'tokens_out': u.output_tokens,
            'cache_creation': creacion,
            'cache_read': lectura,
            'costo_in_eq': normal + 1.25 * creacion + 0.1 * lectura,  # em "tokens normais"
            'cache_usado': usar_cache,
            'cortada': resp.stop_reason == 'max_tokens',
            'bloques': [b.type for b in resp.content],
        }
