"""
Transcrição de áudio e resumo por IA.

- Transcrição: API de voz para texto compatível com OpenAI (/v1/audio/transcriptions).
  Configure OPENAI_API_KEY. Opcional: TRANSCRICAO_URL e TRANSCRICAO_MODELO
  para usar outro provedor compatível.
- Resumo: API do Claude. Configure ANTHROPIC_API_KEY (opcional: ANTHROPIC_MODEL).

O áudio nunca é salvo em disco pelo app: chega em memória, vai para a transcrição
e é descartado em seguida, com sucesso ou erro.
"""
import json
import os
import re
import unicodedata

import requests

TRANSCRICAO_URL = os.environ.get("TRANSCRICAO_URL", "https://api.openai.com/v1/audio/transcriptions")
# Modelo mais preciso por padrão; se o provedor recusar, tenta de novo com o modelo reserva.
TRANSCRICAO_MODELO = os.environ.get("TRANSCRICAO_MODELO", "gpt-4o-transcribe")
TRANSCRICAO_RESERVA = os.environ.get("TRANSCRICAO_RESERVA", "whisper-1")
# Vocabulário de apoio: ajuda o reconhecimento de termos do contexto clínico e holístico.
VOCABULARIO = (
    "Sessão de terapia holística em dependência química, em português do Brasil. Termos frequentes: "
    "fissura, abstinência, lapso, recaída, redução de danos, CAPS AD, Narcóticos Anônimos, NA, AA, "
    "Alcoólicos Anônimos, teste toxicológico, Multi 6, Multi 12, benzodiazepínico, clonazepam, "
    "cocaína, crack, maconha, álcool, cachaça, opioide, reiki, florais, aromaterapia, constelação, "
    "meditação, respiração consciente, aterramento, escaneamento corporal, entrevista motivacional, "
    "prevenção de recaída, gatilho, pino, pedra, beck, noia, rebite.")
LIMITE_AUDIO = 25 * 1024 * 1024  # limite de arquivo da maioria das APIs de transcrição


class ErroVoz(Exception):
    pass


def modo_avaliacao():
    """Com MODO_AVALIACAO=1 nenhuma API paga é chamada, mesmo com chaves configuradas."""
    return os.environ.get("MODO_AVALIACAO", "").strip().lower() in ("1", "true", "sim", "yes")


def transcricao_ativa():
    return modo_avaliacao() or bool(os.environ.get("OPENAI_API_KEY"))


def ia_ativa():
    return modo_avaliacao() or bool(os.environ.get("ANTHROPIC_API_KEY"))


AVISO_SIMULACAO = "[Simulação do modo avaliação: nenhum áudio foi enviado e nenhuma IA foi usada.]"
TEXTO_SIMULADO = (
    "Sessão de cinquenta minutos. O paciente chegou mais tranquilo do que na semana passada e contou que "
    "conseguiu passar o fim de semana sem usar, apesar de um convite para uma festa. Disse que a fissura "
    "apareceu no sábado à noite, perto de seis, e que usou a respiração e ligou para o irmão. Ansiedade em "
    "torno de cinco por causa do trabalho. Dormiu melhor em três noites. Trabalhamos prevenção de recaída e "
    "fizemos o aterramento cinco quatro três dois um. Combinamos que ele vai anotar os gatilhos no check-in "
    "e planejar uma saída alternativa para o próximo convite.")
RESUMO_SIMULADO = {
    "resumo": "Paciente passou o fim de semana sem uso apesar de convite para festa. Fissura moderada no sábado à "
              "noite, manejada com respiração e contato com a rede de apoio. Ansiedade moderada ligada ao trabalho "
              "e melhora parcial do sono. Sessão com prevenção de recaída e aterramento.",
    "humor": 4, "ansiedade": 5, "motivacao": 7, "fissura": 6, "uso_recente": False, "risco": "moderado",
    "sinais_alerta": ["Exposição a convites sociais com oferta da substância"],
    "abordagens": "Prevenção de recaída, aterramento 5-4-3-2-1, respiração",
    "tarefa_paciente": "Anotar os gatilhos no check-in e planejar uma alternativa para o próximo convite",
}
FEEDBACK_SIMULADO = (
    "Momento: fase de consolidação, com boa resposta às estratégias de enfrentamento e uso ativo da rede de apoio.\n\n"
    "Atenção: situações sociais seguem como principal gatilho; ansiedade ligada ao trabalho pode aumentar a fissura.\n\n"
    "Sugestões: ensaiar respostas para convites, reforçar a rotina de sono e revisar o plano de crise na próxima sessão.")


