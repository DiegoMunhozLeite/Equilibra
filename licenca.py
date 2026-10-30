"""
Licenças e revenda do Equilibra: planos, assinaturas, cobranças, clínicas e painel da plataforma.

A cobrança é SIMULADA nesta versão: nenhum dado de cartão é pedido ou guardado.
Para cobrar de verdade, integre um serviço de pagamentos com página de pagamento
hospedada por ele (o app nunca deve receber dados de cartão).

Quem administra a plataforma é definido por ADMIN_EMAILS (e-mails separados por vírgula).
"""
import os
import secrets
from datetime import date, datetime, timedelta

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app import (MESES, Paciente, Terapeuta, Transcricao, app, db, exige, hoje, para_data, para_float, para_int)

DIAS_TESTE = int(os.environ.get("DIAS_TESTE", "14"))
TOLERANCIA_ATRASO = 7  # dias de atraso antes de bloquear novas criações
STATUS = {"teste": "Em teste", "ativa": "Ativa", "atrasada": "Pagamento atrasado", "expirada": "Teste encerrado",
          "cancelada": "Cancelada", "cortesia": "Cortesia"}
METODOS = {"pix": "Pix", "cartao": "Cartão de crédito", "boleto": "Boleto"}


# ============================================================ modelos
class Plano(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    nome = db.Column(db.String(60), nullable=False)
    publico = db.Column(db.String(10), nullable=False)       # autonomo | clinica
    preco_mensal = db.Column(db.Float, nullable=False)       # clínica: preço por terapeuta
    meses_gratis_anual = db.Column(db.Integer, default=2)    # no plano anual, paga 12 menos isso
    limite_pacientes = db.Column(db.Integer)                 # vazio = ilimitado
    minutos_ia = db.Column(db.Integer, default=0)            # por mês; clínica: por terapeuta
    minimo_terapeutas = db.Column(db.Integer, default=1)
    recursos = db.Column(db.Text)                            # uma linha por recurso
    destaque = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)

    @property
    def lista_recursos(self):
        return [r.strip() for r in (self.recursos or "").splitlines() if r.strip()]

    def preco_anual(self, assentos=1):
        return self.preco_mensal * max(assentos, self.minimo_terapeutas or 1) * (12 - (self.meses_gratis_anual or 0))


class Clinica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    convite_token = db.Column(db.String(40), unique=True)
    criada_em = db.Column(db.DateTime, default=datetime.now)
    demo_plataforma = db.Column(db.Boolean, default=False)

    @property
    def membros(self):
        return Terapeuta.query.filter_by(clinica_id=self.id).order_by(Terapeuta.nome).all()


class Assinatura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, index=True)   # conta de autônomo
    clinica_id = db.Column(db.Integer, index=True)     # conta de clínica
    plano_id = db.Column(db.Integer, db.ForeignKey("plano.id"), nullable=False)
    status = db.Column(db.String(12), default="teste")
    ciclo = db.Column(db.String(8), default="mensal")  # mensal | anual
    assentos = db.Column(db.Integer, default=1)
    criada_em = db.Column(db.Date, default=hoje)
    teste_ate = db.Column(db.Date)
    inicio_pago = db.Column(db.Date)
    proxima_cobranca = db.Column(db.Date)
    cancelada_em = db.Column(db.Date)
    plano = db.relationship("Plano")

    @property
    def e_clinica(self):
        return self.clinica_id is not None

    @property
    def clinica(self):
        return db.session.get(Clinica, self.clinica_id) if self.clinica_id else None

    @property
    def dono(self):
        if self.clinica_id:
            return Terapeuta.query.filter_by(clinica_id=self.clinica_id, papel_clinica="admin").first()
        return db.session.get(Terapeuta, self.terapeuta_id)

    @property
    def nome_conta(self):
        c = self.clinica
        return c.nome if c else (self.dono.nome if self.dono else "Conta removida")

    @property
    def terapeutas(self):
        return Terapeuta.query.filter_by(clinica_id=self.clinica_id).count() if self.clinica_id else 1

    @property
    def assentos_cobrados(self):
        if not self.e_clinica:
            return 1
        return max(self.assentos or 1, self.plano.minimo_terapeutas or 1, self.terapeutas)

    def valor_mensal(self):
        """Receita recorrente mensal (MRR) desta conta."""
        if self.status in ("teste", "expirada", "cancelada", "cortesia"):
            return 0.0
        if self.ciclo == "anual":
            return self.plano.preco_anual(self.assentos_cobrados) / 12
        return self.plano.preco_mensal * self.assentos_cobrados

    def valor_ciclo(self):
        if self.ciclo == "anual":
            return self.plano.preco_anual(self.assentos_cobrados)
        return self.plano.preco_mensal * self.assentos_cobrados


