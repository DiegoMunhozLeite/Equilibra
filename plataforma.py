"""
Camada de plataforma: segurança de borda, observabilidade e desempenho.

- Limite de tentativas (login, código de verificação, cadastro, senha) guardado no banco,
  para valer entre todos os processos do servidor.
- Cabeçalhos modernos: Content-Security-Policy com nonce por requisição, HSTS,
  Permissions-Policy (microfone só no próprio app), isolamento de origem.
- Log estruturado de cada requisição com identificador, tempo e status.
- Página de erro 500 amigável e verificação de saúde em /saude.
- Índices para as consultas mais frequentes.
"""
import logging
import os
import secrets
import time
from datetime import datetime, timedelta

from flask import g, jsonify, render_template, request
from sqlalchemy import text

from app import DEV, VERSAO, app, db

log = logging.getLogger("equilibra")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


# ============================================================ limite de tentativas
class Tentativa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(200), index=True, nullable=False)
    quando = db.Column(db.DateTime, default=datetime.now, index=True)


# endpoint: (máximo de envios, janela em minutos)
LIMITES = {
    "entrar": (10, 15), "entrar_codigo": (6, 10), "esqueci": (5, 60), "redefinir": (10, 60),
    "cadastro": (10, 60), "convite": (10, 60), "conta_terapeuta": (20, 15), "conta_paciente": (10, 15),
}


def _ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())[:64]


@app.before_request
def limitar_tentativas():
    g.inicio = time.perf_counter()
    g.req_id = secrets.token_hex(4)
    g.nonce = secrets.token_urlsafe(16)
    regra = LIMITES.get(request.endpoint)
    if request.method != "POST" or not regra:
        return
    maximo, minutos = regra
    chave = f"{request.endpoint}:{_ip()}"
    desde = datetime.now() - timedelta(minutes=minutos)
    try:
        n = Tentativa.query.filter(Tentativa.chave == chave, Tentativa.quando >= desde).count()
        if n >= maximo:
            log.warning("limite atingido req=%s chave=%s", g.req_id, chave)
            return render_template("erro.html", e=type("E", (), {"code": 429})(),
                                   minutos=minutos), 429
        db.session.add(Tentativa(chave=chave))
        if secrets.randbelow(50) == 0:  # limpeza ocasional
            Tentativa.query.filter(Tentativa.quando < datetime.now() - timedelta(days=1)).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.context_processor
def contexto_plataforma():
    return {"csp_nonce": lambda: getattr(g, "nonce", "")}


# ============================================================ cabeçalhos de segurança e log
@app.after_request
def cabecalhos_modernos(resp):
    nonce = getattr(g, "nonce", "")
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; "
        "connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
    resp.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(), payment=(), usb=()"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if not DEV:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["X-Request-Id"] = getattr(g, "req_id", "")
    if request.endpoint not in ("static", "saude"):
        ms = (time.perf_counter() - getattr(g, "inicio", time.perf_counter())) * 1000
        log.info("req=%s %s %s %s %.0fms", getattr(g, "req_id", "-"), request.method, request.path, resp.status_code, ms)
    return resp


@app.errorhandler(500)
def erro_interno(e):
    db.session.rollback()
    log.exception("erro req=%s %s %s", getattr(g, "req_id", "-"), request.method, request.path)
    return render_template("erro.html", e=type("E", (), {"code": 500})(), req_id=getattr(g, "req_id", "")), 500


@app.errorhandler(429)
def muitas(e):
    return render_template("erro.html", e=type("E", (), {"code": 429})(), minutos=15), 429


# ============================================================ saúde do serviço
@app.route("/saude")
def saude():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(ok=True, versao=VERSAO), 200
    except Exception:
        db.session.rollback()
        return jsonify(ok=False, versao=VERSAO), 503


# ============================================================ índices para as consultas mais usadas
INDICES = [
    ("ix_consulta_terapeuta_inicio", "consulta", "terapeuta_id, inicio"),
    ("ix_consulta_paciente_inicio", "consulta", "paciente_id, inicio"),
    ("ix_registro_paciente_data", "registro", "paciente_id, data"),
    ("ix_registro_terapeuta_data", "registro", "terapeuta_id, data"),
    ("ix_checkin_paciente_data", "check_in", "paciente_id, data"),
    ("ix_pagamento_paciente_data", "pagamento", "paciente_id, data"),
    ("ix_transcricao_terapeuta_criado", "transcricao", "terapeuta_id, criado_em"),
    ("ix_acesso_paciente_quando", "acesso", "paciente_id, quando"),
    ("ix_cobranca_assinatura_venc", "cobranca", "assinatura_id, vencimento"),
]


def criar_indices():
    for nome, tabela, colunas in INDICES:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(f'CREATE INDEX IF NOT EXISTS {nome} ON "{tabela}" ({colunas})'))
        except Exception:
            pass