def transcrever(dados: bytes, nome_arquivo: str, tipo: str) -> str:
    """Envia o áudio (em memória) e devolve o texto. Não guarda nada."""
    if modo_avaliacao():
        del dados
        return AVISO_SIMULACAO + "\n\n" + TEXTO_SIMULADO
    chave = os.environ.get("OPENAI_API_KEY")
    if not chave:
        raise ErroVoz("A transcrição não está configurada neste servidor.")
    if len(dados) > LIMITE_AUDIO:
        raise ErroVoz("Arquivo de áudio acima de 25 MB. Grave em partes menores.")
    def enviar(modelo):
        return requests.post(
            TRANSCRICAO_URL,
            headers={"Authorization": f"Bearer {chave}"},
            files={"file": (nome_arquivo, dados, tipo or "application/octet-stream")},
            data={"model": modelo, "language": "pt", "response_format": "json",
                  "prompt": VOCABULARIO, "temperature": "0"},
            timeout=170,
        )
    try:
        resp = enviar(TRANSCRICAO_MODELO)
        if resp.status_code in (400, 404) and TRANSCRICAO_RESERVA and TRANSCRICAO_RESERVA != TRANSCRICAO_MODELO:
            resp = enviar(TRANSCRICAO_RESERVA)
    except requests.RequestException:
        raise ErroVoz("Sem conexão com o serviço de transcrição.")
    finally:
        del dados  # descarta o áudio da memória o quanto antes
    if resp.status_code != 200:
        raise ErroVoz(f"O serviço de transcrição recusou o áudio (código {resp.status_code}).")
    return (resp.json().get("text") or "").strip()


def chamar_claude(prompt: str, max_tokens: int = 1200) -> str:
    if modo_avaliacao():
        return AVISO_SIMULACAO + "\n\n" + FEEDBACK_SIMULADO
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise ErroVoz("A IA não está configurada neste servidor.")
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"), "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=120,
        )
    except requests.RequestException:
        raise ErroVoz("Sem conexão com o serviço de IA.")
    if resp.status_code != 200:
        raise ErroVoz(f"O serviço de IA respondeu com erro (código {resp.status_code}).")
    return "\n".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text").strip()


def anonimizar(texto: str, nomes) -> str:
    """Troca partes do nome do paciente por [paciente] antes de enviar à IA."""
    for nome in nomes:
        for parte in (nome or "").split():
            if len(parte) >= 3:
                texto = re.sub(rf"\b{re.escape(parte)}\b", "[paciente]", texto, flags=re.IGNORECASE)
    return texto


PROMPT_RESUMO = """Você apoia um terapeuta holístico que acompanha pessoas em recuperação de dependência química.
Abaixo está a transcrição de {origem}, já revisada pelo terapeuta.

REGRA PRINCIPAL: use somente o que está escrito na transcrição. Não deduza, não complete e não interprete além
do que foi dito. Cada valor que você preencher precisa vir com um "trecho": uma cópia EXATA, palavra por palavra,
de uma parte curta da transcrição que justifica o valor. Se não houver trecho que justifique, use valor null.

Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois e sem crases, com estas chaves:
- "resumo": até 200 palavras, em português do Brasil, só com fatos presentes na transcrição
- "humor": {{"valor": inteiro de 1 (muito mal) a 5 (muito bem) ou null, "trecho": "..."}}
- "uso_recente": {{"valor": true, false ou null, "trecho": "..."}}
- "indicadores": objeto com as chaves {chaves}; cada uma no formato {{"valor": inteiro de 0 a 10 ou null, "trecho": "..."}}
  Significado: {significados}
- "risco": "baixo", "moderado", "alto" ou "critico"
- "sinais_alerta": lista de {{"texto": frase curta, "trecho": "..."}} sobre ideação suicida, autolesão, abstinência grave,
  overdose, violência ou abandono do tratamento; lista vazia se não houver
- "abordagens": práticas ou técnicas citadas na transcrição, ou ""
- "tarefa_paciente": combinado para o paciente citado na transcrição, ou ""

Outras regras: não faça diagnóstico, não sugira medicamentos nem doses. Qualquer menção a ideação suicida ou risco
à vida exige risco "critico" e um item em sinais_alerta.

Transcrição:
\"\"\"{texto}\"\"\""""


def _normalizar(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9\[\] ]+", " ", t).split())


def trecho_confere(trecho, texto_normalizado):
    """O trecho citado pela IA precisa existir de fato na transcrição."""
    n = _normalizar(trecho)
    return len(n) >= 6 and n in texto_normalizado


