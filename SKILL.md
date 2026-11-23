---
name: creative-review
description: >
  Lê anúncios em vídeo (copy + visual) e devolve a leitura completa pra modelar: transcrição com timestamp,
  leitura cena a cena (o que aparece, texto na tela, fala, função), leitura estratégica (hook, ângulo, estrutura,
  consciência, mecanismo, prova, oferta/CTA) e o "como modelar" (esqueleto que fica × superfície que troca ×
  lista de produção). Também revisa a EDIÇÃO com foco em retenção: trechos sem fala, buracos de áudio, imagem
  parada, fala repetida e quebras de nexo/fluidez, e devolve a lista de cortes com timestamp e a duração
  enxuta. Em lote, fecha com uma síntese dos padrões que se repetem. Usa os frameworks do vault
  Obsidian "Agente de Ads" (7 camadas, hook = ângulo + benefício, big idea, marcadores avançados).
  Use quando o usuário mandar vídeos (arquivo, pasta ou link direto) e pedir pra ler, revisar, decupar,
  destrinchar, transcrever + analisar, ou "modelar" criativos. Triggers: "creative review", "lê esses vídeos",
  "decupa esse anúncio", "me traz a copy e o visual", "quero modelar esses criativos", "revisa a edição",
  "onde esse vídeo perde retenção", "o que cortar nesse ad", "revisa esse AI Drama".
user-invokable: true
argument-hint: "<vídeo | pasta | url .mp4> [...] [contexto: nicho/produto pra modelar]"
---

# Creative Review

Objetivo: o usuário consegue **modelar** o anúncio só lendo o que você entregar — inclusive a parte visual,
que ele não vai conseguir deduzir só pela copy. Mercado principal: DTC / e-com nos EUA (funil típico:
ad → advertorial / quiz / PDP; às vezes VSL).

Você não assiste vídeo. Você lê: **transcrição local + quadros com timestamp + medição de edição**
(onde não tem fala, onde o áudio cai, onde a imagem para). O script prepara os três.

Dois usos, mesma preparação:
- **Modelar** (ad de concorrente): entrega completa, seções 1 a 5 do template.
- **Revisar a edição** (ad nosso, antes de subir): a seção 5 vem primeiro e é o que importa; as outras
  entram só se o usuário pedir.

Em **AI Drama** e em qualquer ad unaware de topo o objetivo do vídeo é retenção. Ali a leitura de edição
é obrigatória e mais dura: rode com `--gap 1.0` e trate todo trecho sem fala como corte, salvo se a imagem
daquele trecho fizer a história andar sozinha.

## Passo 1 — Preparar

```bash
~/.claude/skills/creative-review/.venv/bin/python ~/.claude/skills/creative-review/scripts/prepare.py \
  <vídeos ou pasta> --out <pasta-de-saída>
```

- Python: usa o venv da própria skill (`~/.claude/skills/creative-review/.venv`), com faster-whisper + Pillow.
  Se não existir, siga o README: `python3 -m venv .venv && .venv/bin/pip install faster-whisper pillow`. Requer ffmpeg no PATH.
- Windows: o caminho é `%USERPROFILE%\.claude\skills\creative-review\.venv\Scripts\python.exe` e o script é
  `...\scripts\prepare.py`. Mesmos argumentos.
- Saída padrão: `~/Downloads/creative-review/<AAAA-MM-DD>-<nome-do-lote>/`, salvo se o usuário indicar outra.
- Links da Ad Library: baixe antes com a skill `fb-ad-library-spy` e passe a pasta baixada.
- Opções: `--lang en` (força idioma), `--interval 1.0` (mais quadros em vídeo de corte rápido), `--model medium`,
  `--gap 1.5` (segundos sem fala para o trecho entrar na lista de corte; AI Drama e unaware: `--gap 1.0`).
- Rode em background quando forem vários vídeos.

Por vídeo, o script gera `manifest.json` (duração, orientação, nº de cortes, plano médio), `transcript.md`
(com cada trecho sem fala marcado com ⏸ no lugar onde acontece), `hook/` (0.0–3.0s a cada 0.5s), `sheets/`
(folhas 3x2 com timestamp, resto do vídeo + cada corte de cena), `edicao.md` (trechos sem fala, buracos de
áudio, fala repetida, salto de volume, ritmo por janela, duração enxuta) e `gaps/` (quadros de dentro de
cada trecho sem fala).

