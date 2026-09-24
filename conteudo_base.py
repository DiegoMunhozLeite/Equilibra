"""Conteúdo educativo inicial. Informativo, sem orientação de dose.
Revise com sua equipe e adapte à sua abordagem antes de liberar aos pacientes."""

AVISO = ("\n## Importante\n"
         "Este texto é informativo e não substitui avaliação médica. "
         "Em emergência, ligue 192 (SAMU). Para apoio emocional, ligue 188 (CVV), 24 horas.")

ARTIGOS = [
    dict(categoria="substancia", titulo="Álcool",
         resumo="Efeitos, riscos e por que parar de beber de repente pode exigir acompanhamento médico.",
         corpo="""O álcool é um depressor do sistema nervoso central. No começo pode dar sensação de relaxamento e desinibição; com mais consumo, reduz coordenação, reflexos e julgamento.

## Riscos
- Acidentes, quedas e violência
- Doenças do fígado, pâncreas, coração e vários tipos de câncer
- Piora de ansiedade, depressão e insônia
- Risco muito maior quando misturado com calmantes (benzodiazepínicos) ou opioides

## Sinais de intoxicação grave
- Confusão, vômitos repetidos, respiração lenta ou irregular
- Pele fria ou azulada, dificuldade para acordar

Nesses casos, chame o 192, não deixe a pessoa sozinha e deite-a de lado.

## Abstinência
Quem bebe muito e todos os dias pode ter abstinência perigosa ao parar de uma vez: tremores, suor, agitação, alucinações e convulsões. Por isso a interrupção deve ser planejada com um médico.""" + AVISO),

    dict(categoria="substancia", titulo="Maconha (cannabis)",
         resumo="O que é, efeitos no corpo e na mente e sinais de uso problemático.",
         corpo="""A maconha age no sistema endocanabinoide e altera percepção, memória, atenção e apetite.

## Riscos
- Prejuízo de memória e concentração, especialmente em adolescentes
- Ansiedade, ataques de pânico e, em pessoas vulneráveis, sintomas psicóticos
- Dependência: uso diário, dificuldade de reduzir, uso para conseguir dormir ou se acalmar
- Dirigir sob efeito aumenta o risco de acidentes

## Ao reduzir ou parar
É comum ter irritabilidade, insônia, sonhos intensos, perda de apetite e inquietação por alguns dias a semanas. Rotina de sono, atividade física e práticas de respiração ajudam a atravessar essa fase.""" + AVISO),

    dict(categoria="substancia", titulo="Cocaína e crack",
         resumo="Estimulantes de efeito curto e intenso, com alto risco para coração e mente.",
         corpo="""Cocaína e crack são a mesma substância em formas diferentes. São estimulantes: aceleram coração, pensamento e energia por pouco tempo, seguido de queda de humor e forte vontade de usar de novo.

## Riscos
- Infarto, AVC, arritmias e convulsões, mesmo em pessoas jovens
- Paranoia, agitação e insônia
- Uso em sequência, perda de controle e prejuízo financeiro e familiar
- A mistura com álcool sobrecarrega ainda mais o coração

## Quando buscar ajuda imediata
- Dor no peito, falta de ar, desmaio ou convulsão
- Temperatura muito alta, confusão intensa ou agitação extrema

Ligue 192.

## Depois do uso
Cansaço, tristeza e fissura intensa são comuns nos dias seguintes. Não é fraqueza: é o efeito da substância no cérebro, e passa.""" + AVISO),

    dict(categoria="substancia", titulo="Benzodiazepínicos (calmantes)",
         resumo="Remédios para ansiedade e sono que podem causar dependência.",
         corpo="""Benzodiazepínicos são remédios usados para ansiedade, insônia e convulsões. Usados por muito tempo, o corpo se acostuma e pode surgir dependência.

## Riscos
- Sonolência, lentidão e prejuízo de memória
- Quedas, principalmente em pessoas idosas
- Risco alto de parada respiratória quando combinados com álcool ou opioides

## Nunca pare por conta própria
A retirada deve ser gradual e orientada pelo médico que prescreve. Parar de repente pode causar ansiedade intensa, insônia grave e até convulsões.""" + AVISO),

    dict(categoria="substancia", titulo="Opioides",
         resumo="Analgésicos fortes e outras substâncias com alto risco de overdose.",
         corpo="""Opioides aliviam dor e causam relaxamento, mas deprimem a respiração. Incluem remédios de uso médico e substâncias ilícitas.

## Sinais de overdose
- Pupilas muito pequenas
- Respiração muito lenta, ronco estranho ou parada respiratória
- Lábios e unhas azulados, não acorda com estímulo

Chame o 192 imediatamente e mantenha a pessoa de lado.

## Redução de riscos
- Nunca usar sozinho
- Não misturar com álcool ou calmantes
- A tolerância cai rápido após dias sem uso: voltar a usar é quando mais acontecem overdoses

Existem tratamentos médicos eficazes para dependência de opioides. Converse com um médico ou procure um CAPS AD.""" + AVISO),

    dict(categoria="substancia", titulo="Tabaco e nicotina",
         resumo="Cigarro, vape e narguilé: dependência e caminhos para parar.",
         corpo="""A nicotina é uma das substâncias que mais causam dependência. Está no cigarro, no cigarro eletrônico (vape), no narguilé e no fumo de rolo.

## Riscos
- Doenças do coração, pulmão e diversos tipos de câncer
- Vapes também causam dependência e irritação pulmonar

## Parar é possível
- A fissura dura poucos minutos: beber água, caminhar e respirar ajudam
- O SUS oferece tratamento gratuito para parar de fumar em unidades de saúde
- Muitas pessoas precisam de várias tentativas; cada tentativa conta""" + AVISO),

    dict(categoria="recuperacao", titulo="Lapso não é recaída",
         resumo="Como lidar com um deslize sem desistir do tratamento.",
         corpo="""Lapso é um uso pontual depois de um período sem usar. Recaída é a volta ao padrão antigo de uso. Um lapso não precisa virar recaída.

## Depois de um deslize
- Seja honesto com você e com seu terapeuta
- Troque a culpa por curiosidade: o que aconteceu antes? Onde, com quem, o que sentia?
- Retome a rotina de cuidado no mesmo dia
- Lembre que os dias sem uso que você viveu continuam sendo seus

## Atenção
Depois de um período sem uso, a tolerância diminui. Usar a mesma quantidade de antes aumenta o risco de intoxicação grave.""" + AVISO),

    dict(categoria="recuperacao", titulo="HALT: fome, raiva, solidão e cansaço",
         resumo="Quatro estados que aumentam a vontade de usar e como cuidar de cada um.",
         corpo="""HALT vem do inglês: Hungry, Angry, Lonely, Tired. Quando você sente fissura, vale checar esses quatro estados.

- Fome: coma algo e beba água
- Raiva: nomeie o que sente, caminhe, escreva, espere antes de responder
- Solidão: ligue para alguém da sua rede de apoio ou vá a um grupo
- Cansaço: descanse; decisões difíceis ficam para depois

Muitas vezes, cuidar do corpo já diminui a intensidade da fissura."""),

    dict(categoria="recuperacao", titulo="Onde encontrar apoio",
         resumo="Serviços públicos e grupos de ajuda mútua gratuitos.",
         corpo="""## CAPS AD
Os Centros de Atenção Psicossocial Álcool e Drogas atendem pelo SUS, sem necessidade de encaminhamento. Procure o da sua cidade na secretaria de saúde ou na unidade básica.

## Grupos de ajuda mútua
- Narcóticos Anônimos (NA)
- Alcoólicos Anônimos (AA)
- Grupos para familiares, como Nar-Anon e Al-Anon

## Emergência e apoio emocional
- 192 SAMU, emergência médica
- 188 CVV, apoio emocional 24 horas, gratuito"""),

    dict(categoria="pratica", titulo="Surfar a fissura",
         resumo="Observar a vontade de usar como uma onda que sobe, chega ao pico e desce.",
         corpo="""A fissura costuma crescer, atingir um pico e diminuir em cerca de 20 a 30 minutos. Em vez de lutar contra ela, você pode observá-la.

## Passo a passo
- Sente-se confortável e perceba onde a vontade aparece no corpo: peito, estômago, boca, mãos
- Descreva a sensação sem julgar: quente, apertada, pulsante
- Respire devagar e acompanhe a sensação mudando de intensidade
- Imagine que você está sobre uma prancha, subindo e descendo a onda
- Quando a onda baixar, note que você atravessou sem usar

Cada vez que você surfa uma fissura, fica mais fácil da próxima vez."""),

    dict(categoria="pratica", titulo="Aterramento 5-4-3-2-1",
         resumo="Uma forma rápida de sair da ansiedade e voltar ao presente usando os sentidos.",
         corpo="""Use quando a mente acelerar ou a ansiedade subir.

- 5 coisas que você vê
- 4 coisas que você pode tocar
- 3 sons que você ouve
- 2 cheiros que percebe
- 1 sabor na boca

Faça devagar, falando em voz baixa se ajudar. Termine com três respirações longas."""),

    dict(categoria="pratica", titulo="Respiração para momentos de fissura",
         resumo="Uma respiração lenta e ritmada que acalma o corpo em poucos minutos.",
         corpo="""Respirar devagar, com a expiração mais longa que a inspiração, ativa o sistema de descanso do corpo.

## Como fazer
- Inspire pelo nariz contando 4
- Segure contando 4
- Solte pela boca contando 6
- Repita por 3 a 5 minutos

Se ficar tonto, volte a respirar normalmente. Você pode usar a respiração guiada do app no botão Respirar."""),

    dict(categoria="pratica", titulo="Escaneamento corporal",
         resumo="Relaxamento guiado da cabeça aos pés, bom para antes de dormir.",
         corpo="""Deite-se ou sente-se confortável e feche os olhos se quiser.

- Leve a atenção ao topo da cabeça e perceba qualquer tensão
- Desça devagar: rosto, mandíbula, pescoço e ombros
- Braços, mãos, peito e barriga, acompanhando a respiração
- Quadril, pernas e pés
- A cada região, solte um pouco a tensão ao expirar

Dez minutos por dia já ajudam a dormir melhor e a perceber o corpo antes que a fissura cresça."""),
]