def resumir(texto: str, tipo: str, indicadores) -> dict:
    """indicadores: lista (campo, rótulo, positivo). Só aceita valores com trecho encontrado no texto."""
    if modo_avaliacao():
        return _resumo_simulado()
    campos = [c for c, _, _ in indicadores]
    origem = ("uma gravação da própria sessão (terapeuta e paciente conversando)" if tipo == "consulta"
              else "um áudio em que o terapeuta relata como foi a sessão")
    prompt = PROMPT_RESUMO.format(origem=origem, texto=texto[:120000], chaves=", ".join(f'"{c}"' for c in campos),
                                  significados="; ".join(f"{c} = {r.lower()}" for c, r, _ in indicadores))
    bruto = chamar_claude(prompt, max_tokens=2500)
    bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip()).strip()
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    try:
        dados = json.loads(bruto[inicio:fim + 1])
    except (ValueError, TypeError):
        raise ErroVoz("A IA respondeu num formato inesperado. Tente gerar o resumo de novo.")
    return validar_resumo(dados, texto, campos)


def validar_resumo(dados, texto, campos):
    base = _normalizar(texto)
    saida = {"evidencias": {}, "descartados": []}

    def item(chave, bruto, lo=None, hi=None, booleano=False):
        bruto = bruto if isinstance(bruto, dict) else {"valor": bruto, "trecho": ""}
        valor, trecho = bruto.get("valor"), str(bruto.get("trecho") or "").strip()
        if booleano:
            valor = valor if isinstance(valor, bool) else None
        else:
            try:
                valor = max(lo, min(hi, int(valor)))
            except (TypeError, ValueError):
                valor = None
        if valor is None:
            return None
        if not trecho_confere(trecho, base):
            saida["descartados"].append(chave)  # sem prova na transcrição: não entra
            return None
        saida["evidencias"][chave] = trecho[:300]
        return valor

    saida["humor"] = item("humor", dados.get("humor"), 1, 5)
    saida["uso_recente"] = item("uso_recente", dados.get("uso_recente"), booleano=True)
    ind = dados.get("indicadores") or {}
    for c in campos:
        saida[c] = item(c, ind.get(c), 0, 10)

    alertas = []
    for a in (dados.get("sinais_alerta") or [])[:8]:
        if isinstance(a, dict):
            txt, tr = str(a.get("texto") or "").strip(), str(a.get("trecho") or "").strip()
        else:
            txt, tr = str(a).strip(), ""
        if txt:  # alertas nunca são descartados; só marcamos quando o trecho não foi encontrado
            alertas.append({"texto": txt[:200], "trecho": tr[:300] if trecho_confere(tr, base) else ""})
    risco = dados.get("risco") if dados.get("risco") in ("baixo", "moderado", "alto", "critico") else "baixo"
    if alertas and risco == "baixo":
        risco = "moderado"
    saida.update({
        "resumo": str(dados.get("resumo") or "").strip(),
        "risco": risco, "sinais_alerta": alertas,
        "abordagens": str(dados.get("abordagens") or "")[:200],
        "tarefa_paciente": str(dados.get("tarefa_paciente") or "")[:300],
    })
    return saida


def _resumo_simulado():
    base = TEXTO_SIMULADO
    bruto = {
        "resumo": AVISO_SIMULACAO + " " + RESUMO_SIMULADO["resumo"],
        "humor": {"valor": 4, "trecho": "chegou mais tranquilo do que na semana passada"},
        "uso_recente": {"valor": False, "trecho": "conseguiu passar o fim de semana sem usar"},
        "indicadores": {
            "ansiedade": {"valor": 5, "trecho": "Ansiedade em torno de cinco por causa do trabalho"},
            "fissura": {"valor": 6, "trecho": "a fissura apareceu no sábado à noite, perto de seis"},
            "sono": {"valor": 6, "trecho": "Dormiu melhor em três noites"},
            "motivacao": {"valor": 7, "trecho": "vai anotar os gatilhos no check-in"},
            "isolamento": {"valor": 3, "trecho": "ligou para o irmão"},
        },
        "risco": "moderado",
        "sinais_alerta": [{"texto": "Exposição a convites sociais com oferta da substância",
                           "trecho": "um convite para uma festa"}],
        "abordagens": RESUMO_SIMULADO["abordagens"], "tarefa_paciente": RESUMO_SIMULADO["tarefa_paciente"],
    }
    return validar_resumo(bruto, base, ["ansiedade", "motivacao", "fissura", "tristeza", "irritabilidade",
                                        "sono", "energia", "abstinencia", "isolamento", "autoestima"])
