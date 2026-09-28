"""
Dados de demonstração. Todos os nomes são fictícios e marcados com "· demo".
Nenhum paciente demo recebe senha ou e-mail. Tudo o que é criado aqui fica
anotado na tabela DemoItem e pode ser apagado pelo painel.
"""
import json
import random
from datetime import datetime, time, timedelta

PDF_EXEMPLO = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
               b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R"
               b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
               b"4 0 obj<</Length 120>>stream\nBT /F1 16 Tf 60 780 Td (Termo de consentimento - EXEMPLO) Tj "
               b"0 -28 Td /F1 11 Tf (Documento ficticio gerado para demonstracao do app.) Tj ET\nendstream endobj\n"
               b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
               b"trailer<</Root 1 0 R>>\n%%EOF")

PACIENTES = [
    dict(nome="Ana · demo", tipo_teste="Multi 6", substancias="Álcool", tempo_uso="8 anos", status="ativo", dias_limpo=146,
         sessoes_semana=1, valor_sessao=180.0, horario_pref="Terças às 14h", pacote=(12, 2160.0),
         anamnese="Paciente fictícia. Buscou tratamento após pressão no trabalho. Boa rede de apoio familiar, "
                  "motivada. Pratica caminhada e começou meditação guiada.", consentimento=True, perfil="estavel"),
    dict(nome="Bruno · demo", tipo_teste="Multi 12", substancias="Cocaína|Álcool", tempo_uso="5 anos", status="ativo", dias_limpo=3,
         sessoes_semana=2, valor_sessao=200.0, horario_pref="Segundas e quintas, 18h", pacote=(4, 800.0),
         anamnese="Paciente fictício. Lapso recente em evento social. Relata ambivalência e dificuldade com fins de "
                  "semana. Irmão acompanha o tratamento.", consentimento=True, perfil="risco"),
    dict(nome="Carla · demo", tipo_teste="Multi 3", substancias="Benzodiazepínicos", tempo_uso="3 anos", status="ativo", dias_limpo=41,
         sessoes_semana=1, valor_sessao=160.0, horario_pref="Quartas às 10h", pacote=(4, 640.0),
         anamnese="Paciente fictícia. Em redução gradual acompanhada por psiquiatra. Insônia é o principal desafio. "
                  "Responde bem a práticas de respiração e escaneamento corporal.", consentimento=False, perfil="melhora"),
    dict(nome="Diego · demo", tipo_teste="Multi 6", substancias="Maconha|Tabaco/nicotina", tempo_uso="10 anos", status="ativo",
         dias_limpo=19, sessoes_semana=1, valor_sessao=150.0, horario_pref="Sextas às 16h", pacote=(2, 300.0),
         anamnese="Paciente fictício. Uso diário para dormir. Trabalha de casa, rotina desorganizada. "
                  "Objetivo inicial de reduzir, depois parar.", consentimento=False, perfil="oscila"),
    dict(nome="Elisa · demo", tipo_teste="Multi 9", substancias="Crack", tempo_uso="2 anos", status="pausado", dias_limpo=None,
         sessoes_semana=1, valor_sessao=120.0, horario_pref="A combinar", pacote=None,
         anamnese="Paciente fictícia. Tratamento pausado a pedido dela por mudança de cidade. "
                  "Encaminhada ao CAPS AD da nova região.", consentimento=False, perfil="pausado"),
    dict(nome="Fábio · demo", tipo_teste="Multi 1", substancias="Álcool|Jogo", tempo_uso="12 anos", status="alta", dias_limpo=430,
         sessoes_semana=0, valor_sessao=180.0, horario_pref="", pacote=(20, 3600.0),
         anamnese="Paciente fictício. Recebeu alta após 14 meses. Segue frequentando grupo de ajuda mútua "
                  "e faz contato mensal.", consentimento=False, perfil="alta"),
]

ABORDAGENS = ["Escuta terapêutica, respiração consciente", "Prevenção de recaída, surfar a fissura",
              "Meditação guiada", "Reiki, escuta terapêutica", "Entrevista motivacional",
              "Aterramento 5-4-3-2-1, florais", "Escaneamento corporal"]
