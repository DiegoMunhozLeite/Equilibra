# Equilibra

App de acompanhamento holístico em dependência química, para terapeuta e paciente.
Feito em Python (Flask) como PWA: instala no iPhone pelo Safari, sem App Store.

## O que tem

**Terapeuta**
- Início: sessões do dia, pacientes em atenção, estoque de testes toxicológicos com alerta de reposição
- Agenda semanal, com status e notas pré-sessão
- Fim de sessão: grave seu relato ou a sessão inteira; a IA transcreve, resume e preenche o registro para você revisar
- Pacientes: ficha, tempo sem uso com conquistas, pagamentos por pacote, termo de consentimento de gravação, link de convite
- Registros pós-sessão: humor, ansiedade, motivação, fissura, uso recente, teste, risco, abordagens, tarefa para o paciente
- Mood: distribuição e tendência do humor por período e paciente
- Biblioteca: conteúdos prontos sobre substâncias, recuperação e práticas, e os seus próprios

**Paciente** (entra por link de convite, cria a própria senha)
- Check-in diário de humor, vontade de usar, sono e gatilhos
- Dias sem uso, conquistas, próxima sessão e combinados da semana
- Respiração guiada, conteúdos e tela de ajuda com 188 (CVV) e 192 (SAMU)

## Gravação e privacidade

- **O áudio nunca é guardado.** Ele é gravado em partes de até 10 minutos, cada parte é enviada para transcrição e descartada logo depois. Só o texto fica no banco.
- **Gravar a sessão inteira exige termo ativo.** Anexe o termo assinado na ficha do paciente. Sem ele, ou depois de uma revogação, o botão fica bloqueado. A cada gravação você confirma que avisou o paciente.
- **O nome do paciente é trocado por [paciente]** antes de o texto ir para a IA de resumo. O serviço de transcrição recebe o áudio como foi gravado, então evite dizer nome completo na gravação.
- **Nada entra no prontuário sem revisão.** A IA só sugere; você confere e salva.
- Páginas com dados de pacientes não ficam em cache no aparelho.

### Sugestão de itens para o seu termo de consentimento

Revise com um advogado. Itens que costumam ser pedidos pela LGPD para dados de saúde:
- finalidade da gravação (apoio ao registro clínico) e que o áudio é apagado após virar texto
- quais serviços processam os dados: provedor de transcrição, provedor de IA para resumo e hospedagem do app
- por quanto tempo o texto fica guardado e quem tem acesso
- direito de recusar sem prejuízo ao atendimento e de revogar a qualquer momento
- versão e data do termo, que você registra no app

## Limitações conhecidas no iPhone

- Mantenha o app aberto e a tela ligada durante a gravação. Se o iPhone bloquear a tela ou você trocar de app, o microfone pode pausar. O app pede para a tela não apagar quando o sistema permite.
- Uma parte que falhar três vezes na transcrição é perdida (o áudio não é guardado para nova tentativa). O app avisa quando isso acontece.
- Áudios do WhatsApp podem ser enviados pela opção "Enviar um áudio já gravado", depois de salvos em Arquivos.

## Rodar no computador

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
FLASK_ENV=development python app.py
```

Abra http://localhost:5000 e crie sua conta de terapeuta. O microfone só funciona em `localhost` ou em HTTPS.

## Publicar (Render)

1. Suba esta pasta para um repositório privado no GitHub.
2. No Render, escolha **New > Blueprint** e aponte para o repositório. O `render.yaml` cria o app e o banco Postgres.
3. Em **Environment**, preencha:
   - `CODIGO_CADASTRO`: um código que só você conhece; impede que estranhos criem conta de terapeuta
   - `OPENAI_API_KEY`: ativa a transcrição (Whisper)
   - `ANTHROPIC_API_KEY`: ativa resumos e feedback clínico (crie em console.anthropic.com)
4. Abra o endereço `https://…onrender.com` gerado.

Nunca coloque chaves no código ou no GitHub; use só as variáveis de ambiente. Os planos e preços do Render mudam; confira no site antes de publicar. Evite planos em que o banco expira ou o disco é apagado, porque prontuário não pode sumir.

Outros provedores compatíveis de transcrição podem ser usados com `TRANSCRICAO_URL` e `TRANSCRICAO_MODELO`. O modelo de IA de resumo pode ser trocado com `ANTHROPIC_MODEL`.

## Instalar no iPhone

1. Abra o endereço do app no **Safari**.
2. Toque em **Compartilhar** e depois em **Adicionar à Tela de Início**.
3. O Equilibra abre em tela cheia, com ícone próprio. Faça o mesmo no iPhone do paciente, depois que ele criar o acesso pelo link de convite.

## Arquivos

- `app.py`: rotas, modelos e regras
- `voz.py`: transcrição, anonimização e resumo por IA
- `conteudo_base.py`: textos iniciais da biblioteca (revise antes de liberar aos pacientes)
- `templates/`, `static/`: telas, estilo, ícones, manifest e service worker
