"""Conta, segurança e LGPD: perfil, senha, verificação em duas etapas, recuperação de acesso,
exportação e exclusão de dados, termos de uso e política de privacidade."""
import json
import os
import secrets
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

import click
import segno
from flask import Response, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

import cripto
from app import (INDICADORES, Acesso, CheckIn, Consentimento, Consulta, DemoItem, Pagamento, Paciente, Registro,
                 Terapeuta, Transcricao, app, conferir_senha, db, definir_senha, exige, meu_paciente)

VALIDADE_EMAIL = 60 * 60          # link enviado por e-mail: 1 hora
VALIDADE_TERAPEUTA = 72 * 60 * 60  # link gerado pelo terapeuta para o paciente: 72 horas


def _assinador():
    return URLSafeTimedSerializer(app.secret_key, salt="equilibra-redefinir-senha")


def gerar_token(u):
    # inclui um pedaço do hash atual: depois que a senha muda, o link deixa de valer
    return _assinador().dumps({"t": u.papel[0], "id": u.id, "h": (u.senha_hash or "")[-16:]})


def ler_token(token, validade):
    try:
        d = _assinador().loads(token, max_age=validade)
    except (SignatureExpired, BadSignature):
        return None
    modelo = Terapeuta if d.get("t") == "t" else Paciente
    u = db.session.get(modelo, d.get("id"))
    return u if u and (u.senha_hash or "")[-16:] == d.get("h") else None


def email_configurado():
    return all(os.environ.get(v) for v in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_SENHA"))


def enviar_email(para, assunto, texto):
    msg = EmailMessage()
    msg["From"] = os.environ.get("EMAIL_REMETENTE") or os.environ["SMTP_USUARIO"]
    msg["To"], msg["Subject"] = para, assunto
    msg.set_content(texto)
    porta = int(os.environ.get("SMTP_PORTA", "587"))
    if porta == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], porta, context=ssl.create_default_context(), timeout=20) as s:
            s.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_SENHA"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"], porta, timeout=20) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_SENHA"])
            s.send_message(msg)


def validar_nova_senha(senha, confirma):
    if len(senha) < 8:
        return "A senha precisa ter pelo menos 8 caracteres."
    if senha != confirma:
        return "As senhas não conferem."
    return None


# ---------------------------------------------------------------- verificação em duas etapas no login
@app.route("/entrar/codigo", methods=["GET", "POST"])
def entrar_codigo():
    tid = session.get("2fa_pendente")
    t = db.session.get(Terapeuta, tid) if tid else None
    if not t:
        return redirect(url_for("entrar"))
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        ok = cripto.confere_totp(t.totp_segredo, codigo)
        if not ok and t.codigos_recuperacao:
            restantes = t.codigos_recuperacao.split("|")
            for h in restantes:
                if check_password_hash(h, codigo.replace(" ", "").upper()):
                    restantes.remove(h)
                    t.codigos_recuperacao = "|".join(restantes)
                    db.session.commit()
                    flash(f"Código de recuperação usado. Restam {len(restantes)}.", "aviso")
                    ok = True
                    break
        if ok:
            session.pop("2fa_pendente", None)
            login_user(t, remember=False)
            session["ultimo_uso"] = datetime.now().timestamp()
            return redirect(url_for("painel"))
        flash("Código incorreto. Confira o app autenticador e tente de novo.", "erro")
    return render_template("c_codigo.html")


# ---------------------------------------------------------------- esqueci minha senha
@app.route("/esqueci", methods=["GET", "POST"])
def esqueci():
    enviado = False
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = Terapeuta.query.filter_by(email=email).first() or Paciente.query.filter_by(email=email).first()
        if u and email_configurado():
            link = url_for("redefinir", token=gerar_token(u), _external=True)
            try:
                enviar_email(email, "Equilibra: redefinir senha",
                             f"Olá,\n\nPara criar uma nova senha no Equilibra, abra o link abaixo em até 1 hora:\n\n{link}\n\n"
                             "Se você não pediu isso, ignore este e-mail. Sua senha atual continua valendo.")
            except Exception:
                pass  # não revela se o e-mail existe nem se o envio falhou
        enviado = True
    return render_template("c_esqueci.html", enviado=enviado, email_ok=email_configurado())


@app.route("/redefinir/<token>", methods=["GET", "POST"])
def redefinir(token):
    u = ler_token(token, VALIDADE_TERAPEUTA)
    if not u:
        flash("Este link expirou ou já foi usado. Peça um novo.", "erro")
        return redirect(url_for("esqueci"))
    if request.method == "POST":
        erro = validar_nova_senha(request.form.get("senha", ""), request.form.get("confirma", ""))
        if erro:
            flash(erro, "erro")
        else:
            definir_senha(u, request.form["senha"])
            db.session.commit()
            flash("Senha alterada. Entre com a nova senha.", "ok")
            return redirect(url_for("entrar"))
    return render_template("c_redefinir.html", u=u)