TAREFAS = ["Praticar a respiração 4-4-6 duas vezes ao dia", "Anotar os gatilhos da semana no check-in",
           "Ligar para alguém da rede de apoio quando a fissura passar de 6", "Caminhar 20 minutos três vezes na semana",
           "Ir a uma reunião do grupo de ajuda mútua", "Manter horário fixo para dormir e acordar",
           "Fazer o escaneamento corporal antes de dormir"]
COMENTARIOS = {
    "estavel": ["Sessão tranquila. Relata semana produtiva e boa relação com a família. Reforçamos as práticas que estão funcionando.",
                "Comemoramos a marca de meses sem uso. Conversamos sobre planos e sobre como lidar com confraternizações do trabalho.",
                "Leve ansiedade por prazo no trabalho, sem fissura relevante. Boa adesão à meditação."],
    "risco": ["Relatou lapso no fim de semana após festa. Muita culpa. Trabalhamos a diferença entre lapso e recaída e montamos um plano para os próximos eventos.",
              "Fissura alta nos últimos dias, principalmente à noite. Combinamos contato com o irmão e redução de exposição a gatilhos.",
              "Ambivalência sobre continuar. Usamos entrevista motivacional para retomar os motivos pessoais para o tratamento."],
    "melhora": ["Insônia um pouco melhor com o escaneamento corporal. Segue a redução orientada pelo médico.",
                "Semana com menos ansiedade. Conseguiu dormir seis horas em quatro noites.",
                "Relata mais disposição. Conversamos sobre retomar atividades que deixou de lado."],
    "oscila": ["Reduziu o uso diário, mas ainda tem dificuldade no horário de dormir. Ajustamos a rotina da noite.",
               "Boa semana, sem uso há quase três semanas. Tabaco segue sendo o desafio maior.",
               "Rotina desorganizada voltou a aparecer. Trabalhamos um plano simples de horários."],
    "pausado": ["Última sessão antes da pausa. Organizamos o encaminhamento e o contato com o novo serviço."],
    "alta": ["Sessão de alta. Revisamos a trajetória, os sinais de alerta e o plano de manutenção."],
}
# Outros indicadores por perfil: tristeza, irritabilidade, sono, energia, abstinencia, isolamento, autoestima
PERFIL_EXTRA = {
    "estavel": (2, 2, 7, 7, 0, 2, 7), "risco": (6, 7, 3, 4, 4, 6, 3), "melhora": (4, 3, 4, 5, 3, 3, 5),
    "oscila": (4, 5, 4, 4, 2, 5, 5), "pausado": (5, 5, 4, 4, 2, 6, 4), "alta": (1, 1, 8, 8, 0, 1, 8),
}
CAMPOS_EXTRA = ["tristeza", "irritabilidade", "sono", "energia", "abstinencia", "isolamento", "autoestima"]
PERFIL_NUM = {  # (humor, ansiedade, motivacao, fissura) aproximados
    "estavel": (4, 3, 8, 1), "risco": (2, 7, 4, 8), "melhora": (3, 5, 6, 3),
    "oscila": (3, 5, 5, 5), "pausado": (3, 5, 4, 5), "alta": (5, 2, 9, 0),
}
RISCO_PERFIL = {"estavel": "baixo", "risco": "alto", "melhora": "baixo", "oscila": "moderado",
                "pausado": "moderado", "alta": "baixo"}
GATILHOS = ["Estresse", "Solidão", "Tédio", "Cansaço", "Festa ou evento", "Conflito familiar"]

TRANSCRICAO_EXEMPLO = (
    "Sessão com a Carla hoje, cinquenta minutos. Ela chegou mais animada, contou que dormiu melhor em quatro "
    "noites da semana usando o escaneamento corporal antes de deitar. Ainda acorda de madrugada, mas consegue "
    "voltar a dormir. A redução do remédio segue com o psiquiatra, sem sintomas fortes de abstinência. Ansiedade "
    "em torno de cinco, fissura baixa, uns três. Fizemos respiração e conversamos sobre voltar a nadar. "
    "Combinei que ela vai manter o escaneamento todas as noites e anotar como dormiu no check-in.")