class Cobranca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assinatura_id = db.Column(db.Integer, db.ForeignKey("assinatura.id"), nullable=False, index=True)
    valor = db.Column(db.Float, nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    pago_em = db.Column(db.Date)
    metodo = db.Column(db.String(10))
    status = db.Column(db.String(10), default="pendente")  # pendente | paga | cancelada
    simulada = db.Column(db.Boolean, default=True)
    assinatura = db.relationship("Assinatura")


PLANOS_PADRAO = [
    dict(codigo="essencial", nome="Essencial", publico="autonomo", preco_mensal=79.0, limite_pacientes=15, minutos_ia=120, ordem=1,
         recursos="Até 15 pacientes ativos\nAgenda, prontuário e check-in do paciente\n120 minutos de transcrição com IA por mês\nFinanceiro e recibos\nRelatórios em PDF"),
    dict(codigo="profissional", nome="Profissional", publico="autonomo", preco_mensal=149.0, limite_pacientes=None, minutos_ia=600, ordem=2, destaque=True,
         recursos="Pacientes ilimitados\nTudo do Essencial\n600 minutos de transcrição com IA por mês\nResumo e feedback clínico com IA\nSuporte prioritário"),
    dict(codigo="clinica", nome="Clínica", publico="clinica", preco_mensal=119.0, limite_pacientes=None, minutos_ia=600, minimo_terapeutas=3, ordem=3,
         recursos="Preço por terapeuta (mínimo 3)\nPacientes ilimitados\n600 minutos de IA por terapeuta\nPainel da clínica com a equipe\nConvite de terapeutas por link"),
]


def semear_planos():
    if Plano.query.count() == 0:
        for p in PLANOS_PADRAO:
            db.session.add(Plano(**p))
        db.session.commit()


def planos_ativos(publico=None):
    try:
        q = Plano.query.filter_by(ativo=True)
        if publico:
            q = q.filter_by(publico=publico)
        return q.order_by(Plano.ordem).all()
    except Exception:
        return []


def plano(codigo):
    return Plano.query.filter_by(codigo=codigo).first()


def e_admin(u):
    if os.environ.get("MODO_TESTE_ABERTO") == "1" and u and getattr(u, "papel", "") == "terapeuta":
        return True  # versão de teste: todos veem o Painel da plataforma
    lista = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
    return bool(u and getattr(u, "papel", "") == "terapeuta" and u.email.lower() in lista)


def somar_meses(d, meses):
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    dias = [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return date(ano, mes, min(d.day, dias))


# ============================================================ regras da assinatura
def assinatura_da_conta(t, criar=True):
    a = (Assinatura.query.filter_by(clinica_id=t.clinica_id).first() if t.clinica_id
         else Assinatura.query.filter_by(terapeuta_id=t.id).first())
    if a and e_admin(t) and a.status in ("teste", "expirada"):
        a.status = "cortesia"  # quem administra a plataforma não paga
        db.session.commit()
    if a or not criar:
        return a
    semear_planos()
    if e_admin(t):
        a = Assinatura(terapeuta_id=t.id, plano_id=plano("profissional").id, status="cortesia")
    else:
        a = Assinatura(terapeuta_id=t.id, plano_id=plano("profissional").id, status="teste",
                       teste_ate=hoje() + timedelta(days=DIAS_TESTE))
    db.session.add(a)
    db.session.commit()
    return a


def atualizar(a):
    """Vira o ciclo: encerra testes vencidos, gera cobranças e marca atrasos."""
    mudou = False
    if a.status == "teste" and a.teste_ate and a.teste_ate < hoje():
        a.status, mudou = "expirada", True
    passo = 12 if a.ciclo == "anual" else 1
    while a.status in ("ativa", "atrasada") and a.proxima_cobranca and a.proxima_cobranca <= hoje():
        # emite a cobrança do ciclo e já agenda a seguinte (cobre vários ciclos perdidos sem duplicar)
        if not Cobranca.query.filter_by(assinatura_id=a.id, vencimento=a.proxima_cobranca).first():
            db.session.add(Cobranca(assinatura_id=a.id, valor=a.valor_ciclo(), vencimento=a.proxima_cobranca))
        a.proxima_cobranca = somar_meses(a.proxima_cobranca, passo)
        mudou = True
    if mudou:
        db.session.flush()
    if a.status in ("ativa", "atrasada"):
        pendente = (Cobranca.query.filter_by(assinatura_id=a.id, status="pendente")
                    .filter(Cobranca.vencimento < hoje()).first())
        novo = "atrasada" if pendente else "ativa"
        if novo != a.status:
            a.status, mudou = novo, True
    if mudou:
        db.session.commit()
    return a


def situacao(a):
    pendente = Cobranca.query.filter_by(assinatura_id=a.id, status="pendente").order_by(Cobranca.vencimento).first()
    dias_atraso = (hoje() - pendente.vencimento).days if pendente and pendente.vencimento < hoje() else 0
    pode = a.status in ("teste", "ativa", "cortesia") or (a.status == "atrasada" and dias_atraso <= TOLERANCIA_ATRASO)
    dias_teste = (a.teste_ate - hoje()).days if a.status == "teste" and a.teste_ate else None
    aviso = None
    if a.status == "teste" and dias_teste is not None and dias_teste <= 5:
        aviso = f"Seu teste grátis termina em {dias_teste} {'dia' if dias_teste == 1 else 'dias'}."
    elif a.status == "expirada":
        aviso = "Seu teste grátis terminou. Seus dados estão guardados; assine para voltar a cadastrar e gravar."
    elif a.status == "atrasada":
        aviso = (f"Pagamento em atraso há {dias_atraso} {'dia' if dias_atraso == 1 else 'dias'}." +
                 ("" if pode else " Novos cadastros e gravações estão pausados até a regularização."))
    elif a.status == "cancelada":
        aviso = "Assinatura cancelada. Seus dados continuam disponíveis para consulta e exportação."
    return {"pode": pode, "dias_teste": dias_teste, "aviso": aviso, "pendente": pendente, "dias_atraso": dias_atraso}


def uso(t, a):
    ini = date(hoje().year, hoje().month, 1)
    ids = [t.id] if not a.e_clinica else [m.id for m in Terapeuta.query.filter_by(clinica_id=a.clinica_id)]
    segundos = (db.session.query(func.coalesce(func.sum(Transcricao.segundos), 0))
                .filter(Transcricao.terapeuta_id == t.id, Transcricao.criado_em >= datetime.combine(ini, datetime.min.time())).scalar())
    return {
        "pacientes": Paciente.query.filter_by(terapeuta_id=t.id).filter(Paciente.status.in_(["ativo", "pausado"])).count(),
        "limite_pacientes": a.plano.limite_pacientes,
        "minutos": round((segundos or 0) / 60),
        "limite_minutos": a.plano.minutos_ia,
        "terapeutas": len(ids),
    }


def contratar(a, novo_plano, ciclo, assentos, metodo):
    a.plano_id, a.ciclo = novo_plano.id, ("anual" if ciclo == "anual" else "mensal")
    a.assentos = max(assentos or 1, novo_plano.minimo_terapeutas or 1) if novo_plano.publico == "clinica" else 1
    db.session.flush()
    db.session.refresh(a)
    a.status, a.inicio_pago, a.cancelada_em = "ativa", hoje(), None
    db.session.add(Cobranca(assinatura_id=a.id, valor=a.valor_ciclo(), vencimento=hoje(), pago_em=hoje(),
                            metodo=metodo if metodo in METODOS else "pix", status="paga"))
    a.proxima_cobranca = somar_meses(hoje(), 12 if a.ciclo == "anual" else 1)
    db.session.commit()


def pagar(c, metodo):
    c.status, c.pago_em, c.metodo = "paga", hoje(), metodo if metodo in METODOS else "pix"
    a = c.assinatura
    db.session.commit()
    atualizar(a)


# ============================================================ integração com o restante do app
def ler_convite_clinica(token):
    if not token:
        return None
    try:
        return Clinica.query.filter_by(convite_token=token).first()
    except Exception:
        return None


def apos_cadastro(t, f, convite):
    semear_planos()
    if convite:
        t.clinica_id, t.papel_clinica = convite.id, "membro"
        db.session.commit()
        return
    if f.get("tipo_conta") == "clinica":
        c = Clinica(nome=f.get("nome_clinica", "").strip()[:100], convite_token=secrets.token_urlsafe(16))
        db.session.add(c)
        db.session.flush()
        t.clinica_id, t.papel_clinica = c.id, "admin"
        p = plano("clinica")
        db.session.add(Assinatura(clinica_id=c.id, plano_id=p.id, status="teste", assentos=p.minimo_terapeutas or 1,
                                  teste_ate=hoje() + timedelta(days=DIAS_TESTE)))
        db.session.commit()
        return
    escolhido = plano(f.get("plano", "")) if f.get("plano") else None
    if not escolhido or escolhido.publico != "autonomo":
        escolhido = plano("profissional")
    db.session.add(Assinatura(terapeuta_id=t.id, plano_id=escolhido.id, status="cortesia" if e_admin(t) else "teste",
                              teste_ate=hoje() + timedelta(days=DIAS_TESTE)))
    db.session.commit()


BLOQUEIOS = {"paciente_form": "cadastrar pacientes", "consulta_form": "agendar sessões", "gravacao_nova": "gravar"}


@app.before_request
def verificar_licenca():
    ep = request.endpoint
    if request.method != "POST" or ep not in BLOQUEIOS or not current_user.is_authenticated or current_user.papel != "terapeuta":
        return
    if (request.view_args or {}).get("pid") or (request.view_args or {}).get("cid"):
        return  # editar o que já existe continua liberado
    a = atualizar(assinatura_da_conta(current_user))
    s = situacao(a)
    msg = None
    if not s["pode"]:
        msg = f"Para {BLOQUEIOS[ep]}, regularize sua assinatura. Seus dados continuam disponíveis."
    elif ep == "paciente_form" and a.plano.limite_pacientes and a.status != "cortesia" and \
            uso(current_user, a)["pacientes"] >= a.plano.limite_pacientes:
        msg = f"Seu plano permite até {a.plano.limite_pacientes} pacientes ativos. Mude de plano para cadastrar mais."
    elif ep == "gravacao_nova" and a.plano.minutos_ia and a.status != "cortesia" and \
            uso(current_user, a)["minutos"] >= a.plano.minutos_ia:
        msg = f"Você usou os {a.plano.minutos_ia} minutos de transcrição do mês. Mude de plano ou aguarde o próximo mês."
    if msg:
        if ep == "gravacao_nova":
            return jsonify(erro=msg), 402
        flash(msg, "erro")
        return redirect(url_for("minha_assinatura"))


@app.context_processor
def contexto_licenca():
    dados = {"e_admin": False, "licenca": None, "STATUS_ASSINATURA": STATUS, "METODOS": METODOS}
    try:
        if current_user.is_authenticated and current_user.papel == "terapeuta":
            a = assinatura_da_conta(current_user)
            dados.update(e_admin=e_admin(current_user), licenca={"a": a, **situacao(atualizar(a))})
    except Exception:
        db.session.rollback()
    return dados


# ============================================================ páginas do terapeuta
@app.route("/planos")
def planos_publicos():
    return render_template("planos.html", autonomos=planos_ativos("autonomo"), clinicas=planos_ativos("clinica"),
                           dias_teste=DIAS_TESTE)


@app.route("/t/assinatura")
@exige("terapeuta")
def minha_assinatura():
    a = atualizar(assinatura_da_conta(current_user))
    cobrancas = Cobranca.query.filter_by(assinatura_id=a.id).order_by(Cobranca.vencimento.desc()).limit(24).all()
    gestor = not a.e_clinica or current_user.papel_clinica == "admin"
    return render_template("t_assinatura.html", a=a, s=situacao(a), u=uso(current_user, a), cobrancas=cobrancas, gestor=gestor)


@app.route("/t/assinatura/contratar", methods=["GET", "POST"])
@exige("terapeuta")
def contratar_plano():
    a = assinatura_da_conta(current_user)
    if a.e_clinica and current_user.papel_clinica != "admin":
        flash("A assinatura da clínica é gerenciada pelo administrador dela.", "erro")
        return redirect(url_for("minha_assinatura"))
    opcoes = planos_ativos("clinica" if a.e_clinica else "autonomo")
    if request.method == "POST":
        f = request.form
        novo = next((p for p in opcoes if p.codigo == f.get("plano")), None)
        if not novo:
            flash("Escolha um plano.", "erro")
        else:
            contratar(a, novo, f.get("ciclo"), para_int(f.get("assentos"), 1, 1, 500), f.get("metodo"))
            flash(f"Assinatura do plano {novo.nome} confirmada (pagamento simulado). Obrigado!", "ok")
            return redirect(url_for("minha_assinatura"))
    return render_template("t_contratar.html", a=a, opcoes=opcoes, escolhido=request.args.get("plano") or a.plano.codigo)


@app.route("/t/assinatura/pagar/<int:cid>", methods=["POST"])
@exige("terapeuta")
def pagar_cobranca(cid):
    a = assinatura_da_conta(current_user)
    c = db.session.get(Cobranca, cid)
    if not c or c.assinatura_id != a.id or c.status != "pendente":
        abort(404)
    pagar(c, request.form.get("metodo"))
    flash("Pagamento confirmado (simulação).", "ok")
    return redirect(url_for("minha_assinatura"))


@app.route("/t/assinatura/cancelar", methods=["POST"])
@exige("terapeuta")
def cancelar_assinatura():
    a = assinatura_da_conta(current_user)
    if a.e_clinica and current_user.papel_clinica != "admin":
        abort(403)
    a.status, a.cancelada_em, a.proxima_cobranca = "cancelada", hoje(), None
    Cobranca.query.filter_by(assinatura_id=a.id, status="pendente").update({"status": "cancelada"})
    db.session.commit()
    flash("Assinatura cancelada. Seus dados continuam guardados e podem ser exportados em Minha conta.", "aviso")
    return redirect(url_for("minha_assinatura"))


# ============================================================ clínica
@app.route("/t/clinica")
@exige("terapeuta")
def minha_clinica():
    if not current_user.clinica_id:
        return render_template("t_clinica.html", c=None)
    c = db.session.get(Clinica, current_user.clinica_id)
    a = assinatura_da_conta(current_user)
    ini = datetime.combine(date(hoje().year, hoje().month, 1), datetime.min.time())
    from app import Consulta
    equipe = []
    for m in c.membros:
        equipe.append({"t": m, "pacientes": Paciente.query.filter_by(terapeuta_id=m.id, status="ativo").count(),
                       "sessoes": Consulta.query.filter_by(terapeuta_id=m.id, status="realizada").filter(Consulta.inicio >= ini).count(),
                       "minutos": round((db.session.query(func.coalesce(func.sum(Transcricao.segundos), 0))
                                         .filter(Transcricao.terapeuta_id == m.id, Transcricao.criado_em >= ini).scalar() or 0) / 60)})
    link = url_for("cadastro", clinica=c.convite_token, _external=True) if current_user.papel_clinica == "admin" and c.convite_token else None
    return render_template("t_clinica.html", c=c, a=a, equipe=equipe, link=link)


@app.route("/t/clinica/criar", methods=["POST"])
@exige("terapeuta")
def criar_clinica():
    if current_user.clinica_id:
        return redirect(url_for("minha_clinica"))
    nome = request.form.get("nome", "").strip()[:100]
    if not nome:
        flash("Informe o nome da clínica.", "erro")
        return redirect(url_for("minha_clinica"))
    a = assinatura_da_conta(current_user)
    c = Clinica(nome=nome, convite_token=secrets.token_urlsafe(16))
    db.session.add(c)
    db.session.flush()
    current_user.clinica_id, current_user.papel_clinica = c.id, "admin"
    p = plano("clinica")
    a.terapeuta_id, a.clinica_id, a.plano_id = None, c.id, p.id
    a.assentos = max(a.assentos or 1, p.minimo_terapeutas or 1)
    db.session.commit()
    flash(f"Clínica {nome} criada. Convide sua equipe pelo link abaixo.", "ok")
    return redirect(url_for("minha_clinica"))


@app.route("/t/clinica/convite", methods=["POST"])
@exige("terapeuta")
def novo_convite_clinica():
    if current_user.papel_clinica != "admin":
        abort(403)
    c = db.session.get(Clinica, current_user.clinica_id)
    c.convite_token = secrets.token_urlsafe(16)
    db.session.commit()
    flash("Novo link de convite gerado. O anterior deixou de valer.", "ok")
    return redirect(url_for("minha_clinica"))


@app.route("/t/clinica/remover/<int:tid>", methods=["POST"])
@exige("terapeuta")
def remover_da_clinica(tid):
    m = db.session.get(Terapeuta, tid)
    if current_user.papel_clinica != "admin" or not m or m.clinica_id != current_user.clinica_id or m.id == current_user.id:
        abort(403)
    m.clinica_id, m.papel_clinica = None, None
    db.session.add(Assinatura(terapeuta_id=m.id, plano_id=plano("profissional").id, status="teste",
                              teste_ate=hoje() + timedelta(days=DIAS_TESTE)))
    db.session.commit()
    flash(f"{m.nome} saiu da clínica. Os pacientes dela continuam com ela, numa conta própria em teste.", "ok")
    return redirect(url_for("minha_clinica"))


# ============================================================ painel da plataforma (dono do app)
def so_admin():
    if not current_user.is_authenticated or not e_admin(current_user):
        abort(404)


def todas_assinaturas():
    lista = Assinatura.query.all()
    for a in lista:
        atualizar(a)
    return lista


@app.route("/admin")
@login_required
def admin_painel():
    so_admin()
    lista = todas_assinaturas()
    pagantes = [a for a in lista if a.status in ("ativa", "atrasada")]
    mrr = sum(a.valor_mensal() for a in pagantes)
    ini30 = hoje() - timedelta(days=30)
    cancel30 = [a for a in lista if a.status == "cancelada" and a.cancelada_em and a.cancelada_em >= ini30]
    testes_encerrados = [a for a in lista if a.inicio_pago or a.status == "expirada"]
    convertidas = [a for a in testes_encerrados if a.inicio_pago]
    # receita recebida por mês (6 meses)
    serie = []
    d = date(hoje().year, hoje().month, 1)
    for _ in range(6):
        fim = somar_meses(d, 1)
        total = (db.session.query(func.coalesce(func.sum(Cobranca.valor), 0))
                 .filter(Cobranca.status == "paga", Cobranca.pago_em >= d, Cobranca.pago_em < fim).scalar())
        serie.append({"rotulo": MESES[d.month - 1][:3], "valor": float(total or 0)})
        d = somar_meses(d, -1)
    serie.reverse()
    filtro = request.args.get("status", "")
    mostrar = [a for a in lista if not filtro or a.status == filtro]
    mostrar.sort(key=lambda a: ({"atrasada": 0, "teste": 1, "ativa": 2, "expirada": 3, "cortesia": 4, "cancelada": 5}.get(a.status, 9), a.nome_conta))
    em_aberto = sum(c.valor for c in Cobranca.query.filter_by(status="pendente").filter(Cobranca.vencimento < hoje()))
    return render_template(
        "a_admin.html", lista=mostrar, filtro=filtro, mrr=mrr, arr=mrr * 12,
        n={k: sum(1 for a in lista if a.status == k) for k in STATUS},
        autonomos=sum(1 for a in pagantes if not a.e_clinica), clinicas=sum(1 for a in pagantes if a.e_clinica),
        terapeutas_pagantes=sum(a.assentos_cobrados for a in pagantes),
        ticket=mrr / len(pagantes) if pagantes else 0,
        churn=round(len(cancel30) * 100 / max(1, len(pagantes) + len(cancel30)), 1),
        conversao=round(len(convertidas) * 100 / len(testes_encerrados)) if testes_encerrados else None,
        serie=serie, maior=max([1] + [x["valor"] for x in serie]), em_aberto=em_aberto,
        tem_demo=Terapeuta.query.filter_by(demo_plataforma=True).first() is not None)


@app.route("/admin/conta/<int:aid>", methods=["GET", "POST"])
@login_required
def admin_conta(aid):
    so_admin()
    a = db.session.get(Assinatura, aid) or abort(404)
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "estender":
            base = max(a.teste_ate or hoje(), hoje())
            a.status, a.teste_ate = "teste", base + timedelta(days=para_int(request.form.get("dias"), 14, 1, 365))
            flash("Teste estendido.", "ok")
        elif acao == "plano":
            p = db.session.get(Plano, para_int(request.form.get("plano_id"), 0))
            if p:
                a.plano_id = p.id
                flash(f"Plano alterado para {p.nome}.", "ok")
        elif acao == "cortesia":
            a.status = "cortesia"
            flash("Conta marcada como cortesia (sem cobrança).", "ok")
        elif acao == "ativar":
            a.status, a.inicio_pago = "ativa", a.inicio_pago or hoje()
            a.proxima_cobranca = a.proxima_cobranca or somar_meses(hoje(), 1)
            flash("Assinatura ativada.", "ok")
        elif acao == "cancelar":
            a.status, a.cancelada_em, a.proxima_cobranca = "cancelada", hoje(), None
            flash("Assinatura cancelada.", "aviso")
        elif acao == "pagar":
            c = db.session.get(Cobranca, para_int(request.form.get("cobranca"), 0))
            if c and c.assinatura_id == a.id and c.status == "pendente":
                db.session.commit()
                pagar(c, "pix")
                flash("Cobrança marcada como paga.", "ok")
        db.session.commit()
        return redirect(url_for("admin_conta", aid=a.id))
    dono = a.dono
    return render_template("a_conta.html", a=atualizar(a), s=situacao(a), dono=dono, u=uso(dono, a) if dono else None,
                           cobrancas=Cobranca.query.filter_by(assinatura_id=a.id).order_by(Cobranca.vencimento.desc()).all(),
                           planos=Plano.query.order_by(Plano.ordem).all())


@app.route("/admin/planos", methods=["GET", "POST"])
@login_required
def admin_planos():
    so_admin()
    if request.method == "POST":
        for p in Plano.query.all():
            pre = f"p{p.id}_"
            if request.form.get(pre + "nome") is None:
                continue
            p.nome = request.form.get(pre + "nome", p.nome).strip()[:60] or p.nome
            p.preco_mensal = para_float(request.form.get(pre + "preco"), p.preco_mensal)
            p.meses_gratis_anual = para_int(request.form.get(pre + "gratis"), p.meses_gratis_anual, 0, 11)
            lim = request.form.get(pre + "limite", "").strip()
            p.limite_pacientes = para_int(lim, None, 1, 100000) if lim else None
            p.minutos_ia = para_int(request.form.get(pre + "minutos"), p.minutos_ia, 0, 100000)
            p.minimo_terapeutas = para_int(request.form.get(pre + "minimo"), p.minimo_terapeutas, 1, 1000)
            p.recursos = request.form.get(pre + "recursos", p.recursos)
            p.ativo = request.form.get(pre + "ativo") == "1"
            p.destaque = request.form.get(pre + "destaque") == "1"
        db.session.commit()
        flash("Planos atualizados. Os novos valores valem para as próximas cobranças.", "ok")
        return redirect(url_for("admin_planos"))
    return render_template("a_planos.html", planos=Plano.query.order_by(Plano.ordem).all())


@app.route("/admin/simulador")
@login_required
def admin_simulador():
    so_admin()
    g = request.args
    pa, pc = plano("profissional"), plano("clinica")
    e = {
        "preco_autonomo": para_float(g.get("preco_autonomo"), pa.preco_mensal if pa else 149.0),
        "preco_terapeuta": para_float(g.get("preco_terapeuta"), pc.preco_mensal if pc else 119.0),
        "testes_autonomos": para_int(g.get("testes_autonomos"), 20, 0, 100000),
        "testes_clinicas": para_int(g.get("testes_clinicas"), 3, 0, 10000),
        "conversao": para_float(g.get("conversao"), 35.0),
        "terapeutas_clinica": para_int(g.get("terapeutas_clinica"), 4, 1, 500),
        "churn": para_float(g.get("churn"), 3.0),
        "taxa_pagamento": para_float(g.get("taxa_pagamento"), 4.0),
        "impostos": para_float(g.get("impostos"), 6.0),
        "custo_terapeuta": para_float(g.get("custo_terapeuta"), 12.0),
        "custo_fixo": para_float(g.get("custo_fixo"), 250.0),
        "meses": para_int(g.get("meses"), 24, 6, 60),
    }
    aut = cli = 0.0
    linhas, acumulado, equilibrio = [], 0.0, None
    for mes in range(1, e["meses"] + 1):
        aut = aut * (1 - e["churn"] / 100) + e["testes_autonomos"] * e["conversao"] / 100
        cli = cli * (1 - e["churn"] / 100) + e["testes_clinicas"] * e["conversao"] / 100
        terapeutas = aut + cli * e["terapeutas_clinica"]
        mrr = aut * e["preco_autonomo"] + cli * e["terapeutas_clinica"] * e["preco_terapeuta"]
        liquido = mrr * (1 - (e["taxa_pagamento"] + e["impostos"]) / 100) - terapeutas * e["custo_terapeuta"] - e["custo_fixo"]
        acumulado += liquido
        if equilibrio is None and acumulado >= 0 and mes > 1:
            equilibrio = mes
        linhas.append({"mes": mes, "autonomos": round(aut), "clinicas": round(cli), "terapeutas": round(terapeutas),
                       "mrr": mrr, "liquido": liquido, "acumulado": acumulado})
    return render_template("a_simulador.html", e=e, linhas=linhas, equilibrio=equilibrio,
                           maior=max([1] + [x["mrr"] for x in linhas]))


# ---------------------------------------------------------------- contas fictícias para demonstrar a revenda
NOMES_DEMO = ["Alice", "Beatriz", "Caio", "Daniela", "Eduardo", "Flávia", "Gustavo", "Helena", "Igor", "Júlia",
              "Lucas", "Marina", "Nina", "Otávio", "Paula", "Rafael", "Sofia", "Tiago", "Vera", "Yara"]
CLINICAS_DEMO = [("Clínica Serena · demo", 5, "ativa", "anual"), ("Espaço Raiz · demo", 3, "ativa", "mensal"),
                 ("Instituto Leveza · demo", 4, "teste", "mensal"), ("Casa Aurora · demo", 6, "atrasada", "mensal")]


@app.route("/admin/demo/carregar", methods=["POST"])
@login_required
def admin_demo_carregar():
    so_admin()
    if Terapeuta.query.filter_by(demo_plataforma=True).first():
        flash("As contas de demonstração já estão carregadas.", "aviso")
        return redirect(url_for("admin_painel"))
    import random
    rnd = random.Random(7)
    semear_planos()
    n = 0

    def novo_terapeuta(nome):
        nonlocal n
        n += 1
        t = Terapeuta(nome=nome, email=f"conta{n:03d}@demo.equilibra.invalid", demo_plataforma=True,
                      senha_hash=generate_password_hash(secrets.token_urlsafe(32)))  # sem senha conhecida: não entra
        db.session.add(t)
        db.session.flush()
        return t

    def historico(a, meses_pagos, atrasada=False):
        a.inicio_pago = somar_meses(hoje(), -meses_pagos)
        a.criada_em = a.inicio_pago - timedelta(days=DIAS_TESTE)
        db.session.flush()
        passo = 12 if a.ciclo == "anual" else 1
        venc = a.inicio_pago
        while venc <= hoje():
            pago = not (atrasada and somar_meses(venc, passo) > hoje())
            db.session.add(Cobranca(assinatura_id=a.id, valor=a.valor_ciclo(), vencimento=venc, status="paga" if pago else "pendente",
                                    pago_em=venc + timedelta(days=rnd.randint(0, 2)) if pago else None, metodo=rnd.choice(list(METODOS))))
            venc = somar_meses(venc, passo)
        a.proxima_cobranca = venc

    nomes = iter(NOMES_DEMO)
    perfis = [("profissional", "ativa", 6), ("profissional", "ativa", 4), ("essencial", "ativa", 5), ("profissional", "ativa", 2),
              ("essencial", "ativa", 1), ("profissional", "atrasada", 3), ("essencial", "teste", 0), ("profissional", "teste", 0),
              ("profissional", "expirada", 0), ("essencial", "cancelada", 2)]
    for cod, status, meses in perfis:
        t = novo_terapeuta(next(nomes) + " · demo")
        a = Assinatura(terapeuta_id=t.id, plano_id=plano(cod).id, status="ativa" if status in ("ativa", "atrasada") else status,
                       ciclo="anual" if meses == 6 else "mensal")
        db.session.add(a)
        db.session.flush()
        if status in ("ativa", "atrasada", "cancelada"):
            historico(a, meses, atrasada=(status == "atrasada"))
        if status == "teste":
            a.criada_em, a.teste_ate = hoje() - timedelta(days=rnd.randint(2, 9)), hoje() + timedelta(days=rnd.randint(3, 11))
        if status == "expirada":
            a.criada_em, a.teste_ate = hoje() - timedelta(days=20), hoje() - timedelta(days=6)
        if status == "cancelada":
            a.status, a.cancelada_em, a.proxima_cobranca = "cancelada", hoje() - timedelta(days=12), None
    for nome, equipe, status, ciclo in CLINICAS_DEMO:
        c = Clinica(nome=nome, convite_token=secrets.token_urlsafe(16), demo_plataforma=True)
        db.session.add(c)
        db.session.flush()
        for i in range(equipe):
            t = novo_terapeuta(next(nomes, f"Terapeuta {n + 1}") + " · demo")
            t.clinica_id, t.papel_clinica = c.id, "admin" if i == 0 else "membro"
        a = Assinatura(clinica_id=c.id, plano_id=plano("clinica").id, status="ativa" if status != "teste" else "teste",
                       ciclo=ciclo, assentos=equipe)
        db.session.add(a)
        db.session.flush()
        if status == "teste":
            a.criada_em, a.teste_ate = hoje() - timedelta(days=4), hoje() + timedelta(days=10)
        else:
            historico(a, {"anual": 8, "mensal": 5}[ciclo] if status == "ativa" else 3, atrasada=(status == "atrasada"))
    db.session.commit()
    for a in Assinatura.query.all():
        atualizar(a)
    flash("Contas fictícias de terapeutas e clínicas carregadas, com histórico de cobranças.", "ok")
    return redirect(url_for("admin_painel"))


@app.route("/admin/demo/apagar", methods=["POST"])
@login_required
def admin_demo_apagar():
    so_admin()
    ts = Terapeuta.query.filter_by(demo_plataforma=True).all()
    ids = [t.id for t in ts]
    cids = [c.id for c in Clinica.query.filter_by(demo_plataforma=True)]
    ass = Assinatura.query.filter((Assinatura.terapeuta_id.in_(ids)) | (Assinatura.clinica_id.in_(cids))).all() if ids or cids else []
    aids = [a.id for a in ass]
    if aids:
        Cobranca.query.filter(Cobranca.assinatura_id.in_(aids)).delete(synchronize_session=False)
        Assinatura.query.filter(Assinatura.id.in_(aids)).delete(synchronize_session=False)
    if ids:
        Terapeuta.query.filter(Terapeuta.id.in_(ids)).delete(synchronize_session=False)
    if cids:
        Clinica.query.filter(Clinica.id.in_(cids)).delete(synchronize_session=False)
    db.session.commit()
    flash("Contas de demonstração da plataforma apagadas.", "ok")
    return redirect(url_for("admin_painel"))