@app.route("/t/pacientes/<int:pid>/link-senha", methods=["POST"])
@exige("terapeuta")
def link_senha_paciente(pid):
    p = meu_paciente(pid)
    if not p.tem_acesso:
        flash("Este paciente ainda não criou acesso. Use o link de convite.", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id) + "#acesso")
    session["link_senha"] = {"pid": p.id, "url": url_for("redefinir", token=gerar_token(p), _external=True)}
    flash("Link de nova senha gerado. Ele vale por 72 horas e funciona uma vez.", "ok")
    return redirect(url_for("paciente_detalhe", pid=p.id) + "#acesso")


@app.cli.command("link-senha")
@click.argument("email")
def cli_link_senha(email):
    """Gera um link de nova senha para um terapeuta (use no Shell do Render)."""
    t = Terapeuta.query.filter_by(email=email.strip().lower()).first()
    if not t:
        click.echo("Nenhum terapeuta com esse e-mail.")
        return
    base = os.environ.get("ENDERECO_APP", "").rstrip("/")
    with app.test_request_context(base_url=base or "http://localhost"):
        click.echo(url_for("redefinir", token=gerar_token(t), _external=True))


# ---------------------------------------------------------------- conta do terapeuta
@app.route("/t/conta", methods=["GET", "POST"])
@exige("terapeuta")
def conta_terapeuta():
    t = current_user
    if request.method == "POST":
        acao = request.form.get("acao")
        f = request.form
        if acao == "perfil":
            t.nome = f.get("nome", "").strip()[:80] or t.nome
            t.registro_prof = f.get("registro_prof", "").strip()[:60] or None
            t.cidade = f.get("cidade", "").strip()[:80] or None
            t.telefone = f.get("telefone", "").strip()[:30] or None
            db.session.commit()
            flash("Perfil atualizado. Ele aparece nos recibos e relatórios.", "ok")
        elif acao == "senha":
            if not conferir_senha(t, f.get("atual", "")):
                flash("A senha atual está incorreta.", "erro")
            elif erro := validar_nova_senha(f.get("senha", ""), f.get("confirma", "")):
                flash(erro, "erro")
            else:
                definir_senha(t, f["senha"])
                db.session.commit()
                flash("Senha alterada.", "ok")
        elif acao == "2fa_iniciar":
            session["totp_novo"] = cripto.novo_segredo_totp()
        elif acao == "2fa_confirmar":
            segredo = session.get("totp_novo")
            if segredo and cripto.confere_totp(segredo, f.get("codigo", "")):
                codigos = [secrets.token_hex(4).upper() for _ in range(8)]
                t.totp_segredo, t.totp_ativo = segredo, True
                t.codigos_recuperacao = "|".join(generate_password_hash(c) for c in codigos)
                db.session.commit()
                session.pop("totp_novo", None)
                return render_template("c_codigos.html", codigos=codigos)
            flash("Código incorreto. Confira se o horário do celular está automático e tente de novo.", "erro")
        elif acao == "2fa_desligar":
            if conferir_senha(t, f.get("atual", "")):
                t.totp_ativo, t.totp_segredo, t.codigos_recuperacao = False, None, None
                db.session.commit()
                flash("Verificação em duas etapas desligada.", "aviso")
            else:
                flash("Senha incorreta.", "erro")
        return redirect(url_for("conta_terapeuta") + ("#seguranca" if acao and acao.startswith(("2fa", "senha")) else ""))
    qr = None
    if session.get("totp_novo"):
        uri = f"otpauth://totp/Equilibra:{t.email}?secret={session['totp_novo']}&issuer=Equilibra"
        qr = {"svg": Markup(segno.make(uri, error="m").svg_inline(scale=5, dark="#17507D", light="#FFFFFF")),
              "segredo": session["totp_novo"], "uri": uri}
    acessos = Acesso.query.filter_by(terapeuta_id=t.id).order_by(Acesso.quando.desc()).limit(15).all()
    nomes = {p.id: p.nome for p in Paciente.query.filter_by(terapeuta_id=t.id)}
    return render_template("c_terapeuta.html", qr=qr, acessos=acessos, nomes=nomes,
                           restantes=len(t.codigos_recuperacao.split("|")) if t.codigos_recuperacao else 0)


# ---------------------------------------------------------------- conta do paciente
@app.route("/p/conta", methods=["GET", "POST"])
@exige("paciente")
def conta_paciente():
    p = current_user
    if request.method == "POST" and not session.get("demo_como"):
        f = request.form
        if not conferir_senha(p, f.get("atual", "")):
            flash("A senha atual está incorreta.", "erro")
        elif erro := validar_nova_senha(f.get("senha", ""), f.get("confirma", "")):
            flash(erro, "erro")
        else:
            definir_senha(p, f["senha"])
            db.session.commit()
            flash("Senha alterada.", "ok")
        return redirect(url_for("conta_paciente"))
    return render_template("c_paciente.html")


