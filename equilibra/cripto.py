"""
Criptografia dos textos clínicos no banco de dados.

Os campos marcados com TextoCifrado são gravados criptografados (Fernet/AES) e só
viram texto legível dentro do app. Quem tiver acesso apenas ao banco ou a um backup
vê conteúdo embaralhado.

A chave vem de CHAVE_DADOS (recomendado) ou, na falta dela, de SECRET_KEY.
Guarde essas variáveis: sem elas, os textos criptografados não podem ser lidos.
Textos antigos, gravados antes da criptografia, continuam legíveis e são
criptografados automaticamente na inicialização do app.
"""
import base64
import hashlib
import os
import time
import hmac
import struct

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy.types import Text, TypeDecorator

PREFIXO = "enc1:"
_cache = {}


def _fernet(segredo: str) -> Fernet:
    chave = hashlib.sha256(("equilibra-dados:" + segredo).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def _cofre() -> MultiFernet:
    fontes = tuple(s for s in (os.environ.get("CHAVE_DADOS"), os.environ.get("SECRET_KEY")) if s) or ("desenvolvimento-local",)
    if _cache.get("fontes") != fontes:
        # criptografa com a primeira chave; lê com qualquer uma (permite trocar de chave sem perder dados)
        _cache["fontes"], _cache["cofre"] = fontes, MultiFernet([_fernet(s) for s in fontes] + [_fernet("desenvolvimento-local")])
    return _cache["cofre"]


def cifrar(texto):
    if texto is None or str(texto).startswith(PREFIXO):
        return texto
    return PREFIXO + _cofre().encrypt(str(texto).encode()).decode()


def decifrar(valor):
    if valor is None or not str(valor).startswith(PREFIXO):
        return valor  # texto antigo, ainda não criptografado
    try:
        return _cofre().decrypt(valor[len(PREFIXO):].encode()).decode()
    except InvalidToken:
        return "[Conteúdo protegido: a chave de criptografia do servidor mudou. Restaure CHAVE_DADOS.]"


class TextoCifrado(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return cifrar(value)

    def process_result_value(self, value, dialect):
        return decifrar(value)


# ---------------------------------------------------------------- verificação em duas etapas (TOTP)
def novo_segredo_totp() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def codigo_totp(segredo: str, instante=None, passo=30, digitos=6) -> str:
    chave = base64.b32decode(segredo + "=" * (-len(segredo) % 8), casefold=True)
    contador = int((instante if instante is not None else time.time()) // passo)
    h = hmac.new(chave, struct.pack(">Q", contador), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    numero = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digitos)
    return f"{numero:0{digitos}d}"


def confere_totp(segredo: str, codigo: str) -> bool:
    codigo = "".join(ch for ch in (codigo or "") if ch.isdigit())
    if len(codigo) != 6 or not segredo:
        return False
    agora = time.time()
    return any(hmac.compare_digest(codigo_totp(segredo, agora + d * 30), codigo) for d in (-1, 0, 1))