SUGESTAO_EXEMPLO = {
    "resumo": "Paciente relata melhora do sono em quatro noites com o escaneamento corporal. Redução medicamentosa "
              "segue com acompanhamento psiquiátrico, sem sinais importantes de abstinência. Ansiedade moderada e "
              "fissura baixa. Sessão com respiração e conversa sobre retomar atividade física (natação).",
    "humor": 4, "ansiedade": 5, "motivacao": 7, "fissura": 3, "uso_recente": False, "risco": "baixo",
    "sinais_alerta": [], "abordagens": "Respiração consciente, escaneamento corporal",
    "tarefa_paciente": "Fazer o escaneamento corporal todas as noites e anotar o sono no check-in",
}


def carregar(m, terapeuta):
    """m: módulo app (modelos, db, hoje, agora). Cria tudo e anota em DemoItem."""
    db, hoje, agora = m.db, m.hoje(), m.agora()
    rnd = random.Random(42)
    criados = []

    def anota(tipo, obj):
        db.session.flush()
        criados.append(m.DemoItem(terapeuta_id=terapeuta.id, tipo=tipo, ref_id=obj.id))

    def perto(v, lo, hi, var=1):
        return max(lo, min(hi, v + rnd.randint(-var, var)))

    pacientes = []
    for i, d in enumerate(PACIENTES):
        p = m.Paciente(terapeuta_id=terapeuta.id, nome=d["nome"], substancias=d["substancias"], tipo_teste=d["tipo_teste"],
                       tempo_uso=d["tempo_uso"], status=d["status"], sessoes_semana=d["sessoes_semana"],
                       valor_sessao=d["valor_sessao"], horario_pref=d["horario_pref"] or None,
                       anamnese=d["anamnese"], telefone=f"(11) 90000-00{i + 1:02d}",
                       emergencia_nome="Contato de apoio · demo", emergencia_tel=f"(11) 90000-10{i + 1:02d}",
                       nascimento=hoje.replace(year=hoje.year - (26 + i * 6)) - timedelta(days=37 * i),
                       inicio_tratamento=hoje - timedelta(days=[190, 75, 120, 45, 150, 520][i]),
                       ultimo_uso=(hoje - timedelta(days=d["dias_limpo"])) if d["dias_limpo"] is not None else None)
        db.session.add(p)
        anota("paciente", p)
        pacientes.append((p, d))

    # sessões passadas com registro, uma por semana nas últimas 5 semanas
    base_horas = [14, 18, 10, 16, 11, 15]
    for idx, (p, d) in enumerate(pacientes):
        perfil = d["perfil"]
        semanas = {"pausado": [4], "alta": [3]}.get(perfil, [5, 4, 3, 2, 1])
        h, a, mo, f = PERFIL_NUM[perfil]
        for n, s in enumerate(semanas):
            dia = hoje - timedelta(days=7 * s + idx % 3)
            inicio = datetime.combine(dia, time(base_horas[idx]))
            faltou = perfil == "oscila" and s == 3
            c = m.Consulta(terapeuta_id=terapeuta.id, paciente_id=p.id, inicio=inicio, duracao=50,
                           tipo="online" if perfil == "oscila" and s % 2 else "individual",
                           status="faltou" if faltou else "realizada")
            if not faltou:
                c.checkin_em = inicio + timedelta(minutes=rnd.randint(-3, 12))
                c.checkout_em = c.checkin_em + timedelta(minutes=rnd.randint(44, 68))
            db.session.add(c)
            db.session.flush()
            tendencia = (len(semanas) - n) if perfil == "melhora" else 0
            teste = perfil in ("risco", "estavel") and s in (4, 1)
            r = m.Registro(terapeuta_id=terapeuta.id, paciente_id=p.id, consulta_id=c.id, data=dia,
                           realizada=not faltou,
                           humor=None if faltou else perto(h - (1 if tendencia > 3 else 0), 1, 5),
                           ansiedade=None if faltou else perto(a + tendencia // 2, 0, 10),
                           motivacao=None if faltou else perto(mo, 0, 10),
                           fissura=None if faltou else perto(f + tendencia // 2, 0, 10),
                           uso_recente=(perfil == "risco" and s == 1),
                           data_uso=(hoje - timedelta(days=3)) if (perfil == "risco" and s == 1) else None,
                           teste_feito=teste, teste_tipo=d["tipo_teste"] if teste else None,
                           teste_resultado=("positivo" if perfil == "risco" and s == 1 else "negativo") if teste else None,
                           risco="baixo" if faltou else (RISCO_PERFIL[perfil] if s <= 2 else
                                                         "moderado" if perfil == "risco" else "baixo"),
                           abordagens=None if faltou else rnd.choice(ABORDAGENS),
                           comentarios="Paciente não compareceu e não avisou. Enviei mensagem para remarcar."
                           if faltou else COMENTARIOS[perfil][n % len(COMENTARIOS[perfil])],
                           tarefa_paciente=None if faltou else rnd.choice(TAREFAS))
            if not faltou:
                for campo, base_v in zip(CAMPOS_EXTRA, PERFIL_EXTRA[perfil]):
                    if rnd.random() < 0.85:  # nem todo indicador é avaliado em toda sessão
                        setattr(r, campo, perto(base_v - (tendencia // 2 if campo in ("sono", "energia") else -(tendencia // 3)), 0, 10))
            if perfil == "risco" and s == 1:
                r.feedback_ia = ("[Exemplo de feedback gerado por IA]\n\nMomento: lapso recente com culpa intensa e fissura "
                                 "alta à noite, o que indica período de vulnerabilidade.\n\nAtenção: risco de recaída nas próximas "
                                 "semanas, isolamento e ambivalência sobre o tratamento.\n\nSugestões: reforçar o plano para eventos "
                                 "sociais, envolver a rede de apoio combinada e considerar encontros mais frequentes nesta fase.")
            db.session.add(r)

    # hoje: uma sessão já passou (aparece em Fim de sessão) e outra mais tarde
    ativos = [p for p, d in pacientes if d["status"] == "ativo"]
    ref = agora.replace(minute=0, second=0, microsecond=0)
    for p, delta in [(ativos[1], -2), (ativos[0], 3)]:
        inicio = ref + timedelta(hours=delta)
        if inicio.date() != hoje:
            inicio = datetime.combine(hoje, time(9 if delta < 0 else 20))
        db.session.add(m.Consulta(terapeuta_id=terapeuta.id, paciente_id=p.id, inicio=inicio, duracao=50,
                                  tipo="individual", status="agendada",
                                  notas_pre="Retomar o plano para o fim de semana." if delta < 0 else None))
    # próximas duas semanas
    for idx, p in enumerate(ativos):
        for semana in (1, 2):
            dia = hoje + timedelta(days=semana * 7 - 3 + idx)
            db.session.add(m.Consulta(terapeuta_id=terapeuta.id, paciente_id=p.id,
                                      inicio=datetime.combine(dia, time(base_horas[idx])), duracao=50,
                                      tipo="online" if idx == 3 else "individual", status="agendada",
                                      notas_pre="Perguntar sobre o sono." if idx == 2 and semana == 1 else None))
    db.session.add(m.Consulta(terapeuta_id=terapeuta.id, paciente_id=ativos[3].id,
                              inicio=datetime.combine(hoje + timedelta(days=1), time(17)), duracao=50,
                              tipo="online", status="cancelada", notas_pre="Paciente pediu para remarcar."))

    # check-ins diários dos últimos 30 dias
    for p, d in pacientes:
        if d["status"] != "ativo":
            continue
        h, a, mo, f = PERFIL_NUM[d["perfil"]]
        for k in range(30):
            dia = hoje - timedelta(days=29 - k)
            if rnd.random() < 0.15:
                continue
            fis = f
            if d["perfil"] == "risco":
                fis = f - 3 + (k // 8)
            if d["perfil"] == "melhora":
                fis = 6 - k // 7
            usou = d["perfil"] == "risco" and dia == hoje - timedelta(days=3)
            db.session.add(m.CheckIn(paciente_id=p.id, data=dia,
                                     humor=perto(h - (1 if usou else 0), 1, 5),
                                     fissura=perto(fis + (2 if usou else 0), 0, 10), sono=perto(3, 1, 5),
                                     usou=usou, gatilhos=", ".join(rnd.sample(GATILHOS, rnd.randint(0, 2))) or None,
                                     nota="Dia difícil depois da festa." if usou else None))

    # pagamentos
    for p, d in pacientes:
        if d["pacote"]:
            sess, valor = d["pacote"]
            db.session.add(m.Pagamento(paciente_id=p.id, valor=valor, sessoes=sess,
                                       data=hoje - timedelta(days=36), nota="Pacote · demo (Pix)"))

    # termos de consentimento de exemplo
    for p, d in pacientes:
        if d["consentimento"]:
            db.session.add(m.Consentimento(paciente_id=p.id, terapeuta_id=terapeuta.id,
                                           assinado_em=hoje - timedelta(days=60), versao="exemplo-demo",
                                           arquivo=PDF_EXEMPLO, arquivo_tipo="application/pdf",
                                           arquivo_nome=f"termo-exemplo-{p.id}.pdf"))

    # uma transcrição aguardando revisão
    carla = next(p for p, d in pacientes if d["perfil"] == "melhora")
    t = m.Transcricao(terapeuta_id=terapeuta.id, paciente_id=carla.id, tipo="resumo", status="transcrita",
                      texto=TRANSCRICAO_EXEMPLO, texto_original=TRANSCRICAO_EXEMPLO, partes=1, segundos=94,
                      criado_em=agora - timedelta(minutes=40))
    db.session.add(t)

    # um conteúdo próprio na biblioteca
    a = m.Artigo(autor_id=terapeuta.id, categoria="pratica", publicado=True,
                 titulo="Ritual da noite (exemplo)",
                 resumo="Uma sequência curta para desacelerar antes de dormir.",
                 corpo="Conteúdo de exemplo criado pelo terapeuta.\n\n## Passo a passo\n"
                       "- Desligue telas 30 minutos antes de deitar\n- Faça três minutos de respiração 4-4-6\n"
                       "- Escreva uma coisa boa do dia\n- Termine com o escaneamento corporal")
    db.session.add(a)
    anota("artigo", a)

    quantidades = {"Multi 1": 12, "Multi 2": 6, "Multi 3": 9, "Multi 6": 3, "Multi 9": 7, "Multi 12": 2}
    for e in m.estoques(terapeuta):
        e.quantidade, e.minimo = quantidades.get(e.tipo, 5), 5
    db.session.add_all(criados)
    db.session.commit()
    return len(pacientes)


def apagar(m, terapeuta):
    db = m.db
    itens = m.DemoItem.query.filter_by(terapeuta_id=terapeuta.id).all()
    ids = [i.ref_id for i in itens if i.tipo == "paciente"]
    if ids:
        for modelo in (m.Transcricao, m.Registro, m.CheckIn, m.Pagamento, m.Consentimento, m.Consulta):
            modelo.query.filter(modelo.paciente_id.in_(ids)).delete(synchronize_session=False)
        m.Paciente.query.filter(m.Paciente.id.in_(ids), m.Paciente.terapeuta_id == terapeuta.id).delete(synchronize_session=False)
    arts = [i.ref_id for i in itens if i.tipo == "artigo"]
    if arts:
        m.Artigo.query.filter(m.Artigo.id.in_(arts), m.Artigo.autor_id == terapeuta.id).delete(synchronize_session=False)
    m.DemoItem.query.filter_by(terapeuta_id=terapeuta.id).delete(synchronize_session=False)
    db.session.commit()
    return len(ids)
