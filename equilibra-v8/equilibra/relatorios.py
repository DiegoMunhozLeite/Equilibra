"""Evolução dos indicadores e relatório do paciente para imprimir ou salvar em PDF."""
from datetime import datetime, timedelta

from flask import render_template, request
from flask_login import current_user

from app import (HUMOR, INDICADORES, RESULTADO_TESTE, CheckIn, Consulta, Registro, app, exige, hoje, meu_paciente,
                 para_int, registrar_acesso)


def evolucao(paciente_id, limite=12):
    """Para cada indicador: valores das últimas sessões, primeiro e último valor e se melhorou."""
    regs = (Registro.query.filter_by(paciente_id=paciente_id, realizada=True)
            .order_by(Registro.data.desc(), Registro.id.desc()).limit(limite).all())[::-1]
    saida = []
    for campo, rotulo, positivo in INDICADORES:
        pontos = [(r.data, getattr(r, campo)) for r in regs if getattr(r, campo) is not None]
        if not pontos:
            continue
        primeiro, ultimo = pontos[0][1], pontos[-1][1]
        dif = ultimo - primeiro
        if len(pontos) < 2 or abs(dif) < 1:
            direcao = "estavel"
        else:
            direcao = "melhorou" if (dif > 0) == positivo else "piorou"
        n = len(pontos)
        linha = " ".join(f"{(i * 100 / (n - 1)) if n > 1 else 50:.1f},{30 - v * 2.6:.1f}" for i, (_, v) in enumerate(pontos))
        saida.append({"campo": campo, "rotulo": rotulo, "positivo": positivo, "pontos": pontos, "primeiro": primeiro,
                      "ultimo": ultimo, "direcao": direcao, "linha": linha, "media": round(sum(v for _, v in pontos) / n, 1)})
    return saida


@app.route("/t/pacientes/<int:pid>/relatorio", methods=["GET", "POST"])
@exige("terapeuta")
def relatorio_paciente(pid):
    p = meu_paciente(pid)
    if request.method == "GET":
        return render_template("terapeuta/relatorio_opcoes.html", p=p)
    f = request.form
    dias = para_int(f.get("dias"), 90, 7, 3650)
    inicio = hoje() - timedelta(days=dias - 1)
    consultas = (Consulta.query.filter_by(paciente_id=p.id)
                 .filter(Consulta.inicio >= datetime.combine(inicio, datetime.min.time())).order_by(Consulta.inicio).all())
    consultas = [c for c in consultas if c.inicio.date() <= hoje()]
    realizadas = [c for c in consultas if c.status == "realizada"]
    faltas = [c for c in consultas if c.status == "faltou"]
    marcadas = len(realizadas) + len(faltas)
    regs = (Registro.query.filter_by(paciente_id=p.id).filter(Registro.data >= inicio)
            .order_by(Registro.data).all())
    testes = [r for r in regs if r.teste_feito]
    cks = CheckIn.query.filter_by(paciente_id=p.id).filter(CheckIn.data >= inicio).all()
    humores = [r.humor for r in regs if r.humor] + [c.humor for c in cks]
    # comparação: primeiras sessões do período contra as últimas (cada indicador com seus próprios registros)
    comparativo = []
    for campo, rotulo, positivo in INDICADORES:
        valores = [getattr(r, campo) for r in regs if getattr(r, campo) is not None]
        if not valores:
            continue
        if len(valores) == 1:
            comparativo.append({"rotulo": rotulo, "antes": valores[0], "depois": None, "direcao": None, "n": 1})
            continue
        metade = len(valores) // 2
        antes, depois = valores[:metade], valores[-metade:]
        ma, md = round(sum(antes) / len(antes), 1), round(sum(depois) / len(depois), 1)
        direcao = ("melhora" if (md > ma) == positivo else "piora") if abs(md - ma) >= 1 else "estável"
        comparativo.append({"rotulo": rotulo, "antes": ma, "depois": md, "direcao": direcao, "n": len(valores)})
    registrar_acesso(p.id, "gerou relatório")
    return render_template(
        "terapeuta/relatorio_paciente.html", p=p, t=current_user, dias=dias, inicio=inicio, fim=hoje(),
        realizadas=len(realizadas), faltas=len(faltas), canceladas=sum(1 for c in consultas if c.status == "cancelada"),
        presenca=round(len(realizadas) * 100 / marcadas) if marcadas else None,
        minutos=sum(c.minutos_atendidos or 0 for c in realizadas), testes=testes, comparativo=comparativo,
        humor_medio=round(sum(humores) / len(humores), 1) if humores else None, n_checkins=len(cks),
        fissura_media=round(sum(c.fissura for c in cks) / len(cks), 1) if cks else None,
        regs=regs if f.get("incluir_evolucao") == "1" else [], parecer=f.get("parecer", "").strip(),
        destinatario=f.get("destinatario", "").strip(), incluir_substancias=f.get("incluir_substancias") == "1",
        HUMOR=HUMOR, RESULTADO_TESTE=RESULTADO_TESTE)
