# Equilibra

App de acompanhamento holístico em dependência química, para terapeuta e paciente.
Feito em Python (Flask) como PWA: instala no iPhone pelo Safari, sem App Store.

## O que tem

**Terapeuta**
- Início: sessões do dia, atendimento em andamento, tempo atendido no mês, pacientes em atenção e estoque de testes por tipo (Multi 1 a Multi 12) com alerta de reposição
- Agenda semanal, com status, notas pré-sessão e check-in/check-out do atendimento
- Relatório mensal do tempo de atendimento: total, média, minutos por dia, por paciente e comparação com o mês anterior
- Fim de sessão: grave seu relato ou a sessão inteira; a IA transcreve, resume e preenche o registro para você revisar
- Pacientes: ficha, tempo sem uso com conquistas, pagamentos por pacote, termo de consentimento de gravação, link de convite
- Registros pós-sessão: humor, 10 indicadores (ansiedade, motivação, fissura, tristeza, irritabilidade, sono, energia, abstinência física, isolamento e autoestima), uso recente, teste por tipo, risco, abordagens e tarefa para o paciente
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
- **Você confere a transcrição antes do resumo.** Depois de gravar, o app mostra o texto para você corrigir. A IA só resume o texto revisado, e a versão original fica guardada.
- **A IA precisa provar cada valor.** Cada indicador sugerido vem com o trecho exato da transcrição que o justifica. O app confere se o trecho existe; se não existir, o valor é descartado e fica como "não avaliado".
- **Nada entra no prontuário sem revisão.** A IA só sugere; você confere e salva.
- Nenhuma transcrição automática é 100% fiel. O modelo padrão é o `gpt-4o-transcribe`, com um vocabulário de apoio do contexto clínico e holístico; se ele não estiver disponível, o app usa o `whisper-1`. Ambos podem ser trocados por `TRANSCRICAO_MODELO` e `TRANSCRICAO_RESERVA`.
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

## Segurança e LGPD (v8)

- **Criptografia:** anamnese, anotações e notas de sessão, feedback da IA, transcrições e notas dos check-ins ficam criptografados no banco. A chave vem de `CHAVE_DADOS` (criada automaticamente pelo `render.yaml`) e, como reserva, de `SECRET_KEY`. **Nunca apague nem troque essas duas variáveis no Render**: sem elas, os textos criptografados não podem mais ser lidos. Anote os valores num gerenciador de senhas.
- **Saída por inatividade:** o terapeuta sai sozinho após `INATIVIDADE_MIN` minutos sem uso (padrão 60).
- **Verificação em duas etapas:** opcional, em Minha conta. Usa o app Senhas do iPhone ou qualquer autenticador, com 8 códigos de recuperação.
- **Recuperação de senha:** pacientes recebem um link gerado pelo terapeuta na ficha. Para envio por e-mail, preencha `SMTP_HOST`, `SMTP_PORTA`, `SMTP_USUARIO`, `SMTP_SENHA` e `EMAIL_REMETENTE` com os dados de um serviço de e-mail transacional ou de uma senha de app do seu provedor. Sem e-mail configurado, um administrador gera o link de um terapeuta no Shell do Render com `flask --app app link-senha email@do.terapeuta`.
- **Registro de acessos:** cada abertura de ficha, registro, transcrição, relatório ou exportação fica anotada.
- **Direitos do titular:** exportar e excluir todos os dados de um paciente na ficha dele; o paciente baixa uma cópia em Minha conta; o terapeuta baixa tudo em Minha conta.
- **Termos e privacidade:** modelos em `/termos` e `/privacidade`. Revise com um advogado e preencha os campos entre colchetes antes de usar com pacientes reais.
- **Backup:** confira no painel do banco no Render se o plano tem backups automáticos e como restaurá-los. Como reforço, baixe periodicamente a cópia completa em Minha conta.

## Demonstração para terapeutas

- **Modo avaliação** (`MODO_AVALIACAO=1`, já ligado no `render.yaml`): nenhuma API paga é chamada; transcrição, resumo e feedback são exemplos simulados e identificados.
- **Dados de demonstração:** no fim do painel, "Carregar dados de demonstração" cria pacientes fictícios marcados com "· demo". "Apagar dados de demonstração" remove tudo.
- **Ver como paciente:** na ficha de um paciente demo, abre o app como o paciente vê. A faixa no topo tem o botão para voltar ao terapeuta.

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

## Versões

A versão em uso aparece no rodapé de todas as telas. Ela é definida em `VERSAO`, no começo de `app.py`.

| Versão | O que trouxe |
|---|---|
| v1 | Primeira versão: terapeuta e paciente, agenda, prontuário, check-in diário, biblioteca, gravação com consentimento e transcrição com IA |
| v2 | Visual azul clarinho e branco, novo ícone |
| v3 | Dados de demonstração (carregar e apagar) |
| v4 | Modo avaliação: IA simulada, sem custo |
| v5 | Visual branco, testes Multi 1 a 12 com estoque por tipo, 10 indicadores, revisão da transcrição com prova da IA, check-in e check-out, relatório mensal, ver como paciente |
| v6 | Número da versão no rodapé do app |
| v7 | Versões de bibliotecas travadas e inicialização segura do servidor (corrige falha de build) |
| v8.2 | Todos os arquivos numa pasta só (o envio pelo GitHub não desmonta mais a estrutura) e aviso de arquivo faltando |
| v8 | Área financeira, evolução dos indicadores, relatório em PDF, sessões recorrentes, recibos, criptografia dos dados clínicos, verificação em duas etapas, recuperação de senha, registro de acessos, saída por inatividade, exportação e exclusão de dados (LGPD), termos e privacidade |

## Arquivos

Desde a v8.2, **todos os arquivos ficam numa pasta só, sem subpastas**. Para atualizar, selecione tudo (Ctrl + A) e arraste para a página inicial do repositório no GitHub. Se algum arquivo não chegar, o painel do terapeuta mostra um aviso com o nome dele.

- `app.py`: rotas, modelos e regras
- `financeiro.py`, `conta.py`, `relatorios.py`, `voz.py`, `cripto.py`, `demo.py`: módulos
- `t_*.html`: telas do terapeuta · `p_*.html`: telas do paciente · `c_*.html`: conta e LGPD · demais `.html`: telas comuns
- `style.css`, `sw.js`, `manifest.webmanifest`, `*.png`: visual, app instalável e ícones

As pastas antigas `templates` e `static` no GitHub não são mais usadas e podem ser apagadas.