# ---------------------------------------------------------------- LGPD: exportar e excluir
def dados_paciente(p, completo=True):
    """Todos os dados do paciente em formato aberto. completo=False omite anotações privadas do terapeuta."""
    def linha(obj, campos):
        out = {}
        for c in campos:
            v = getattr(obj, c)
            out[c] = v.isoformat() if hasattr(v, "isoformat") else v
        return out
    base = linha(p, ["nome", "nascimento", "telefone", "email", "substancias", "tipo_teste", "tempo_uso", "status",
                     "inicio_tratamento", "ultimo_uso", "sessoes_semana", "valor_sessao", "horario_pref",
                     "emergencia_nome", "emergencia_tel", "criado_em"])
    if completo:
        base["anamnese"] = p.anamnese
    campos_reg = ["data", "realizada", "humor"] + [c for c, _, _ in INDICADORES] + [
        "uso_recente", "data_uso", "teste_feito", "teste_tipo", "teste_resultado", "risco", "abordagens", "tarefa_paciente"]
    if completo:
        campos_reg += ["comentarios", "feedback_ia"]
    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "paciente": base,
        "sessoes": [linha(c, ["inicio", "duracao", "tipo", "status", "checkin_em", "checkout_em"])
                    for c in Consulta.query.filter_by(paciente_id=p.id).order_by(Consulta.inicio)],
        "registros": [linha(r, campos_reg) for r in Registro.query.filter_by(paciente_id=p.id).order_by(Registro.data)],
        "checkins": [linha(c, ["data", "humor", "fissura", "sono", "usou", "gatilhos", "nota"])
                     for c in CheckIn.query.filter_by(paciente_id=p.id).order_by(CheckIn.data)],
        "pagamentos": [linha(x, ["data", "valor", "sessoes", "forma", "nota"])
                       for x in Pagamento.query.filter_by(paciente_id=p.id).order_by(Pagamento.data)],
        "consentimentos": [linha(c, ["assinado_em", "versao", "revogado_em"])
                           for c in Consentimento.query.filter_by(paciente_id=p.id)],
        "transcricoes": [linha(t, ["criado_em", "tipo", "texto"]) for t in Transcricao.query.filter_by(paciente_id=p.id)]
        if completo else [],
    }


def baixar_json(dados, nome):
    return Response(json.dumps(dados, ensure_ascii=False, indent=2, default=str), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "no-store"})


@app.route("/t/pacientes/<int:pid>/exportar")
@exige("terapeuta")
def exportar_paciente(pid):
    from app import registrar_acesso
    p = meu_paciente(pid)
    registrar_acesso(p.id, "exportou dados")
    return baixar_json(dados_paciente(p), f"dados-paciente-{p.id}.json")


@app.route("/p/conta/exportar")
@exige("paciente")
def exportar_meus_dados():
    return baixar_json(dados_paciente(current_user, completo=False), "meus-dados-equilibra.json")


@app.route("/t/conta/exportar")
@exige("terapeuta")
def exportar_tudo():
    from financeiro import Despesa
    pacientes = Paciente.query.filter_by(terapeuta_id=current_user.id).all()
    return baixar_json({
        "terapeuta": {"nome": current_user.nome, "email": current_user.email},
        "pacientes": [dados_paciente(p) for p in pacientes],
        "despesas": [{"data": d.data.isoformat(), "descricao": d.descricao, "categoria": d.categoria, "valor": d.valor}
                     for d in Despesa.query.filter_by(terapeuta_id=current_user.id)],
    }, f"equilibra-copia-{datetime.now():%Y-%m-%d}.json")


def apagar_pacientes(ids, terapeuta_id):
    """Exclusão definitiva, usada pela LGPD e pelos dados de demonstração."""
    if not ids:
        return 0
    for modelo in (Transcricao, Registro, CheckIn, Pagamento, Consentimento, Consulta):
        modelo.query.filter(modelo.paciente_id.in_(ids)).delete(synchronize_session=False)
    Acesso.query.filter(Acesso.paciente_id.in_(ids)).delete(synchronize_session=False)
    DemoItem.query.filter(DemoItem.tipo == "paciente", DemoItem.ref_id.in_(ids)).delete(synchronize_session=False)
    n = Paciente.query.filter(Paciente.id.in_(ids), Paciente.terapeuta_id == terapeuta_id).delete(synchronize_session=False)
    db.session.commit()
    return n


@app.route("/t/pacientes/<int:pid>/excluir", methods=["POST"])
@exige("terapeuta")
def excluir_paciente(pid):
    p = meu_paciente(pid)
    if request.form.get("confirma", "").strip().lower() != p.nome.strip().lower():
        flash("Para excluir, digite o nome do paciente exatamente como está cadastrado.", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id) + "#lgpd")
    nome = p.nome
    apagar_pacientes([p.id], current_user.id)
    flash(f"Todos os dados de {nome} foram excluídos definitivamente.", "ok")
    return redirect(url_for("pacientes"))


# ---------------------------------------------------------------- termos e privacidade
@app.route("/termos")
def termos():
    return render_template("c_termos.html")


@app.route("/privacidade")
def privacidade():
    return render_template("c_privacidade.html")
