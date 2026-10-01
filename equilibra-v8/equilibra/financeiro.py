"""Área financeira do terapeuta: recebimentos, despesas, saldos de pacotes, recibos e exportação."""
import csv
import io
from datetime import date, datetime, timedelta

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app import (MESES, Consulta, Pagamento, Paciente, app, db, exige, hoje, meu_paciente, para_data,
                 para_float, para_int)

FORMAS = {"pix": "Pix", "dinheiro": "Dinheiro", "cartao": "Cartão", "transferencia": "Transferência", "outro": "Outro"}
CATEGORIAS_DESPESA = {"testes": "Testes toxicológicos", "sala": "Aluguel ou sala", "materiais": "Materiais e insumos",
                      "formacao": "Formação e supervisão", "impostos": "Impostos e taxas", "marketing": "Divulgação",
                      "outros": "Outros"}


class Despesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey("terapeuta.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, default=hoje)
    descricao = db.Column(db.String(160), nullable=False)
    categoria = db.Column(db.String(20), default="outros")
    valor = db.Column(db.Float, nullable=False)


@app.context_processor
def contexto_financeiro():
    return dict(FORMAS=FORMAS, CATEGORIAS_DESPESA=CATEGORIAS_DESPESA)


def limites_mes(ano, mes):
    ini = date(ano, mes, 1)
    fim = date(ano + (mes == 12), mes % 12 + 1, 1)
    return ini, fim


def pagamentos_do_terapeuta(tid):
    return Pagamento.query.join(Paciente, Pagamento.paciente_id == Paciente.id).filter(Paciente.terapeuta_id == tid)


def totais_mes(tid, ano, mes):
    ini, fim = limites_mes(ano, mes)
    recebido = (pagamentos_do_terapeuta(tid).filter(Pagamento.data >= ini, Pagamento.data < fim)
                .with_entities(func.coalesce(func.sum(Pagamento.valor), 0)).scalar())
    gastos = (db.session.query(func.coalesce(func.sum(Despesa.valor), 0))
              .filter(Despesa.terapeuta_id == tid, Despesa.data >= ini, Despesa.data < fim).scalar())
    return float(recebido or 0), float(gastos or 0)


def situacao_pacientes(tid):
    """Saldo de sessões de cada paciente: positivo = crédito, negativo = a receber."""
    lista = []
    for p in Paciente.query.filter_by(terapeuta_id=tid).filter(Paciente.status.in_(["ativo", "pausado"])).order_by(Paciente.nome):
        saldo = p.saldo_sessoes()
        ultimo = Pagamento.query.filter_by(paciente_id=p.id).order_by(Pagamento.data.desc()).first()
        a_receber = (-saldo * (p.valor_sessao or 0)) if saldo < 0 else 0
        lista.append({"p": p, "saldo": saldo, "a_receber": a_receber, "ultimo": ultimo,
                      "situacao": "deve" if saldo < 0 else "acabando" if saldo <= 1 else "ok"})
    ordem = {"deve": 0, "acabando": 1, "ok": 2}
    return sorted(lista, key=lambda x: (ordem[x["situacao"]], x["p"].nome))


@app.route("/t/financeiro")
@exige("terapeuta")
def financeiro():
    try:
        ano, mes = map(int, (request.args.get("mes") or f"{hoje():%Y-%m}").split("-"))
        assert 1 <= mes <= 12
    except (ValueError, AssertionError):
        ano, mes = hoje().year, hoje().month
    ini, fim = limites_mes(ano, mes)
    tid = current_user.id
    recebido, gastos = totais_mes(tid, ano, mes)

    # últimos 6 meses para o gráfico
    serie = []
    a, m = ano, mes
    for _ in range(6):
        r, g = totais_mes(tid, a, m)
        serie.append({"rotulo": MESES[m - 1][:3], "recebido": r, "gastos": g})
        a, m = (a - 1, 12) if m == 1 else (a, m - 1)
    serie.reverse()
    maior = max([1] + [max(x["recebido"], x["gastos"]) for x in serie])

    pagamentos = (pagamentos_do_terapeuta(tid).filter(Pagamento.data >= ini, Pagamento.data < fim)
                  .order_by(Pagamento.data.desc(), Pagamento.id.desc()).all())
    despesas = (Despesa.query.filter_by(terapeuta_id=tid).filter(Despesa.data >= ini, Despesa.data < fim)
                .order_by(Despesa.data.desc(), Despesa.id.desc()).all())
    por_forma = {}
    for pg in pagamentos:
        por_forma[pg.forma or "outro"] = por_forma.get(pg.forma or "outro", 0) + pg.valor
    por_categoria = {}
    for d in despesas:
        por_categoria[d.categoria or "outros"] = por_categoria.get(d.categoria or "outros", 0) + d.valor

    # previsão: sessões ainda agendadas neste mês
    agendadas = (Consulta.query.filter_by(terapeuta_id=tid, status="agendada")
                 .filter(Consulta.inicio >= datetime.combine(max(ini, hoje()), datetime.min.time()),
                         Consulta.inicio < datetime.combine(fim, datetime.min.time())).all())
    previsto = sum(c.paciente.valor_sessao or 0 for c in agendadas)
    situacao = situacao_pacientes(tid)
    prox = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    ant = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return render_template(
        "terapeuta/financeiro.html", ano=ano, mes=mes, rotulo=f"{MESES[mes - 1]} de {ano}",
        recebido=recebido, gastos=gastos, resultado=recebido - gastos, serie=serie, maior=maior,
        pagamentos=pagamentos, despesas=despesas, por_forma=por_forma, por_categoria=por_categoria,
        agendadas=len(agendadas), previsto=previsto, situacao=situacao,
        a_receber=sum(x["a_receber"] for x in situacao), devendo=[x for x in situacao if x["situacao"] == "deve"],
        acabando=[x for x in situacao if x["situacao"] == "acabando"],
        pacientes=[x["p"] for x in situacao], link_ant=f"{ant[0]}-{ant[1]:02d}", link_prox=f"{prox[0]}-{prox[1]:02d}",
        e_futuro=prox > (hoje().year, hoje().month))


@app.route("/t/financeiro/pagamento", methods=["POST"])
@exige("terapeuta")
def financeiro_pagamento():
    f = request.form
    p = meu_paciente(para_int(f.get("paciente"), 0))
    valor = para_float(f.get("valor"))
    if not valor or valor <= 0:
        flash("Informe o valor recebido.", "erro")
    else:
        db.session.add(Pagamento(paciente_id=p.id, valor=valor, sessoes=para_int(f.get("sessoes"), 1, 0, 200),
                                 data=para_data(f.get("data")) or hoje(),
                                 forma=f.get("forma") if f.get("forma") in FORMAS else "pix",
                                 nota=f.get("nota", "").strip()[:200] or None))
        db.session.commit()
        flash(f"Pagamento de {p.nome} registrado.", "ok")
    return redirect(request.form.get("voltar") or url_for("financeiro"))


@app.route("/t/financeiro/pagamento/<int:pgid>/excluir", methods=["POST"])
@exige("terapeuta")
def financeiro_pagamento_excluir(pgid):
    pg = db.session.get(Pagamento, pgid)
    if not pg or pg.paciente.terapeuta_id != current_user.id:
        abort(404)
    db.session.delete(pg)
    db.session.commit()
    flash("Pagamento excluído.", "ok")
    return redirect(request.form.get("voltar") or url_for("financeiro"))


@app.route("/t/financeiro/despesa", methods=["POST"])
@exige("terapeuta")
def financeiro_despesa():
    f = request.form
    valor = para_float(f.get("valor"))
    if not valor or valor <= 0 or not f.get("descricao", "").strip():
        flash("Informe a descrição e o valor da despesa.", "erro")
    else:
        db.session.add(Despesa(terapeuta_id=current_user.id, descricao=f["descricao"].strip()[:160], valor=valor,
                               categoria=f.get("categoria") if f.get("categoria") in CATEGORIAS_DESPESA else "outros",
                               data=para_data(f.get("data")) or hoje()))
        db.session.commit()
        flash("Despesa registrada.", "ok")
    return redirect(request.form.get("voltar") or url_for("financeiro"))


@app.route("/t/financeiro/despesa/<int:did>/excluir", methods=["POST"])
@exige("terapeuta")
def financeiro_despesa_excluir(did):
    d = db.session.get(Despesa, did)
    if not d or d.terapeuta_id != current_user.id:
        abort(404)
    db.session.delete(d)
    db.session.commit()
    flash("Despesa excluída.", "ok")
    return redirect(request.form.get("voltar") or url_for("financeiro"))


@app.route("/t/pagamentos/<int:pgid>/recibo")
@exige("terapeuta")
def recibo(pgid):
    pg = db.session.get(Pagamento, pgid)
    if not pg or pg.paciente.terapeuta_id != current_user.id:
        abort(404)
    return render_template("terapeuta/recibo.html", pg=pg, t=current_user, extenso=valor_por_extenso(pg.valor))


@app.route("/t/financeiro/exportar")
@exige("terapeuta")
def financeiro_exportar():
    try:
        ano, mes = map(int, request.args.get("mes", f"{hoje():%Y-%m}").split("-"))
    except ValueError:
        ano, mes = hoje().year, hoje().month
    ini, fim = limites_mes(ano, mes)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["Data", "Tipo", "Descrição", "Categoria ou forma", "Sessões", "Valor (R$)"])
    for pg in pagamentos_do_terapeuta(current_user.id).filter(Pagamento.data >= ini, Pagamento.data < fim).order_by(Pagamento.data):
        w.writerow([pg.data.strftime("%d/%m/%Y"), "Recebimento", pg.paciente.nome, FORMAS.get(pg.forma or "outro", "Outro"),
                    pg.sessoes, f"{pg.valor:.2f}".replace(".", ",")])
    for d in Despesa.query.filter_by(terapeuta_id=current_user.id).filter(Despesa.data >= ini, Despesa.data < fim).order_by(Despesa.data):
        w.writerow([d.data.strftime("%d/%m/%Y"), "Despesa", d.descricao, CATEGORIAS_DESPESA.get(d.categoria, "Outros"),
                    "", f"-{d.valor:.2f}".replace(".", ",")])
    return Response("\ufeff" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="financeiro-{ano}-{mes:02d}.csv"'})


# ---------------------------------------------------------------- valor por extenso para recibos
_UNID = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze",
         "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CEM = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]


def _ate_mil(n):
    if n == 100:
        return "cem"
    partes = []
    c, resto = divmod(n, 100)
    if c:
        partes.append(_CEM[c])
    if resto < 20:
        if resto:
            partes.append(_UNID[resto])
    else:
        d, u = divmod(resto, 10)
        partes.append(_DEZ[d] + (f" e {_UNID[u]}" if u else ""))
    return " e ".join(partes)


def valor_por_extenso(valor):
    reais, centavos = int(valor), round((valor - int(valor)) * 100)
    if centavos == 100:
        reais, centavos = reais + 1, 0
    partes = []
    milhares, unidades = divmod(reais, 1000)
    if milhares:
        partes.append("mil" if milhares == 1 else f"{_ate_mil(milhares)} mil")
    if unidades:
        partes.append(_ate_mil(unidades))
    texto = (" e " if milhares and unidades and (unidades < 100 or unidades % 100 == 0) else " ").join(partes) if partes else "zero"
    texto += " real" if reais == 1 else " reais"
    if centavos:
        texto += f" e {_ate_mil(centavos)} {'centavo' if centavos == 1 else 'centavos'}"
    return texto
