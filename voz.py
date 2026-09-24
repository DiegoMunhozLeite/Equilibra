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

import requests

TRANSCRICAO_URL = os.environ.get("TRANSCRICAO_URL", "https://api.openai.com/v1/audio/transcriptions")
TRANSCRICAO_MODELO = os.environ.get("TRANSCRICAO_MODELO", "whisper-1")
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
    try:
        resp = requests.post(
            TRANSCRICAO_URL,
            headers={"Authorization": f"Bearer {chave}"},
            files={"file": (nome_arquivo, dados, tipo or "application/octet-stream")},
            data={"model": TRANSCRICAO_MODELO, "language": "pt", "response_format": "json"},
            timeout=170,
        )
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
Abaixo está a transcrição automática de {origem}. A transcrição pode ter erros de reconhecimento de fala.

Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois e sem crases, com estas chaves:
- "resumo": texto em português do Brasil, até 200 palavras, com os temas da sessão, estado do paciente e combinados
- "humor": inteiro de 1 (muito mal) a 5 (muito bem), ou null se não der para inferir
- "ansiedade": inteiro de 0 a 10, ou null
- "motivacao": inteiro de 0 a 10, ou null
- "fissura": inteiro de 0 a 10, ou null
- "uso_recente": true, false ou null
- "risco": "baixo", "moderado", "alto" ou "critico"
- "sinais_alerta": lista de frases curtas sobre riscos mencionados (ideação suicida, autolesão, abstinência grave, overdose, violência, abandono do tratamento); lista vazia se não houver
- "abordagens": texto curto com práticas ou técnicas usadas na sessão, ou ""
- "tarefa_paciente": uma tarefa ou combinado para o paciente até a próxima sessão, ou ""

Regras: não faça diagnóstico, não sugira medicamentos nem doses, não invente informações que não estão na
transcrição. Se houver qualquer menção a ideação suicida ou risco à vida, use risco "critico" e registre em sinais_alerta.

Transcrição:
\"\"\"{texto}\"\"\""""


def resumir(texto: str, tipo: str) -> dict:
    if modo_avaliacao():
        dados = dict(RESUMO_SIMULADO)
        dados["resumo"] = AVISO_SIMULACAO + " " + dados["resumo"]
        return dados
    origem = ("uma gravação da própria sessão (terapeuta e paciente conversando)" if tipo == "consulta"
              else "um áudio em que o terapeuta relata como foi a sessão")
    bruto = chamar_claude(PROMPT_RESUMO.format(origem=origem, texto=texto[:120000]), max_tokens=1500)
    bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip()).strip()
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    try:
        dados = json.loads(bruto[inicio:fim + 1])
    except (ValueError, TypeError):
        raise ErroVoz("A IA respondeu num formato inesperado. Tente gerar o resumo de novo.")

    def inteiro(v, lo, hi):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return None

    alertas = [str(a)[:200] for a in (dados.get("sinais_alerta") or []) if a][:8]
    risco = dados.get("risco") if dados.get("risco") in ("baixo", "moderado", "alto", "critico") else "baixo"
    if alertas and risco == "baixo":
        risco = "moderado"
    uso = dados.get("uso_recente")
    return {
        "resumo": str(dados.get("resumo") or "").strip(),
        "humor": inteiro(dados.get("humor"), 1, 5),
        "ansiedade": inteiro(dados.get("ansiedade"), 0, 10),
        "motivacao": inteiro(dados.get("motivacao"), 0, 10),
        "fissura": inteiro(dados.get("fissura"), 0, 10),
        "uso_recente": uso if isinstance(uso, bool) else None,
        "risco": risco,
        "sinais_alerta": alertas,
        "abordagens": str(dados.get("abordagens") or "")[:200],
        "tarefa_paciente": str(dados.get("tarefa_paciente") or "")[:300],
    }
