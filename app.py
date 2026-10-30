"""
Equilibra — acompanhamento holístico em dependência química.
Flask + PWA (no iPhone: Safari > Compartilhar > Adicionar à Tela de Início).

Configuração por variáveis de ambiente (nunca coloque chaves no código):
  SECRET_KEY          obrigatória em produção
  DATABASE_URL        opcional (padrão: SQLite local)
  CODIGO_CADASTRO     opcional; se definido, é exigido para cadastrar terapeutas
  ANTHROPIC_API_KEY   opcional; ativa resumos e feedback clínico com IA
  ANTHROPIC_MODEL     opcional; modelo usado pela IA
  OPENAI_API_KEY      opcional; ativa a transcrição de áudio (ver voz.py)
  MODO_AVALIACAO      1 = simula transcrição e IA, sem chamar nenhuma API paga
"""
import json
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup, escape
from sqlalchemy import func
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import voz
from cripto import TextoCifrado, cifrar

TZ = ZoneInfo("America/Sao_Paulo")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEV = os.environ.get("FLASK_ENV") == "development"

# Todos os arquivos ficam numa pasta só (sem subpastas), para o envio pelo GitHub não desmontar a estrutura.
app = Flask(__name__, template_folder=BASE_DIR, static_folder=None)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "equilibra.db"))
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=not DEV,
    REMEMBER_COOKIE_DURATION=timedelta(days=30),
    REMEMBER_COOKIE_SECURE=not DEV,
    MAX_CONTENT_LENGTH=26 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "entrar"
login_manager.login_message = "Entre para continuar."


def agora():
    return datetime.now(TZ).replace(tzinfo=None)


def hoje():
    return agora().date()


def para_data(txt):
    try:
        return date.fromisoformat(txt) if txt else None
    except ValueError:
        return None


def para_int(txt, padrao=None, minimo=None, maximo=None):
    try:
        v = int(txt)
    except (TypeError, ValueError):
        return padrao
    if minimo is not None:
        v = max(minimo, v)
    if maximo is not None:
        v = min(maximo, v)
    return v


def para_float(txt, padrao=None):
    try:
        return float(str(txt).replace(",", "."))
    except (TypeError, ValueError):
        return padrao


# ============================================================ constantes
VERSAO = "v9.5"
# Arquivos que precisam estar na mesma pasta do app.py. Se faltar algum, o painel avisa.
ARQUIVOS_ESSENCIAIS = ['_icones.html', '_itens.html', '_marca.html', 'a_admin.html', 'a_conta.html', 'a_planos.html', 'a_simulador.html', 'ajuda.html', 'app.js', 'app.py', 'apple-touch-icon.png', 'artigo.html', 'base.html', 'biblioteca.html', 'boas_vindas.html', 'c_codigo.html', 'c_codigos.html', 'c_esqueci.html', 'c_paciente.html', 'c_privacidade.html', 'c_redefinir.html', 'c_terapeuta.html', 'c_termos.html', 'cadastro.html', 'conta.py', 'conteudo_base.py', 'convite.html', 'cripto.py', 'demo.py', 'entrar.html', 'erro.html', 'financeiro.py', 'icon-192.png', 'icon-512.png', 'licenca.py', 'manifest.webmanifest', 'offline.html', 'p_casa.html', 'p_checkin.html', 'p_diario.html', 'planos.html', 'plataforma.py', 'relatorios.py', 'respirar.html', 'style.css', 'sw.js', 't__indicadores.html', 't_agenda.html', 't_artigo_form.html', 't_assinatura.html', 't_clinica.html', 't_consulta_form.html', 't_contratar.html', 't_fim.html', 't_financeiro.html', 't_gravacao.html', 't_mood.html', 't_paciente.html', 't_paciente_form.html', 't_pacientes.html', 't_painel.html', 't_recibo.html', 't_registro.html', 't_registro_form.html', 't_registros.html', 't_relatorio.html', 't_relatorio_opcoes.html', 't_relatorio_paciente.html', 'voz.py']


def arquivos_faltando():
    return [f for f in ARQUIVOS_ESSENCIAIS if not os.path.exists(os.path.join(BASE_DIR, f))]  # aumente a cada entrega; aparece no rodapé do app
HUMOR = {1: ("😞", "Muito mal"), 2: ("😔", "Mal"), 3: ("😐", "Regular"), 4: ("🙂", "Bem"), 5: ("😊", "Muito bem")}
RISCO = {"baixo": "Baixo", "moderado": "Moderado", "alto": "Alto", "critico": "Crítico"}
STATUS_PACIENTE = {"ativo": "Ativo", "pausado": "Pausado", "alta": "Alta", "inativo": "Inativo"}
STATUS_CONSULTA = {"agendada": "Agendada", "realizada": "Realizada", "faltou": "Faltou", "cancelada": "Cancelada"}
TIPO_CONSULTA = {"individual": "Individual", "familiar": "Familiar", "grupo": "Grupo", "online": "Online"}
RESULTADO_TESTE = {"negativo": "Negativo", "positivo": "Positivo", "inconclusivo": "Inconclusivo"}
TIPOS_TESTE = ["Multi 1", "Multi 2", "Multi 3", "Multi 6", "Multi 9", "Multi 12"]
# Indicadores pós-sessão (0 a 10). positivo=True quando um valor mais alto é melhor.
INDICADORES = [
    ("ansiedade", "Ansiedade", False),
    ("motivacao", "Motivação", True),
    ("fissura", "Fissura", False),
    ("tristeza", "Tristeza", False),
    ("irritabilidade", "Irritabilidade", False),
    ("sono", "Qualidade do sono", True),
    ("energia", "Energia e disposição", True),
    ("abstinencia", "Sintomas físicos de abstinência", False),
    ("isolamento", "Isolamento social", False),
    ("autoestima", "Autoestima", True),
]
CAMPOS_INDICADORES = [c for c, _, _ in INDICADORES]
SUBSTANCIAS = ["Álcool", "Tabaco/nicotina", "Maconha", "Cocaína", "Crack", "Benzodiazepínicos",
               "Opioides", "Anfetaminas", "Ecstasy/MDMA", "Inalantes", "Jogo", "Outra"]
GATILHOS = ["Estresse", "Solidão", "Tédio", "Raiva", "Tristeza", "Cansaço", "Festa ou evento",
            "Pessoas específicas", "Dinheiro na mão", "Conflito familiar", "Dor física"]
CATEGORIAS = {"substancia": "Substâncias", "recuperacao": "Recuperação", "pratica": "Práticas"}
MARCOS = [(1, "24 horas"), (30, "1 mês"), (60, "2 meses"), (90, "3 meses"), (120, "4 meses"),
          (180, "6 meses"), (270, "9 meses"), (365, "1 ano"), (548, "18 meses"), (730, "2 anos"),
          (1095, "3 anos"), (1825, "5 anos"), (3650, "10 anos")]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
DIAS_LONGOS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