## Passo 2 — Ler

Para cada vídeo, nesta ordem:
1. `manifest.json` → ficha técnica e ritmo (cortes, plano médio).
2. **Todos** os quadros de `hook/` → os 3 primeiros segundos são metade da análise.
3. `transcript.md` → a copy. Whisper erra nomes e números: corrija com a legenda queimada nos quadros
   e marque `[?]` o que não der pra confirmar.
4. **Todas** as folhas de `sheets/` → cenas, texto na tela, produto, b-roll, provas visuais, CTA.
5. `edicao.md` + **todas** as folhas de `gaps/` → a leitura de edição (Passo 2B).

Regras: nunca invente o que não está nem na fala nem nos quadros. Ritmo de corte e animação entre
quadros são estimativa — diga isso quando importar. Vídeo sem fala: a copy é o texto na tela.

## Passo 2B — Ler a edição (retenção)

A medição acha onde não tem fala. Quem decide se aquilo é erro é você, olhando os quadros. Duas passadas:

**1. Trechos sem fala.** Para cada linha de `edicao.md`, abra os quadros daquele trecho em `gaps/` e responda:
a imagem faz a história andar sem a fala (texto novo na tela, revelação, reação que muda a cena, produto
entrando)? Se sim, **fica** e você diz por quê. Se é cinematografia de enfeite, plano que sobrou depois da
fala acabar, imagem parada ou trilha tocando sozinha, **corta**, com o timestamp exato de entrada e saída.
Abertura sem fala no primeiro segundo e trecho "grave" (4s ou mais) nunca passam sem veredito.

**2. Nexo, frase por frase.** Leia a transcrição inteira em ordem, uma frase de cada vez, e para cada uma
pergunte: ela nasce da anterior? Marque toda quebra, com timestamp e a fala literal:
- salto de assunto sem ponte; frase que responde uma pergunta que ninguém fez
- "ele", "isso", "aquilo" apontando pra algo que nunca foi apresentado (o setup foi cortado ou nunca existiu)
- loop aberto que não fecha, ou que fecha antes de ter rendido
- a mesma informação dita duas vezes; recomeço de frase; frase cortada no meio
- fala e imagem contando coisas diferentes; legenda queimada diferente da fala
- personagem, voz, roupa ou cenário que muda de um plano pro outro sem a história pedir
- queda de energia: bloco lento (veja "Ritmo por janela") logo depois de um bloco rápido

Não confie na leitura por bloco: quebra de fluidez só aparece lendo linha a linha, e é exatamente o que
uma revisão apressada deixa passar. Cada achado sai com **onde, o que está lá, por que quebra, o que
fazer** (cortar de X a Y, encurtar, reordenar, escrever uma ponte). Feche com a duração atual, a duração
depois dos cortes e os 3 cortes que mais devolvem retenção.

Limite a dizer no chat, não no documento: sincronia labial e qualidade de voz não dá pra julgar por quadro
e transcrição; a detecção de fala pode confundir música cantada com fala.

## Passo 3 — Entregar (um `review.md` por vídeo, na pasta do vídeo)

Use o template em `references/template-review.md` e o checklist em `references/checklist-leitura.md`.
Seções: Ficha · Copy · Leitura cena a cena · Leitura estratégica · Como modelar · Edição e retenção.
Em revisão de edição, "Edição e retenção" sobe pro topo, logo depois da Ficha.

Enxuto: sem ressalvas metodológicas no documento (essas vão no chat). Copy citada literal, no idioma original;
análise em pt-BR.

## Passo 4 — Lote (2+ vídeos)

Escreva `sintese.md` na raiz do lote: o que se repete (hook visual, estrutura de blocos, formato, prova,
ritmo, CTA), o que varia, e 3–5 "esqueletos" prontos pra modelar com qual vídeo é a referência de cada um.
Em revisão de edição, a síntese é o erro que se repete entre os vídeos (vira orientação pro editor) e uma
tabela com duração atual × duração enxuta de cada um.

## Passo 5 — Fechar no chat

Liste os arquivos (links), dê 3–5 linhas com o achado principal e pergunte pra qual nicho/produto/mecanismo
modelar. A escrita das copies novas é com `ads-builder` / `creative-pattern-analysis` / `hook-lab` — não aqui.
Se o usuário quiser guardar na biblioteca, copie o `review.md` pro Obsidian em `Agente de Ads/03-Exemplos-Ads/`.