# ============================================================ modelos
class Terapeuta(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    estoque_testes = db.Column(db.Integer, default=0)
    estoque_minimo = db.Column(db.Integer, default=10)
    registro_prof = db.Column(db.String(60))   # ex.: registro em associação profissional
    cidade = db.Column(db.String(80))
    telefone = db.Column(db.String(30))
    totp_segredo = db.Column(TextoCifrado)
    totp_ativo = db.Column(db.Boolean, default=False)
    codigos_recuperacao = db.Column(db.Text)
    clinica_id = db.Column(db.Integer, index=True)       # preenchido quando o terapeuta faz parte de uma clínica
    papel_clinica = db.Column(db.String(10))            # admin | membro
    demo_plataforma = db.Column(db.Boolean, default=False)  # conta fictícia do painel da plataforma
    criado_em = db.Column(db.DateTime, default=agora)
    papel = "terapeuta"

    def get_id(self):
        return f"t-{self.id}"


class Paciente(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    nascimento = db.Column(db.Date)
    telefone = db.Column(db.String(30))
    email = db.Column(db.String(160), unique=True)
    substancias = db.Column(db.String(300))
    tipo_teste = db.Column(db.String(12))  # Multi 1 … Multi 12, ou "nenhum"
    tempo_uso = db.Column(db.String(60))
    status = db.Column(db.String(12), default="ativo")
    inicio_tratamento = db.Column(db.Date)
    ultimo_uso = db.Column(db.Date)
    sessoes_semana = db.Column(db.Integer, default=1)
    valor_sessao = db.Column(db.Float)
    horario_pref = db.Column(db.String(80))
    emergencia_nome = db.Column(db.String(80))
    emergencia_tel = db.Column(db.String(30))
    anamnese = db.Column(TextoCifrado)
    senha_hash = db.Column(db.String(256))
    codigo_convite = db.Column(db.String(40), unique=True)
    criado_em = db.Column(db.DateTime, default=agora)
    terapeuta = db.relationship("Terapeuta", backref="pacientes")
    papel = "paciente"

    def get_id(self):
        return f"p-{self.id}"

    @property
    def lista_substancias(self):
        return [s for s in (self.substancias or "").split("|") if s]

    @property
    def inicial(self):
        return (self.nome or "?")[0].upper()

    @property
    def tem_acesso(self):
        return bool(self.senha_hash)

    def registrar_uso(self, dia):
        if dia and (not self.ultimo_uso or dia > self.ultimo_uso):
            self.ultimo_uso = dia

    @property
    def dias_limpo(self):
        return (hoje() - self.ultimo_uso).days if self.ultimo_uso else None

    def conquistas(self):
        d = self.dias_limpo
        if d is None:
            return [], None
        feitas = [rot for n, rot in MARCOS if d >= n]
        prox = next(((n - d, rot) for n, rot in MARCOS if d < n), None)
        return feitas, prox

    def saldo_sessoes(self):
        compradas = db.session.query(func.coalesce(func.sum(Pagamento.sessoes), 0)).filter_by(paciente_id=self.id).scalar()
        realizadas = Consulta.query.filter_by(paciente_id=self.id, status="realizada").count()
        return int(compradas) - realizadas


def definir_senha(u, senha):
    u.senha_hash = generate_password_hash(senha)


def conferir_senha(u, senha):
    return bool(u and u.senha_hash) and check_password_hash(u.senha_hash, senha)


class Consulta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    inicio = db.Column(db.DateTime, nullable=False)
    duracao = db.Column(db.Integer, default=50)
    tipo = db.Column(db.String(20), default="individual")
    status = db.Column(db.String(20), default="agendada")
    notas_pre = db.Column(TextoCifrado)
    checkin_em = db.Column(db.DateTime)    # início real do atendimento
    checkout_em = db.Column(db.DateTime)   # fim real do atendimento
    paciente = db.relationship("Paciente")
    registro = db.relationship("Registro", uselist=False, back_populates="consulta")

    @property
    def em_atendimento(self):
        return bool(self.checkin_em and not self.checkout_em)

    @property
    def minutos_atendidos(self):
        if self.checkin_em and self.checkout_em and self.checkout_em > self.checkin_em:
            return round((self.checkout_em - self.checkin_em).total_seconds() / 60)
        return None


class Registro(db.Model):
    """Registro pós-sessão (prontuário). Só o terapeuta vê, exceto 'tarefa_paciente'."""
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consulta.id"))
    data = db.Column(db.Date, default=hoje, nullable=False)
    realizada = db.Column(db.Boolean, default=True)
    humor = db.Column(db.Integer)          # 1–5
    ansiedade = db.Column(db.Integer)      # 0–10
    motivacao = db.Column(db.Integer)      # 0–10
    fissura = db.Column(db.Integer)        # 0–10
    uso_recente = db.Column(db.Boolean, default=False)
    data_uso = db.Column(db.Date)
    teste_feito = db.Column(db.Boolean, default=False)
    teste_resultado = db.Column(db.String(15))
    teste_tipo = db.Column(db.String(12))
    tristeza = db.Column(db.Integer)
    irritabilidade = db.Column(db.Integer)
    sono = db.Column(db.Integer)
    energia = db.Column(db.Integer)
    abstinencia = db.Column(db.Integer)
    isolamento = db.Column(db.Integer)
    autoestima = db.Column(db.Integer)
    risco = db.Column(db.String(10), default="baixo")
    abordagens = db.Column(db.String(200))
    comentarios = db.Column(TextoCifrado)
    tarefa_paciente = db.Column(db.String(300))
    feedback_ia = db.Column(TextoCifrado)
    criado_em = db.Column(db.DateTime, default=agora)
    paciente = db.relationship("Paciente")
    consulta = db.relationship("Consulta", back_populates="registro")


class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, default=hoje)
    humor = db.Column(db.Integer, nullable=False)
    fissura = db.Column(db.Integer, nullable=False)
    sono = db.Column(db.Integer)
    usou = db.Column(db.Boolean, default=False)
    gatilhos = db.Column(db.String(300))
    nota = db.Column(TextoCifrado)
    paciente = db.relationship("Paciente")
    __table_args__ = (db.UniqueConstraint("paciente_id", "data"),)


class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    data = db.Column(db.Date, default=hoje)
    valor = db.Column(db.Float, nullable=False)
    sessoes = db.Column(db.Integer, default=1)
    nota = db.Column(db.String(200))
    forma = db.Column(db.String(15))  # pix | dinheiro | cartao | transferencia | outro
    paciente = db.relationship("Paciente")


class Consentimento(db.Model):
    """Termo de consentimento para gravação de sessões."""
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False)
    assinado_em = db.Column(db.Date, nullable=False)
    versao = db.Column(db.String(40))
    arquivo = db.Column(db.LargeBinary)
    arquivo_tipo = db.Column(db.String(80))
    arquivo_nome = db.Column(db.String(120))
    revogado_em = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=agora)


class Transcricao(db.Model):
    """Texto transcrito de uma gravação. O áudio em si nunca é guardado."""
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False, index=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consulta.id"))
    registro_id = db.Column(db.Integer, db.ForeignKey("registro.id"))
    tipo = db.Column(db.String(10), nullable=False)  # resumo | consulta
    status = db.Column(db.String(12), default="gravando")  # gravando | transcrita | pronta | revisada | erro
    texto = db.Column(TextoCifrado, default="")
    texto_original = db.Column(TextoCifrado)  # transcrição como saiu, antes das correções do terapeuta
    partes = db.Column(db.Integer, default=0)
    falhas = db.Column(db.Integer, default=0)
    segundos = db.Column(db.Integer, default=0)
    sugestao = db.Column(TextoCifrado)  # JSON gerado pela IA
    erro = db.Column(db.String(300))
    criado_em = db.Column(db.DateTime, default=agora)
    paciente = db.relationship("Paciente")
    consulta = db.relationship("Consulta")

    @property
    def dados(self):
        try:
            return json.loads(self.sugestao) if self.sugestao else {}
        except ValueError:
            return {}


def consentimento_ativo(p):
    return (Consentimento.query.filter_by(paciente_id=p.id, revogado_em=None)
            .order_by(Consentimento.assinado_em.desc()).first())


class EstoqueTeste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    tipo = db.Column(db.String(12), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    minimo = db.Column(db.Integer, default=5)
    __table_args__ = (db.UniqueConstraint("terapeuta_id", "tipo"),)


def estoques(terapeuta):
    """Um registro por tipo de teste, criado na primeira vez."""
    atuais = {e.tipo: e for e in EstoqueTeste.query.filter_by(terapeuta_id=terapeuta.id)}
    novos = False
    for tipo in TIPOS_TESTE:
        if tipo not in atuais:
            atuais[tipo] = EstoqueTeste(terapeuta_id=terapeuta.id, tipo=tipo, quantidade=0, minimo=5)
            db.session.add(atuais[tipo])
            novos = True
    if novos:
        db.session.commit()
    return [atuais[t] for t in TIPOS_TESTE]


class DemoItem(db.Model):
    """Anota o que foi criado pelos dados de demonstração, para apagar depois."""
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)
    ref_id = db.Column(db.Integer, nullable=False)


class Artigo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"))  # None = conteúdo base
    categoria = db.Column(db.String(30), nullable=False)
    titulo = db.Column(db.String(140), nullable=False)
    resumo = db.Column(db.String(300))
    corpo = db.Column(db.Text, nullable=False)
    publicado = db.Column(db.Boolean, default=True)


@login_manager.user_loader
def carregar_usuario(uid):
    try:
        tipo, num = uid.split("-", 1)
        num = int(num)
    except ValueError:
        return None
    if tipo == "t":
        return db.session.get(Terapeuta, num)
    p = db.session.get(Paciente, num)
    if p and session.get("demo_como") == p.id:
        return p  # visualização de paciente demo pelo terapeuta
    return p if p and p.tem_acesso and p.status != "inativo" else None


# ============================================================ segurança
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


INATIVIDADE_MIN = int(os.environ.get("INATIVIDADE_MIN", "60"))  # terapeuta sai sozinho após este tempo parado


class Acesso(db.Model):
    """Registro de quem abriu dados de um paciente (exigência de boa prática da LGPD)."""
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), index=True)
    paciente_id = db.Column(db.Integer, index=True)
    acao = db.Column(db.String(40), nullable=False)
    quando = db.Column(db.DateTime, default=agora)
    ip = db.Column(db.String(64))
    aparelho = db.Column(db.String(120))


def registrar_acesso(paciente_id, acao):
    try:
        ua = request.headers.get("User-Agent", "")
        aparelho = "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Android" if "Android" in ua else \
                   "Mac" if "Macintosh" in ua else "Windows" if "Windows" in ua else (ua[:60] or "desconhecido")
        db.session.add(Acesso(terapeuta_id=current_user.id if current_user.papel == "terapeuta" else None,
                              paciente_id=paciente_id, acao=acao, ip=(request.remote_addr or "")[:64], aparelho=aparelho))
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.before_request
def controlar_inatividade():
    if request.endpoint in ("static", "service_worker", "manifest") or not current_user.is_authenticated:
        return
    if current_user.papel == "terapeuta" and not session.get("demo_como") and not teste_aberto():
        ultimo = session.get("ultimo_uso")
        if ultimo and datetime.now().timestamp() - ultimo > INATIVIDADE_MIN * 60:
            logout_user()
            session.clear()
            flash(f"Por segurança, você saiu após {INATIVIDADE_MIN} minutos sem uso. Entre de novo.", "aviso")
            return redirect(url_for("entrar"))
        session.permanent = True
        session["ultimo_uso"] = datetime.now().timestamp()


@app.before_request
def verificar_csrf():
    if request.method == "POST":
        enviado = request.form.get("_csrf", "")
        if not enviado or not secrets.compare_digest(enviado, session.get("_csrf", "")):
            abort(400)


@app.after_request
def cabecalhos(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if resp.mimetype == "text/html":
        resp.headers["Cache-Control"] = "no-store"
    return resp


def exige(papel):
    def deco(f):
        @wraps(f)
        @login_required
        def inner(*a, **kw):
            if current_user.papel != papel:
                abort(403)
            return f(*a, **kw)
        return inner
    return deco


def meu_paciente(pid):
    p = db.session.get(Paciente, pid)
    if not p or p.terapeuta_id != current_user.id:
        abort(404)
    return p


def minha_consulta(cid):
    c = db.session.get(Consulta, cid)
    if not c or c.terapeuta_id != current_user.id:
        abort(404)
    return c


def meu_registro(rid):
    r = db.session.get(Registro, rid)
    if not r or r.terapeuta_id != current_user.id:
        abort(404)
    return r


# ============================================================ filtros de template
@app.template_filter("data_br")
def data_br(d):
    return d.strftime("%d/%m/%Y") if d else ""


@app.template_filter("hora")
def hora(d):
    return d.strftime("%H:%M") if d else ""


@app.template_filter("dia_curto")
def dia_curto(d):
    return f"{DIAS[d.weekday()]}, {d.day} {MESES[d.month - 1][:3]}" if d else ""


@app.template_filter("dia_longo")
def dia_longo(d):
    return f"{DIAS_LONGOS[d.weekday()]}, {d.day} de {MESES[d.month - 1]}" if d else ""


@app.template_filter("moeda")
def moeda(v):
    if v is None:
        return ""
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("tempo")
def tempo_legivel(dias):
    if dias is None:
        return ""
    if dias < 30:
        return f"{dias} dia" + ("" if dias == 1 else "s")
    if dias < 365:
        m = dias // 30
        return f"{m} {'mês' if m == 1 else 'meses'}"
    a, m = dias // 365, (dias % 365) // 30
    txt = f"{a} ano" + ("" if a == 1 else "s")
    return txt + (f" e {m} {'mês' if m == 1 else 'meses'}" if m else "")


@app.template_filter("texto")
def texto(corpo):
    html, lista = [], False
    for linha in (corpo or "").splitlines():
        s = linha.strip()
        if s.startswith("- "):
            if not lista:
                html.append("<ul>")
                lista = True
            html.append(f"<li>{escape(s[2:])}</li>")
            continue
        if lista:
            html.append("</ul>")
            lista = False
        if s.startswith("## "):
            html.append(f"<h3>{escape(s[3:])}</h3>")
        elif s:
            html.append(f"<p>{escape(s)}</p>")
    if lista:
        html.append("</ul>")
    return Markup("\n".join(html))


@app.context_processor
def contexto():
    saudacao = "Bom dia" if agora().hour < 12 else "Boa tarde" if agora().hour < 18 else "Boa noite"
    return dict(csrf_token=csrf_token, HUMOR=HUMOR, RISCO=RISCO, STATUS_PACIENTE=STATUS_PACIENTE,
                STATUS_CONSULTA=STATUS_CONSULTA, TIPO_CONSULTA=TIPO_CONSULTA, CATEGORIAS=CATEGORIAS,
                RESULTADO_TESTE=RESULTADO_TESTE, TIPOS_TESTE=TIPOS_TESTE, INDICADORES=INDICADORES, SUBSTANCIAS=SUBSTANCIAS, GATILHOS=GATILHOS,
                hoje=hoje(), saudacao=saudacao, ia_ativa=voz.ia_ativa(), transcricao_ativa=voz.transcricao_ativa(),
                modo_avaliacao=voz.modo_avaliacao(), vendo_como=session.get("demo_como"), VERSAO=VERSAO,
                faltando=arquivos_faltando() if current_user.is_authenticated and current_user.papel == "terapeuta" else [])


# ============================================================ regras clínicas
def alertas(p):
    """Motivos para o paciente aparecer em 'Pacientes em atenção'."""
    motivos = []
    ultimo_reg = Registro.query.filter_by(paciente_id=p.id).order_by(Registro.data.desc(), Registro.id.desc()).first()
    if ultimo_reg and ultimo_reg.risco in ("alto", "critico"):
        motivos.append(f"Risco {RISCO[ultimo_reg.risco].lower()} na última sessão")
    recentes = CheckIn.query.filter_by(paciente_id=p.id).filter(CheckIn.data >= hoje() - timedelta(days=3)).all()
    if p.ultimo_uso and (hoje() - p.ultimo_uso).days <= 7:
        motivos.append("Uso registrado nos últimos 7 dias")
    if any(c.fissura >= 8 for c in recentes):
        motivos.append("Fissura muito alta no check-in")
    if any(c.humor == 1 for c in recentes):
        motivos.append("Humor muito baixo no check-in")
    if p.tem_acesso:
        ultimo = CheckIn.query.filter_by(paciente_id=p.id).order_by(CheckIn.data.desc()).first()
        if not ultimo or (hoje() - ultimo.data).days >= 5:
            motivos.append("Sem check-in há 5 dias ou mais")
    return motivos


def serie_diaria(pontos, dias=30):
    """pontos: lista (data, valor 0–10). Retorna polyline para SVG 300x80."""
    inicio = hoje() - timedelta(days=dias - 1)
    por_dia = {}
    for d, v in pontos:
        if d >= inicio and v is not None:
            por_dia.setdefault(d, []).append(v)
    saida = []
    for i in range(dias):
        d = inicio + timedelta(days=i)
        if d in por_dia:
            v = sum(por_dia[d]) / len(por_dia[d])
            saida.append(f"{round(i * 300 / (dias - 1), 1)},{round(76 - v * 7.2, 1)}")
    return " ".join(saida)


def feedback_ia(r):
    """Envia só dados clínicos, sem nome, telefone ou e-mail."""
    dados = {
        "substancias": r.paciente.lista_substancias, "dias_sem_uso": r.paciente.dias_limpo,
        "humor_1a5": r.humor,
        "indicadores_0a10": {rot: getattr(r, c) for c, rot, _ in INDICADORES if getattr(r, c) is not None},
        "uso_recente": r.uso_recente,
        "teste": f"{r.teste_tipo or ''} {r.teste_resultado or ''}".strip() if r.teste_feito else None,
        "risco": r.risco, "abordagens": r.abordagens,
        "observacoes": voz.anonimizar(r.comentarios or "", [r.paciente.nome]),
    }
    prompt = ("Você apoia um terapeuta holístico que atende pessoas em recuperação de dependência química. "
              "Com base no registro da sessão abaixo, escreva em português do Brasil, em até 180 palavras: "
              "1) uma leitura breve do momento do paciente; 2) pontos de atenção e sinais de risco; "
              "3) duas ou três sugestões para a próxima sessão. Não faça diagnóstico, não sugira medicamentos "
              "ou doses e indique encaminhamento médico ou psiquiátrico quando houver risco alto, "
              "sinais de abstinência grave ou ideação suicida.\n\nRegistro:\n" + json.dumps(dados, ensure_ascii=False))
    return voz.chamar_claude(prompt, max_tokens=700)


# ============================================================ PWA
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(BASE_DIR, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(BASE_DIR, "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


EXTENSOES_PUBLICAS = {".css", ".js", ".png", ".svg", ".ico", ".webmanifest"}


@app.route("/static/<path:filename>", endpoint="static")
def arquivo_estatico(filename):
    nome = os.path.basename(filename)  # aceita endereços antigos como /static/icons/icon-192.png
    if os.path.splitext(nome)[1].lower() not in EXTENSOES_PUBLICAS:
        abort(404)  # nunca expõe código (.py) nem telas (.html)
    resp = send_from_directory(BASE_DIR, nome)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/offline")
def offline():
    return render_template("offline.html")


# ============================================================ acesso
@app.route("/")
def inicio():
    if not current_user.is_authenticated:
        return redirect(url_for("entrar"))
    return redirect(url_for("painel" if current_user.papel == "terapeuta" else "casa"))


EMAIL_LOCAL = "local@equilibra.local"


def acesso_sem_senha():
    """Modo sem senha: só com ACESSO_SEM_SENHA=1 e só para quem acessa do próprio computador."""
    if os.environ.get("ACESSO_SEM_SENHA") != "1":
        return False
    orig = request.environ.get("werkzeug.proxy_fix.orig", {}).get("REMOTE_ADDR")  # ignora cabeçalhos de proxy
    ip = orig or request.environ.get("REMOTE_ADDR", "")
    return ip in ("127.0.0.1", "::1")


def teste_aberto():
    """Versão de teste online: entra só com o nome, uma conta por pessoa (MODO_TESTE_ABERTO=1)."""
    return os.environ.get("MODO_TESTE_ABERTO") == "1"


@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("inicio"))
    if teste_aberto() and not acesso_sem_senha():
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()[:80]
            if not nome:
                flash("Digite seu nome para começar.", "erro")
            else:
                import licenca
                t = Terapeuta(nome=nome, email=f"teste-{secrets.token_hex(6)}@equilibra.local")
                definir_senha(t, secrets.token_urlsafe(32))
                db.session.add(t)
                db.session.commit()
                licenca.apos_cadastro(t, {}, None)
                login_user(t, remember=True)  # volta direto nas próximas vezes, neste aparelho
                return redirect(url_for("painel"))
        return render_template("boas_vindas.html", teste=True)
    if acesso_sem_senha():
        t = Terapeuta.query.filter_by(email=EMAIL_LOCAL).first()
        if not t and request.method == "POST":
            nome = request.form.get("nome", "").strip()[:80]
            if not nome:
                flash("Digite seu nome para começar.", "erro")
            else:
                import licenca
                t = Terapeuta(nome=nome, email=EMAIL_LOCAL)
                definir_senha(t, secrets.token_urlsafe(32))  # senha aleatória: o acesso é só por este computador
                db.session.add(t)
                db.session.commit()
                licenca.apos_cadastro(t, {}, None)
        if t:
            login_user(t, remember=False)
            session["ultimo_uso"] = datetime.now().timestamp()
            return redirect(request.args.get("next") if (request.args.get("next") or "").startswith("/t") else url_for("painel"))
        return render_template("boas_vindas.html")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        u = Terapeuta.query.filter_by(email=email).first() or Paciente.query.filter_by(email=email).first()
        if conferir_senha(u, senha) and (u.papel == "terapeuta" or u.status != "inativo"):
            if u.papel == "terapeuta" and u.totp_ativo:
                session["2fa_pendente"] = u.id
                return redirect(url_for("entrar_codigo"))
            login_user(u, remember=(u.papel == "paciente"))
            session["ultimo_uso"] = datetime.now().timestamp()
            return redirect(url_for("inicio"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("entrar.html")


@app.route("/sair", methods=["POST"])
@login_required
def sair():
    logout_user()
    session.clear()
    return redirect(url_for("entrar"))


def email_em_uso(email, exceto=None):
    for modelo in (Terapeuta, Paciente):
        u = modelo.query.filter_by(email=email).first()
        if u and u is not exceto:
            return True
    return False


def validar_credenciais(email, senha, confirma, exceto=None):
    if "@" not in email or len(email) < 5:
        return "Informe um e-mail válido."
    if len(senha) < 8:
        return "A senha precisa ter pelo menos 8 caracteres."
    if senha != confirma:
        return "As senhas não conferem."
    if email_em_uso(email, exceto):
        return "Este e-mail já está cadastrado."
    return None


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    import licenca
    codigo = os.environ.get("CODIGO_CADASTRO")
    convite_clinica = licenca.ler_convite_clinica(request.values.get("clinica", ""))
    if convite_clinica:
        codigo = None  # convite de uma clínica dispensa o código de cadastro
    if request.method == "POST":
        f = request.form
        email = f.get("email", "").strip().lower()
        erro = validar_credenciais(email, f.get("senha", ""), f.get("confirma", ""))
        if not f.get("nome", "").strip():
            erro = "Informe seu nome."
        if codigo and not secrets.compare_digest(f.get("codigo", ""), codigo):
            erro = "Código de cadastro inválido."
        if not convite_clinica and f.get("tipo_conta") == "clinica" and not f.get("nome_clinica", "").strip():
            erro = "Informe o nome da clínica."
        if erro:
            flash(erro, "erro")
        else:
            t = Terapeuta(nome=f["nome"].strip()[:80], email=email)
            definir_senha(t, f["senha"])
            db.session.add(t)
            db.session.commit()
            licenca.apos_cadastro(t, f, convite_clinica)
            login_user(t, remember=False)
            session["ultimo_uso"] = datetime.now().timestamp()
            return redirect(url_for("painel"))
    return render_template("cadastro.html", exige_codigo=bool(codigo), convite_clinica=convite_clinica,
                           planos=licenca.planos_ativos(), plano_escolhido=request.values.get("plano", ""))


@app.route("/convite/<codigo>", methods=["GET", "POST"])
def convite(codigo):
    p = Paciente.query.filter_by(codigo_convite=codigo).first()
    if not p or p.tem_acesso:
        flash("Este convite já foi usado ou não existe. Peça um novo ao seu terapeuta.", "erro")
        return redirect(url_for("entrar"))
    if request.method == "POST":
        f = request.form
        email = f.get("email", "").strip().lower()
        erro = validar_credenciais(email, f.get("senha", ""), f.get("confirma", ""), exceto=p)
        if not f.get("aceite"):
            erro = "Para continuar, confirme que concorda com o uso dos dados no seu acompanhamento."
        if erro:
            flash(erro, "erro")
        else:
            p.email = email
            definir_senha(p, f["senha"])
            p.codigo_convite = None
            db.session.commit()
            login_user(p, remember=True)
            flash("Conta criada. Que bom ter você aqui.", "ok")
            return redirect(url_for("casa"))
    return render_template("convite.html", p=p)


# ============================================================ terapeuta: início
@app.route("/t")
@exige("terapeuta")
def painel():
    ini = datetime.combine(hoje(), datetime.min.time())
    consultas = (Consulta.query.filter_by(terapeuta_id=current_user.id)
                 .filter(Consulta.inicio >= ini, Consulta.inicio < ini + timedelta(days=1))
                 .filter(Consulta.status != "cancelada").order_by(Consulta.inicio).all())
    ativos = Paciente.query.filter_by(terapeuta_id=current_user.id, status="ativo").all()
    atencao = [(p, m) for p in ativos if (m := alertas(p))]
    recentes = (Registro.query.filter_by(terapeuta_id=current_user.id)
                .order_by(Registro.data.desc(), Registro.id.desc()).limit(5).all())
    n_recentes = Registro.query.filter_by(terapeuta_id=current_user.id).filter(Registro.data >= hoje() - timedelta(days=7)).count()
    tem_demo = DemoItem.query.filter_by(terapeuta_id=current_user.id).first() is not None
    total = Paciente.query.filter_by(terapeuta_id=current_user.id).count()
    lista_estoque = estoques(current_user)
    em_atendimento = (Consulta.query.filter_by(terapeuta_id=current_user.id)
                      .filter(Consulta.checkin_em.isnot(None), Consulta.checkout_em.is_(None)).all())
    mes = resumo_mes(current_user.id, hoje().year, hoje().month)
    return render_template("t_painel.html", consultas=consultas, atencao=atencao,
                           ativos=len(ativos), recentes=recentes, n_recentes=n_recentes,
                           tem_demo=tem_demo, total_pacientes=total, estoques=lista_estoque,
                           baixos=[e for e in lista_estoque if e.quantidade < e.minimo and e.minimo > 0],
                           em_atendimento=em_atendimento, mes=mes,
                           fin=financeiro.totais_mes(current_user.id, hoje().year, hoje().month),
                           a_receber=sum(x["a_receber"] for x in financeiro.situacao_pacientes(current_user.id)))


@app.route("/t/demo/carregar", methods=["POST"])
@exige("terapeuta")
def demo_carregar():
    import demo, sys
    if DemoItem.query.filter_by(terapeuta_id=current_user.id).first():
        flash("Os dados de demonstração já estão carregados.", "aviso")
    else:
        n = demo.carregar(sys.modules[__name__], current_user)
        flash(f"Pronto: {n} pacientes fictícios com sessões, registros, check-ins e pagamentos. "
              "Apague quando quiser no fim desta página.", "ok")
    return redirect(url_for("painel"))


@app.route("/t/demo/apagar", methods=["POST"])
@exige("terapeuta")
def demo_apagar():
    import demo, sys
    n = demo.apagar(sys.modules[__name__], current_user)
    flash(f"Dados de demonstração apagados ({n} pacientes fictícios). Seus dados reais não foram alterados.", "ok")
    return redirect(url_for("painel"))


@app.route("/t/estoque", methods=["POST"])
@exige("terapeuta")
def estoque():
    lista = {e.tipo: e for e in estoques(current_user)}
    acao, tipo = request.form.get("acao"), request.form.get("tipo")
    if acao in ("mais", "menos") and tipo in lista:
        e = lista[tipo]
        e.quantidade = e.quantidade + 1 if acao == "mais" else max(0, e.quantidade - 1)
    elif acao == "definir":
        for i, t in enumerate(TIPOS_TESTE):
            e = lista[t]
            e.quantidade = para_int(request.form.get(f"qtd_{i}"), e.quantidade, 0, 100000)
            e.minimo = para_int(request.form.get(f"min_{i}"), e.minimo, 0, 100000)
        flash("Estoque atualizado.", "ok")
    db.session.commit()
    return redirect(url_for("painel") + "#estoque")


# ============================================================ terapeuta: pacientes
@app.route("/t/pacientes")
@exige("terapeuta")
def pacientes():
    q = request.args.get("q", "").strip()
    st = request.args.get("status", "ativo")
    consulta = Paciente.query.filter_by(terapeuta_id=current_user.id)
    if q:
        consulta = consulta.filter(Paciente.nome.ilike(f"%{q}%"))
    if st in STATUS_PACIENTE:
        consulta = consulta.filter_by(status=st)
    return render_template("t_pacientes.html", lista=consulta.order_by(Paciente.nome).all(), q=q, st=st)


def salvar_paciente(p, f):
    p.nome = f.get("nome", "").strip()[:100]
    p.nascimento = para_data(f.get("nascimento"))
    p.telefone = f.get("telefone", "").strip()[:30] or None
    email = f.get("email", "").strip().lower() or None
    if email and email_em_uso(email, exceto=p):
        return "Este e-mail já está em uso por outra conta."
    if not p.tem_acesso:
        p.email = email
    subs = [s for s in f.getlist("substancias") if s in SUBSTANCIAS]
    outra = f.get("substancia_outra", "").strip()
    if outra:
        subs = [s for s in subs if s != "Outra"] + [outra[:40]]
    p.substancias = "|".join(subs) or None
    tipo_teste = f.get("tipo_teste", "")
    p.tipo_teste = tipo_teste if tipo_teste in TIPOS_TESTE or tipo_teste == "nenhum" else None
    p.tempo_uso = f.get("tempo_uso", "").strip()[:60] or None
    p.status = f.get("status") if f.get("status") in STATUS_PACIENTE else "ativo"
    p.inicio_tratamento = para_data(f.get("inicio_tratamento"))
    p.ultimo_uso = para_data(f.get("ultimo_uso"))
    p.sessoes_semana = para_int(f.get("sessoes_semana"), 1, 0, 14)
    p.valor_sessao = para_float(f.get("valor_sessao"))
    p.horario_pref = f.get("horario_pref", "").strip()[:80] or None
    p.emergencia_nome = f.get("emergencia_nome", "").strip()[:80] or None
    p.emergencia_tel = f.get("emergencia_tel", "").strip()[:30] or None
    p.anamnese = f.get("anamnese", "").strip() or None
    if not p.nome:
        return "Informe o nome do paciente."
    if not p.tipo_teste:
        return "Escolha o tipo de teste toxicológico do paciente (ou “Não faz teste”)."
    return None


@app.route("/t/pacientes/novo", methods=["GET", "POST"])
@app.route("/t/pacientes/<int:pid>/editar", methods=["GET", "POST"])
@exige("terapeuta")
def paciente_form(pid=None):
    p = meu_paciente(pid) if pid else Paciente(terapeuta_id=current_user.id, status="ativo", sessoes_semana=1)
    if request.method == "POST":
        erro = salvar_paciente(p, request.form)
        if erro:
            flash(erro, "erro")
        else:
            db.session.add(p)
            db.session.commit()
            flash("Paciente salvo.", "ok")
            return redirect(url_for("paciente_detalhe", pid=p.id))
    return render_template("t_paciente_form.html", p=p)


@app.route("/t/pacientes/<int:pid>")
@exige("terapeuta")
def paciente_detalhe(pid):
    p = meu_paciente(pid)
    registrar_acesso(p.id, "abriu a ficha")
    registros = Registro.query.filter_by(paciente_id=p.id).order_by(Registro.data.desc(), Registro.id.desc()).all()
    checkins = CheckIn.query.filter_by(paciente_id=p.id).order_by(CheckIn.data.desc()).limit(60).all()
    proximas = (Consulta.query.filter_by(paciente_id=p.id, status="agendada")
                .filter(Consulta.inicio >= agora() - timedelta(hours=2)).order_by(Consulta.inicio).limit(3).all())
    pagamentos = Pagamento.query.filter_by(paciente_id=p.id).order_by(Pagamento.data.desc()).limit(10).all()
    feitas, prox = p.conquistas()
    pontos = [(c.data, c.fissura) for c in checkins] + [(r.data, r.fissura) for r in registros]
    link = url_for("convite", codigo=p.codigo_convite, _external=True) if p.codigo_convite and not p.tem_acesso else None
    return render_template("t_paciente.html", p=p, registros=registros[:10], checkins=checkins[:7],
                           proximas=proximas, pagamentos=pagamentos, feitas=feitas, prox=prox,
                           grafico=serie_diaria(pontos), saldo=p.saldo_sessoes(), link=link, motivos=alertas(p),
                           consentimento=consentimento_ativo(p),
                           e_demo=DemoItem.query.filter_by(terapeuta_id=current_user.id, tipo="paciente", ref_id=p.id).first() is not None,
                           evolucao=relatorios.evolucao(p.id),
                           link_senha=(session.pop("link_senha", None) or {}).get("url") if (session.get("link_senha") or {}).get("pid") == p.id else None,
                           acessos=Acesso.query.filter_by(paciente_id=p.id).order_by(Acesso.quando.desc()).limit(8).all(),
                           ultimo_registro=registros[0] if registros else None)


@app.route("/t/pacientes/<int:pid>/convite", methods=["POST"])
@exige("terapeuta")
def gerar_convite(pid):
    p = meu_paciente(pid)
    if p.tem_acesso:
        flash("Este paciente já tem acesso ao app.", "erro")
    else:
        p.codigo_convite = secrets.token_urlsafe(16)
        db.session.commit()
        flash("Link de convite gerado. Envie para o paciente.", "ok")
    return redirect(url_for("paciente_detalhe", pid=p.id) + "#acesso")


@app.route("/t/pacientes/<int:pid>/pagamento", methods=["POST"])
@exige("terapeuta")
def novo_pagamento(pid):
    p = meu_paciente(pid)
    valor = para_float(request.form.get("valor"))
    if not valor or valor <= 0:
        flash("Informe o valor recebido.", "erro")
    else:
        db.session.add(Pagamento(paciente_id=p.id, valor=valor,
                                 sessoes=para_int(request.form.get("sessoes"), 1, 0, 100),
                                 data=para_data(request.form.get("data")) or hoje(),
                                 nota=request.form.get("nota", "").strip()[:200] or None))
        db.session.commit()
        flash("Pagamento registrado.", "ok")
    return redirect(url_for("paciente_detalhe", pid=p.id) + "#pagamentos")


# ============================================================ terapeuta: agenda
@app.route("/t/agenda")
@exige("terapeuta")
def agenda():
    dia = para_data(request.args.get("dia")) or hoje()
    segunda = dia - timedelta(days=dia.weekday())
    semana = [segunda + timedelta(days=i) for i in range(7)]
    ini = datetime.combine(segunda, datetime.min.time())
    consultas = (Consulta.query.filter_by(terapeuta_id=current_user.id)
                 .filter(Consulta.inicio >= ini, Consulta.inicio < ini + timedelta(days=7))
                 .order_by(Consulta.inicio).all())
    com_consulta = {c.inicio.date() for c in consultas if c.status != "cancelada"}
    do_dia = [c for c in consultas if c.inicio.date() == dia]
    return render_template("t_agenda.html", dia=dia, semana=semana, do_dia=do_dia,
                           com_consulta=com_consulta, anterior=segunda - timedelta(days=7),
                           proxima=segunda + timedelta(days=7))


@app.route("/t/agenda/nova", methods=["GET", "POST"])
@app.route("/t/agenda/<int:cid>/editar", methods=["GET", "POST"])
@exige("terapeuta")
def consulta_form(cid=None):
    c = minha_consulta(cid) if cid else Consulta(terapeuta_id=current_user.id, duracao=50, tipo="individual",
                                                 status="agendada", paciente_id=para_int(request.args.get("paciente")))
    lista = (Paciente.query.filter_by(terapeuta_id=current_user.id)
             .filter(Paciente.status.in_(["ativo", "pausado"])).order_by(Paciente.nome).all())
    if request.method == "POST":
        f = request.form
        p = db.session.get(Paciente, para_int(f.get("paciente"), 0))
        try:
            inicio = datetime.fromisoformat(f"{f['data']}T{f['hora']}")
        except (KeyError, ValueError):
            inicio = None
        if not p or p.terapeuta_id != current_user.id or not inicio:
            flash("Escolha o paciente, a data e o horário.", "erro")
        else:
            c.paciente_id, c.inicio = p.id, inicio
            c.duracao = para_int(f.get("duracao"), 50, 10, 240)
            c.tipo = f.get("tipo") if f.get("tipo") in TIPO_CONSULTA else "individual"
            c.status = f.get("status") if f.get("status") in STATUS_CONSULTA else "agendada"
            c.notas_pre = f.get("notas_pre", "").strip() or None
            def hora_real(campo):
                try:
                    return datetime.fromisoformat(f"{f['data']}T{f[campo]}") if f.get(campo) else None
                except ValueError:
                    return None
            ci, co = hora_real("checkin_hora"), hora_real("checkout_hora")
            if co and ci and co <= ci:
                co += timedelta(days=1)  # atendimento que passou da meia-noite
            if f.get("checkin_hora") is not None:
                c.checkin_em, c.checkout_em = ci, (co if ci else None)
                if c.minutos_atendidos and c.status == "agendada":
                    c.status = "realizada"
            db.session.add(c)
            repetir = request.form.get("repetir") if not cid else None
            vezes = para_int(request.form.get("vezes"), 1, 1, 52)
            criadas = 1
            if repetir in ("semanal", "quinzenal") and vezes > 1:
                passo = 7 if repetir == "semanal" else 14
                for i in range(1, vezes):
                    db.session.add(Consulta(terapeuta_id=current_user.id, paciente_id=c.paciente_id,
                                            inicio=c.inicio + timedelta(days=passo * i), duracao=c.duracao,
                                            tipo=c.tipo, status="agendada"))
                    criadas += 1
            db.session.commit()
            flash(f"{criadas} sessões agendadas." if criadas > 1 else "Sessão salva.", "ok")
            return redirect(url_for("agenda", dia=c.inicio.date().isoformat()))
    padrao = c.inicio or datetime.combine(para_data(request.args.get("dia")) or hoje(), datetime.min.time()).replace(hour=9)
    return render_template("t_consulta_form.html", c=c, pacientes=lista, padrao=padrao)


@app.route("/t/agenda/<int:cid>/excluir", methods=["POST"])
@exige("terapeuta")
def excluir_consulta(cid):
    c = minha_consulta(cid)
    dia = c.inicio.date().isoformat()
    if c.registro:
        c.registro.consulta_id = None
    db.session.delete(c)
    db.session.commit()
    flash("Sessão excluída.", "ok")
    return redirect(url_for("agenda", dia=dia))


# ============================================================ atendimento: check-in, check-out e relatório
@app.route("/t/agenda/<int:cid>/checkin", methods=["POST"])
@exige("terapeuta")
def consulta_checkin(cid):
    c = minha_consulta(cid)
    if c.status == "cancelada":
        flash("Esta sessão está cancelada.", "erro")
    elif not c.checkin_em:
        c.checkin_em, c.checkout_em = agora(), None
        db.session.commit()
        flash(f"Check-in às {c.checkin_em:%H:%M}. Bom atendimento.", "ok")
    return redirect(request.form.get("voltar") or url_for("agenda", dia=c.inicio.date().isoformat()))


@app.route("/t/agenda/<int:cid>/checkout", methods=["POST"])
@exige("terapeuta")
def consulta_checkout(cid):
    c = minha_consulta(cid)
    if not c.checkin_em:
        flash("Faça o check-in antes do check-out.", "erro")
        return redirect(request.form.get("voltar") or url_for("agenda"))
    if not c.checkout_em:
        c.checkout_em = agora()
        c.status = "realizada"
        db.session.commit()
        flash(f"Check-out às {c.checkout_em:%H:%M}. Atendimento de {c.minutos_atendidos} min.", "ok")
    if not c.registro:
        return redirect(url_for("fim_sessao", consulta=c.id))
    return redirect(request.form.get("voltar") or url_for("agenda", dia=c.inicio.date().isoformat()))


@app.route("/t/agenda/<int:cid>/desfazer-checkin", methods=["POST"])
@exige("terapeuta")
def consulta_desfazer(cid):
    c = minha_consulta(cid)
    c.checkin_em = c.checkout_em = None
    if c.status == "realizada" and not c.registro:
        c.status = "agendada"
    db.session.commit()
    flash("Check-in desfeito.", "ok")
    return redirect(request.form.get("voltar") or url_for("agenda", dia=c.inicio.date().isoformat()))


def resumo_mes(terapeuta_id, ano, mes):
    ini = datetime(ano, mes, 1)
    fim = datetime(ano + (mes == 12), mes % 12 + 1, 1)
    consultas = (Consulta.query.filter_by(terapeuta_id=terapeuta_id)
                 .filter(Consulta.inicio >= ini, Consulta.inicio < fim).all())
    atendidas = [c for c in consultas if c.minutos_atendidos]
    minutos = sum(c.minutos_atendidos for c in atendidas)
    ndias = (fim - ini).days
    por_dia = [0] * ndias
    for c in atendidas:
        por_dia[c.checkin_em.day - 1 if c.checkin_em.month == mes else c.inicio.day - 1] += c.minutos_atendidos
    por_paciente = {}
    for c in atendidas:
        item = por_paciente.setdefault(c.paciente_id, {"paciente": c.paciente, "minutos": 0, "sessoes": 0})
        item["minutos"] += c.minutos_atendidos
        item["sessoes"] += 1
    atrasos = [round((c.checkin_em - c.inicio).total_seconds() / 60) for c in atendidas]
    return {
        "ano": ano, "mes": mes, "rotulo": f"{MESES[mes - 1]} de {ano}",
        "minutos": minutos, "atendimentos": len(atendidas),
        "media": round(minutos / len(atendidas)) if atendidas else 0,
        "planejado": sum(c.duracao or 0 for c in atendidas),
        "sem_checkin": sum(1 for c in consultas if c.status == "realizada" and not c.minutos_atendidos),
        "faltas": sum(1 for c in consultas if c.status == "faltou"),
        "canceladas": sum(1 for c in consultas if c.status == "cancelada"),
        "atraso_medio": round(sum(atrasos) / len(atrasos)) if atrasos else 0,
        "por_dia": por_dia,
        "por_paciente": sorted(por_paciente.values(), key=lambda x: -x["minutos"]),
    }


@app.template_filter("horas")
def horas(minutos):
    minutos = int(minutos or 0)
    h, m = divmod(minutos, 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


@app.route("/t/relatorio")
@exige("terapeuta")
def relatorio():
    try:
        ano, mes = map(int, (request.args.get("mes") or f"{hoje():%Y-%m}").split("-"))
        assert 1 <= mes <= 12 and 2000 <= ano <= 2100
    except (ValueError, AssertionError):
        ano, mes = hoje().year, hoje().month
    atual = resumo_mes(current_user.id, ano, mes)
    ant_ano, ant_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    anterior = resumo_mes(current_user.id, ant_ano, ant_mes)
    prox = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    maior = max(atual["por_dia"] + [1])
    return render_template("t_relatorio.html", r=atual, anterior=anterior, maior=maior,
                           link_ant=f"{ant_ano}-{ant_mes:02d}", link_prox=f"{prox[0]}-{prox[1]:02d}",
                           e_futuro=(prox[0], prox[1]) > (hoje().year, hoje().month))


# ============================================================ ver como paciente (só pacientes demo)
@app.route("/t/pacientes/<int:pid>/ver-como", methods=["POST"])
@exige("terapeuta")
def ver_como_paciente(pid):
    p = meu_paciente(pid)
    if not DemoItem.query.filter_by(terapeuta_id=current_user.id, tipo="paciente", ref_id=p.id).first():
        flash("A visualização como paciente está disponível só para pacientes de demonstração.", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id))
    tid = current_user.id
    logout_user()
    session["demo_como"], session["demo_terapeuta"] = p.id, tid
    login_user(p, remember=False)
    return redirect(url_for("casa"))


@app.route("/demo/voltar", methods=["POST"])
@login_required
def demo_voltar():
    tid, pid = session.pop("demo_terapeuta", None), session.pop("demo_como", None)
    t = db.session.get(Terapeuta, tid) if tid else None
    logout_user()
    if not t:
        return redirect(url_for("entrar"))
    login_user(t, remember=False)
    session["ultimo_uso"] = datetime.now().timestamp()
    return redirect(url_for("paciente_detalhe", pid=pid) if pid else url_for("painel"))


# ============================================================ terapeuta: registros
@app.route("/t/registros")
@exige("terapeuta")
def registros():
    q = request.args.get("q", "").strip()
    risco = request.args.get("risco", "")
    consulta = Registro.query.filter_by(terapeuta_id=current_user.id).join(Paciente)
    if q:
        consulta = consulta.filter(Paciente.nome.ilike(f"%{q}%"))
    if risco in RISCO:
        consulta = consulta.filter(Registro.risco == risco)
    ativos = Paciente.query.filter_by(terapeuta_id=current_user.id, status="ativo").all()
    atencao = [(p, m) for p in ativos if (m := alertas(p))]
    return render_template("t_registros.html", lista=consulta.order_by(Registro.data.desc(), Registro.id.desc()).limit(100).all(),
                           q=q, risco=risco, atencao=atencao)


@app.route("/t/agenda/<int:cid>/registro", methods=["GET", "POST"])
@app.route("/t/pacientes/<int:pid>/registro", methods=["GET", "POST"])
@app.route("/t/registros/<int:rid>/editar", methods=["GET", "POST"])
@exige("terapeuta")
def registro_form(cid=None, pid=None, rid=None):
    if rid:
        r = meu_registro(rid)
    elif cid:
        c = minha_consulta(cid)
        r = c.registro or Registro(terapeuta_id=current_user.id, paciente_id=c.paciente_id, consulta_id=c.id,
                                   data=c.inicio.date(), risco="baixo", realizada=True)
    else:
        p = meu_paciente(pid)
        r = Registro(terapeuta_id=current_user.id, paciente_id=p.id, data=hoje(), risco="baixo", realizada=True)
    paciente = db.session.get(Paciente, r.paciente_id)
    t = None
    tid = para_int(request.values.get("transcricao"))
    if tid:
        t = db.session.get(Transcricao, tid)
        if not t or t.terapeuta_id != current_user.id or t.paciente_id != r.paciente_id:
            abort(404)
    if request.method == "GET" and t and t.dados:
        d = t.dados
        for campo in ["humor", "abordagens", "tarefa_paciente"] + CAMPOS_INDICADORES:
            if d.get(campo) not in (None, ""):
                setattr(r, campo, d[campo])
        if d.get("uso_recente") is not None:
            r.uso_recente = d["uso_recente"]
        r.risco = d.get("risco") or r.risco
        resumo = d.get("resumo", "")
        r.comentarios = (r.comentarios + "\n\n" + resumo) if r.comentarios else resumo
    if request.method == "POST":
        f = request.form
        teste_antes = bool(r.teste_feito)
        r.realizada = f.get("realizada", "1") == "1"
        r.data = para_data(f.get("data")) or r.data
        r.humor = para_int(f.get("humor"), None, 1, 5)
        for campo in CAMPOS_INDICADORES:
            setattr(r, campo, para_int(f.get(campo), None, 0, 10))
        r.uso_recente = f.get("uso_recente") == "1"
        r.data_uso = para_data(f.get("data_uso")) if r.uso_recente else None
        r.teste_feito = f.get("teste_feito") == "1"
        r.teste_resultado = f.get("teste_resultado") if r.teste_feito and f.get("teste_resultado") in RESULTADO_TESTE else None
        tipo_antes = r.teste_tipo
        r.teste_tipo = (f.get("teste_tipo") if f.get("teste_tipo") in TIPOS_TESTE else None) if r.teste_feito else None
        r.risco = f.get("risco") if f.get("risco") in RISCO else "baixo"
        r.abordagens = f.get("abordagens", "").strip()[:200] or None
        r.comentarios = f.get("comentarios", "").strip() or None
        r.tarefa_paciente = f.get("tarefa_paciente", "").strip()[:300] or None
        if r.uso_recente:
            paciente.registrar_uso(r.data_uso or r.data)
        if r.teste_feito and r.teste_resultado == "positivo":
            paciente.registrar_uso(r.data)
        estoque_usado = None
        lista = {e.tipo: e for e in estoques(current_user)}
        if teste_antes and tipo_antes in lista and (not r.teste_feito or r.teste_tipo != tipo_antes):
            lista[tipo_antes].quantidade += 1  # devolve ao estoque se o teste foi desmarcado ou trocado
        if r.teste_feito and r.teste_tipo in lista and (not teste_antes or r.teste_tipo != tipo_antes):
            estoque_usado = lista[r.teste_tipo]
            estoque_usado.quantidade = max(0, estoque_usado.quantidade - 1)
        consulta = db.session.get(Consulta, r.consulta_id) if r.consulta_id else None
        if consulta:
            consulta.status = "realizada" if r.realizada else "faltou"
        db.session.add(r)
        db.session.flush()
        if t:
            t.registro_id, t.status = r.id, "revisada"
        db.session.commit()
        if estoque_usado and estoque_usado.quantidade < estoque_usado.minimo:
            flash(f"Registro salvo. Restam {estoque_usado.quantidade} testes {estoque_usado.tipo}; hora de repor.", "aviso")
        else:
            flash("Registro salvo.", "ok")
        return redirect(url_for("registro_detalhe", rid=r.id))
    cons = db.session.get(Consulta, r.consulta_id) if r.consulta_id else None
    if not r.id and not r.teste_tipo and paciente.tipo_teste in TIPOS_TESTE:
        r.teste_tipo = paciente.tipo_teste
    evid = (t.dados.get("evidencias") or {}) if t else {}
    return render_template("t_registro_form.html", r=r, p=paciente, t=t, cons=cons, evid=evid,
                           estoque_por_tipo={e.tipo: e.quantidade for e in estoques(current_user)})


@app.route("/t/registros/<int:rid>")
@exige("terapeuta")
def registro_detalhe(rid):
    r = meu_registro(rid)
    registrar_acesso(r.paciente_id, "abriu registro de sessão")
    t = Transcricao.query.filter_by(registro_id=r.id).first()
    cons = db.session.get(Consulta, r.consulta_id) if r.consulta_id else None
    return render_template("t_registro.html", r=r, t=t, cons=cons)


@app.route("/t/registros/<int:rid>/ia", methods=["POST"])
@exige("terapeuta")
def registro_ia(rid):
    r = meu_registro(rid)
    try:
        texto_ia = feedback_ia(r)
    except voz.ErroVoz as e:
        texto_ia = None
        flash(f"{e} Tente de novo em alguns minutos.", "erro")
    if texto_ia:
        r.feedback_ia = texto_ia
        db.session.commit()
        flash("Feedback gerado. Revise antes de usar: é uma sugestão, não um parecer.", "ok")
    return redirect(url_for("registro_detalhe", rid=r.id) + "#ia")


@app.route("/t/registros/<int:rid>/excluir", methods=["POST"])
@exige("terapeuta")
def excluir_registro(rid):
    r = meu_registro(rid)
    pid = r.paciente_id
    db.session.delete(r)
    db.session.commit()
    flash("Registro excluído.", "ok")
    return redirect(url_for("paciente_detalhe", pid=pid))


# ============================================================ consentimento de gravação
TIPOS_CONTRATO = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/heic": "heic", "image/webp": "webp"}


@app.route("/t/pacientes/<int:pid>/consentimento", methods=["POST"])
@exige("terapeuta")
def novo_consentimento(pid):
    p = meu_paciente(pid)
    arq = request.files.get("arquivo")
    assinado = para_data(request.form.get("assinado_em"))
    if not assinado or not arq or not arq.filename:
        flash("Informe a data da assinatura e anexe o termo assinado (PDF ou foto).", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id) + "#gravacao")
    if arq.mimetype not in TIPOS_CONTRATO:
        flash("Envie o termo em PDF, JPG, PNG ou HEIC.", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id) + "#gravacao")
    dados = arq.read()
    if len(dados) > 10 * 1024 * 1024:
        flash("O arquivo do termo passa de 10 MB. Envie uma versão menor.", "erro")
        return redirect(url_for("paciente_detalhe", pid=p.id) + "#gravacao")
    for antigo in Consentimento.query.filter_by(paciente_id=p.id, revogado_em=None):
        antigo.revogado_em = hoje()
    db.session.add(Consentimento(paciente_id=p.id, terapeuta_id=current_user.id, assinado_em=assinado,
                                 versao=request.form.get("versao", "").strip()[:40] or None, arquivo=dados,
                                 arquivo_tipo=arq.mimetype, arquivo_nome=f"termo-{p.id}-{assinado.isoformat()}.{TIPOS_CONTRATO[arq.mimetype]}"))
    db.session.commit()
    flash("Termo de consentimento anexado. A gravação da sessão está liberada para este paciente.", "ok")
    return redirect(url_for("paciente_detalhe", pid=p.id) + "#gravacao")


@app.route("/t/consentimentos/<int:cid>/arquivo")
@exige("terapeuta")
def arquivo_consentimento(cid):
    c = db.session.get(Consentimento, cid)
    if not c or c.terapeuta_id != current_user.id or not c.arquivo:
        abort(404)
    return Response(c.arquivo, mimetype=c.arquivo_tipo, headers={
        "Content-Disposition": f'inline; filename="{c.arquivo_nome}"', "Cache-Control": "no-store"})


@app.route("/t/consentimentos/<int:cid>/revogar", methods=["POST"])
@exige("terapeuta")
def revogar_consentimento(cid):
    c = db.session.get(Consentimento, cid)
    if not c or c.terapeuta_id != current_user.id:
        abort(404)
    c.revogado_em = hoje()
    db.session.commit()
    flash("Consentimento revogado. Novas gravações de sessão ficam bloqueadas para este paciente.", "ok")
    return redirect(url_for("paciente_detalhe", pid=c.paciente_id) + "#gravacao")


# ============================================================ fim de sessão (gravação e transcrição)
@app.route("/t/fim")
@exige("terapeuta")
def fim_sessao():
    ini = datetime.combine(hoje() - timedelta(days=2), datetime.min.time())
    recentes = (Consulta.query.filter_by(terapeuta_id=current_user.id)
                .filter(Consulta.inicio >= ini, Consulta.inicio <= agora() + timedelta(hours=12))
                .filter(Consulta.status.in_(["agendada", "realizada"]))
                .order_by(Consulta.inicio.desc()).all())
    sem_registro = [c for c in recentes if not c.registro]
    lista = (Paciente.query.filter_by(terapeuta_id=current_user.id)
             .filter(Paciente.status.in_(["ativo", "pausado"])).order_by(Paciente.nome).all())
    pendentes = (Transcricao.query.filter_by(terapeuta_id=current_user.id)
                 .filter(Transcricao.status.in_(["transcrita", "pronta", "erro", "gravando"]))
                 .order_by(Transcricao.criado_em.desc()).limit(20).all())
    consentidos = {c.paciente_id for c in Consentimento.query.filter_by(terapeuta_id=current_user.id, revogado_em=None)}
    sel_c = para_int(request.args.get("consulta"))
    sel_p = para_int(request.args.get("paciente"))
    if not sel_c and not sel_p and sem_registro:
        agora_ = agora()
        passadas = [c for c in sem_registro if c.inicio <= agora_]
        sel_c = (passadas[0] if passadas else sem_registro[-1]).id
    return render_template("t_fim.html", sem_registro=sem_registro, pacientes=lista, pendentes=pendentes,
                           consentidos=consentidos, sel_c=sel_c, sel_p=sel_p)


def minha_transcricao(tid):
    t = db.session.get(Transcricao, tid)
    if not t or t.terapeuta_id != current_user.id:
        abort(404)
    return t


@app.route("/t/gravacao/nova", methods=["POST"])
@exige("terapeuta")
def gravacao_nova():
    f = request.form
    tipo = f.get("tipo") if f.get("tipo") in ("resumo", "consulta") else "resumo"
    c = None
    if f.get("consulta"):
        c = minha_consulta(para_int(f.get("consulta"), 0))
        p = c.paciente
    else:
        p = meu_paciente(para_int(f.get("paciente"), 0))
    if not voz.transcricao_ativa():
        return jsonify(erro="A transcrição não está configurada. Veja o README para ativar."), 400
    if tipo == "consulta":
        if not consentimento_ativo(p):
            return jsonify(erro="Este paciente não tem termo de consentimento ativo. Anexe o termo na ficha dele."), 403
        if f.get("avisado") != "1":
            return jsonify(erro="Confirme que avisou o paciente de que a gravação vai começar."), 400
    t = Transcricao(terapeuta_id=current_user.id, paciente_id=p.id, consulta_id=c.id if c else None, tipo=tipo)
    db.session.add(t)
    db.session.commit()
    return jsonify(id=t.id)


@app.route("/t/gravacao/<int:tid>/parte", methods=["POST"])
@exige("terapeuta")
def gravacao_parte(tid):
    t = minha_transcricao(tid)
    audio = request.files.get("audio")
    if not audio:
        return jsonify(erro="Nenhum áudio recebido."), 400
    nome, tipo = audio.filename or "audio.m4a", audio.mimetype
    dados = audio.read()
    audio.close()
    try:
        texto_parte = voz.transcrever(dados, nome, tipo)
    except voz.ErroVoz as e:
        t.falhas += 1
        db.session.commit()
        return jsonify(erro=str(e)), 502
    finally:
        del dados  # o áudio não é guardado em lugar nenhum
    t.partes += 1
    t.segundos += para_int(request.form.get("segundos"), 0, 0, 36000)
    if texto_parte:
        t.texto = ((t.texto or "") + ("\n\n" if t.texto else "") + texto_parte)
    db.session.commit()
    return jsonify(ok=True, partes=t.partes, caracteres=len(t.texto or ""))


@app.route("/t/gravacao/<int:tid>/concluir", methods=["POST"])
@exige("terapeuta")
def gravacao_concluir(tid):
    t = minha_transcricao(tid)
    if not (t.texto or "").strip():
        t.status, t.erro = "erro", "Nenhuma fala foi reconhecida na gravação."
        db.session.commit()
        return jsonify(url=url_for("gravacao_ver", tid=t.id))
    t.texto_original = t.texto  # guarda a versão exata que saiu da transcrição
    t.status = "transcrita"     # o resumo só é gerado depois que o terapeuta revisar o texto
    db.session.commit()
    return jsonify(url=url_for("gravacao_ver", tid=t.id))


@app.route("/t/gravacao/<int:tid>/texto", methods=["POST"])
@exige("terapeuta")
def gravacao_texto(tid):
    t = minha_transcricao(tid)
    novo = (request.form.get("texto") or "").strip()
    if not novo:
        flash("A transcrição não pode ficar vazia.", "erro")
        return redirect(url_for("gravacao_ver", tid=t.id))
    if novo != (t.texto or "").strip():
        t.texto = novo
        if t.sugestao:
            t.sugestao, t.status = None, "transcrita"  # resumo antigo não vale para o texto corrigido
    db.session.commit()
    if request.form.get("gerar") == "1":
        return gravacao_resumir(t.id)
    flash("Correções salvas.", "ok")
    return redirect(url_for("gravacao_ver", tid=t.id))


@app.route("/t/gravacao/<int:tid>/resumir", methods=["POST"])
@exige("terapeuta")
def gravacao_resumir(tid):
    t = minha_transcricao(tid)
    try:
        anon = voz.anonimizar(t.texto or "", [t.paciente.nome])
        dados = voz.resumir(anon, t.tipo, INDICADORES)
        t.sugestao, t.erro, t.status = json.dumps(dados, ensure_ascii=False), None, "pronta"
        flash("Resumo gerado a partir da transcrição revisada.", "ok")
    except voz.ErroVoz as e:
        t.erro = str(e)
        flash(str(e), "erro")
    db.session.commit()
    return redirect(url_for("gravacao_ver", tid=t.id))


@app.route("/t/gravacao/<int:tid>")
@exige("terapeuta")
def gravacao_ver(tid):
    t = minha_transcricao(tid)
    registrar_acesso(t.paciente_id, "abriu transcrição")
    if t.registro_id:
        return redirect(url_for("registro_detalhe", rid=t.registro_id))
    if t.consulta_id:
        destino = url_for("registro_form", cid=t.consulta_id, transcricao=t.id)
    else:
        destino = url_for("registro_form", pid=t.paciente_id, transcricao=t.id)
    return render_template("t_gravacao.html", t=t, destino=destino)


@app.route("/t/gravacao/<int:tid>/excluir", methods=["POST"])
@exige("terapeuta")
def gravacao_excluir(tid):
    t = minha_transcricao(tid)
    db.session.delete(t)
    db.session.commit()
    flash("Transcrição excluída.", "ok")
    return redirect(url_for("fim_sessao"))


@app.errorhandler(413)
def muito_grande(e):
    if request.path.startswith("/t/gravacao"):
        return jsonify(erro="Arquivo de áudio grande demais (máximo 25 MB)."), 413
    flash("Arquivo grande demais.", "erro")
    return redirect(request.referrer or url_for("inicio"))


# ============================================================ terapeuta: mood
@app.route("/t/mood")
@exige("terapeuta")
def mood():
    periodo = para_int(request.args.get("dias"), 30)
    if periodo not in (7, 30, 90):
        periodo = 30
    pid = para_int(request.args.get("paciente"))
    inicio = hoje() - timedelta(days=periodo - 1)
    lista = Paciente.query.filter_by(terapeuta_id=current_user.id).order_by(Paciente.nome).all()
    ids = [p.id for p in lista if not pid or p.id == pid]
    regs = Registro.query.filter(Registro.paciente_id.in_(ids), Registro.data >= inicio, Registro.humor.isnot(None)).all()
    cks = CheckIn.query.filter(CheckIn.paciente_id.in_(ids), CheckIn.data >= inicio).all()
    todos = [(x.data, x.humor) for x in regs] + [(x.data, x.humor) for x in cks]
    contagem = {n: sum(1 for _, h in todos if h == n) for n in HUMOR}
    total = len(todos)
    media = round(sum(h for _, h in todos) / total, 1) if total else None
    linha = serie_diaria([(d, (h - 1) * 2.5) for d, h in todos], dias=periodo)
    return render_template("t_mood.html", contagem=contagem, total=total, media=media, linha=linha,
                           pacientes=lista, pid=pid, periodo=periodo)


# ============================================================ biblioteca (terapeuta edita)
@app.route("/t/biblioteca/novo", methods=["GET", "POST"])
@app.route("/t/biblioteca/<int:aid>/editar", methods=["GET", "POST"])
@exige("terapeuta")
def artigo_form(aid=None):
    a = db.session.get(Artigo, aid) if aid else Artigo(categoria="pratica", publicado=True)
    if aid and (not a or a.autor_id != current_user.id):
        abort(404)
    if request.method == "POST":
        f = request.form
        if not f.get("titulo", "").strip() or not f.get("corpo", "").strip():
            flash("Título e texto são obrigatórios.", "erro")
        else:
            a.titulo, a.resumo = f["titulo"].strip()[:140], f.get("resumo", "").strip()[:300]
            a.corpo = f["corpo"].strip()
            a.categoria = f.get("categoria") if f.get("categoria") in CATEGORIAS else "pratica"
            a.publicado, a.autor_id = f.get("publicado") == "1", current_user.id
            db.session.add(a)
            db.session.commit()
            flash("Conteúdo salvo.", "ok")
            return redirect(url_for("artigo", aid=a.id))
    return render_template("t_artigo_form.html", a=a)


# ============================================================ paciente
@app.route("/p")
@exige("paciente")
def casa():
    p = current_user
    ck = CheckIn.query.filter_by(paciente_id=p.id, data=hoje()).first()
    proximas = (Consulta.query.filter_by(paciente_id=p.id, status="agendada").filter(Consulta.inicio >= agora())
                .order_by(Consulta.inicio).limit(3).all())
    tarefa = (Registro.query.filter_by(paciente_id=p.id).filter(Registro.tarefa_paciente.isnot(None))
              .order_by(Registro.data.desc(), Registro.id.desc()).first())
    cks = CheckIn.query.filter_by(paciente_id=p.id).order_by(CheckIn.data.desc()).limit(30).all()
    feitas, prox = p.conquistas()
    return render_template("p_casa.html", ck=ck, proximas=proximas, tarefa=tarefa, feitas=feitas, prox=prox,
                           recentes=cks[:5], grafico=serie_diaria([(c.data, c.fissura) for c in cks]),
                           saldo=p.saldo_sessoes() if p.valor_sessao or Pagamento.query.filter_by(paciente_id=p.id).first() else None)


@app.route("/p/checkin", methods=["GET", "POST"])
@exige("paciente")
def checkin():
    p = current_user
    ck = CheckIn.query.filter_by(paciente_id=p.id, data=hoje()).first()
    if request.method == "POST":
        f = request.form
        humor, fissura = para_int(f.get("humor"), None, 1, 5), para_int(f.get("fissura"), None, 0, 10)
        if humor is None or fissura is None:
            flash("Escolha como você está e o nível de fissura.", "erro")
            return redirect(url_for("checkin"))
        ck = ck or CheckIn(paciente_id=p.id, data=hoje())
        ck.humor, ck.fissura = humor, fissura
        ck.sono = para_int(f.get("sono"), None, 1, 5)
        ck.usou = f.get("usou") == "1"
        ck.gatilhos = ", ".join(g for g in f.getlist("gatilhos") if g in GATILHOS) or None
        ck.nota = f.get("nota", "").strip() or None
        if ck.usou:
            p.registrar_uso(hoje())
        db.session.add(ck)
        db.session.commit()
        if ck.usou:
            flash("Obrigado pela honestidade. Um deslize não apaga o caminho que você já fez. Fale com seu terapeuta.", "ok")
        elif fissura >= 7:
            flash("A fissura vem em ondas e passa. Vamos respirar juntos por alguns minutos.", "ok")
            return redirect(url_for("respirar"))
        else:
            flash("Check-in salvo.", "ok")
        return redirect(url_for("casa"))
    return render_template("p_checkin.html", ck=ck)


@app.route("/p/diario")
@exige("paciente")
def diario():
    cks = CheckIn.query.filter_by(paciente_id=current_user.id).order_by(CheckIn.data.desc()).limit(60).all()
    consultas = (Consulta.query.filter_by(paciente_id=current_user.id).filter(Consulta.inicio >= agora())
                 .filter(Consulta.status == "agendada").order_by(Consulta.inicio).limit(5).all())
    tarefas = (Registro.query.filter_by(paciente_id=current_user.id).filter(Registro.tarefa_paciente.isnot(None))
               .order_by(Registro.data.desc()).limit(10).all())
    return render_template("p_diario.html", checkins=cks[:30], consultas=consultas, tarefas=tarefas,
                           grafico=serie_diaria([(c.data, c.fissura) for c in cks]))


# ============================================================ compartilhado
def artigos_visiveis():
    if current_user.papel == "paciente":
        return Artigo.query.filter(Artigo.publicado.is_(True),
                                   (Artigo.autor_id.is_(None)) | (Artigo.autor_id == current_user.terapeuta_id))
    return Artigo.query.filter((Artigo.autor_id.is_(None)) | (Artigo.autor_id == current_user.id))


@app.route("/biblioteca")
@login_required
def biblioteca():
    cat = request.args.get("c")
    q = artigos_visiveis()
    if cat in CATEGORIAS:
        q = q.filter_by(categoria=cat)
    return render_template("biblioteca.html", artigos=q.order_by(Artigo.titulo).all(), cat=cat)


@app.route("/biblioteca/<int:aid>")
@login_required
def artigo(aid):
    a = artigos_visiveis().filter(Artigo.id == aid).first() or abort(404)
    return render_template("artigo.html", a=a)


@app.route("/respirar")
@login_required
def respirar():
    return render_template("respirar.html")


@app.route("/ajuda")
@login_required
def ajuda():
    return render_template("ajuda.html")


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def erro(e):
    return render_template("erro.html", e=e), e.code


# ============================================================ inicialização
def migrar_colunas():
    """Adiciona colunas novas a tabelas já existentes (create_all não faz isso)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    for tabela in db.metadata.sorted_tables:
        if not insp.has_table(tabela.name):
            continue
        existentes = {c["name"] for c in insp.get_columns(tabela.name)}
        for col in tabela.columns:
            if col.name in existentes:
                continue
            tipo = col.type.compile(dialect=db.engine.dialect)
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{tabela.name}" ADD COLUMN "{col.name}" {tipo}'))
            except Exception:
                pass  # outro processo pode ter criado a coluna ao mesmo tempo


CAMPOS_CIFRADOS = [("paciente", "anamnese"), ("consulta", "notas_pre"), ("registro", "comentarios"),
                   ("registro", "feedback_ia"), ("check_in", "nota"), ("transcricao", "texto"),
                   ("transcricao", "texto_original"), ("transcricao", "sugestao")]


def criptografar_textos_antigos():
    from sqlalchemy import text
    for tabela, coluna in CAMPOS_CIFRADOS:
        try:
            linhas = db.session.execute(text(f'SELECT id, "{coluna}" FROM "{tabela}" WHERE "{coluna}" IS NOT NULL '
                                             f'AND "{coluna}" NOT LIKE :p'), {"p": "enc1:%"}).fetchall()
            for ident, valor in linhas:
                db.session.execute(text(f'UPDATE "{tabela}" SET "{coluna}" = :v WHERE id = :i'), {"v": cifrar(valor), "i": ident})
            db.session.commit()
        except Exception:
            db.session.rollback()


def iniciar_banco():
    with app.app_context():
        for tentativa in range(3):  # tolera outro processo criando as mesmas tabelas ao mesmo tempo
            try:
                db.create_all()
                break
            except Exception:
                db.session.rollback()
                import time
                time.sleep(1 + tentativa)
        migrar_colunas()
        criptografar_textos_antigos()
        import licenca
        licenca.semear_planos()
        import plataforma
        plataforma.criar_indices()
        if Artigo.query.filter_by(autor_id=None).count() == 0:
            from conteudo_base import ARTIGOS
            for a in ARTIGOS:
                db.session.add(Artigo(autor_id=None, **a))
            db.session.commit()
        db.session.remove()
        db.engine.dispose()  # com --preload, cada processo do servidor abre as próprias conexões


import sys as _sys
_sys.modules.setdefault("app", _sys.modules[__name__])  # permite "python app.py" e os módulos abaixo
import financeiro  # noqa: E402,F401
import conta  # noqa: E402,F401
import relatorios  # noqa: E402,F401
import licenca  # noqa: E402,F401
import plataforma  # noqa: E402,F401

iniciar_banco()

if __name__ == "__main__":
    local = os.environ.get("ACESSO_SEM_SENHA") == "1"  # sem senha: só aceita conexões deste computador
    app.run(debug=DEV, host="127.0.0.1" if local else "0.0.0.0", port=int(os.environ.get("PORT", 5000)))
