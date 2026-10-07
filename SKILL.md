---
name: creative-review
description: >
  Lê anúncios em vídeo (copy + visual) e devolve a leitura completa pra modelar: transcrição com timestamp,
  leitura cena a cena (o que aparece, texto na tela, fala, função), leitura estratégica (hook, ângulo, estrutura,
  consciência, mecanismo, prova, oferta/CTA) e o "como modelar" (esqueleto que fica × superfície que troca ×
  lista de produção). Em lote, fecha com uma síntese dos padrões que se repetem. Usa os frameworks do vault
  Obsidian "Agente de Ads" (7 camadas, hook = ângulo + benefício, big idea, marcadores avançados).
  Use quando o usuário mandar vídeos (arquivo, pasta ou link direto) e pedir pra ler, revisar, decupar,
  destrinchar, transcrever + analisar, ou "modelar" criativos. Triggers: "creative review", "lê esses vídeos",
  "decupa esse anúncio", "me traz a copy e o visual", "quero modelar esses criativos".
user-invokable: true
argument-hint: "<vídeo | pasta | url .mp4> [...] [contexto: nicho/produto pra modelar]"
---

# Creative Review

Objetivo: o usuário consegue **modelar** o anúncio só lendo o que você entregar — inclusive a parte visual,
que ele não vai conseguir deduzir só pela copy. Mercado principal: DTC / e-com nos EUA (funil típico:
ad → advertorial / quiz / PDP; às vezes VSL).

Você não assiste vídeo. Você lê: **transcrição local + quadros com timestamp**. O script prepara os dois.

## Passo 1 — Preparar

```bash
~/.claude/skills/creative-review/.venv/bin/python ~/.claude/skills/creative-review/scripts/prepare.py \
  <vídeos ou pasta> --out <pasta-de-saída>
```

- Python: usa o venv da própria skill (`~/.claude/skills/creative-review/.venv`), com faster-whisper + Pillow.
  Se não existir, siga o README: `python3 -m venv .venv && .venv/bin/pip install faster-whisper pillow`. Requer ffmpeg no PATH.
- Saída padrão: `~/Downloads/creative-review/<AAAA-MM-DD>-<nome-do-lote>/`, salvo se o usuário indicar outra.
- Links da Ad Library: baixe antes com a skill `fb-ad-library-spy` e passe a pasta baixada.
- Opções: `--lang en` (força idioma), `--interval 1.0` (mais quadros em vídeo de corte rápido), `--model medium`.
- Rode em background quando forem vários vídeos.

Por vídeo, o script gera `manifest.json` (duração, orientação, nº de cortes, plano médio), `transcript.md`,
`hook/` (0.0–3.0s a cada 0.5s) e `sheets/` (folhas 3x2 com timestamp, resto do vídeo + cada corte de cena).

## Passo 2 — Ler

Para cada vídeo, nesta ordem:
1. `manifest.json` → ficha técnica e ritmo (cortes, plano médio).
2. **Todos** os quadros de `hook/` → os 3 primeiros segundos são metade da análise.
3. `transcript.md` → a copy. Whisper erra nomes e números: corrija com a legenda queimada nos quadros
   e marque `[?]` o que não der pra confirmar.
4. **Todas** as folhas de `sheets/` → cenas, texto na tela, produto, b-roll, provas visuais, CTA.

Regras: nunca invente o que não está nem na fala nem nos quadros. Ritmo de corte e animação entre
quadros são estimativa — diga isso quando importar. Vídeo sem fala: a copy é o texto na tela.

## Passo 3 — Entregar (um `review.md` por vídeo, na pasta do vídeo)

Use o template em `references/template-review.md` e o checklist em `references/checklist-leitura.md`.
Seções: Ficha · Copy · Leitura cena a cena · Leitura estratégica · Como modelar.

Enxuto: sem ressalvas metodológicas no documento (essas vão no chat). Copy citada literal, no idioma original;
análise em pt-BR.

## Passo 4 — Lote (2+ vídeos)

Escreva `sintese.md` na raiz do lote: o que se repete (hook visual, estrutura de blocos, formato, prova,
ritmo, CTA), o que varia, e 3–5 "esqueletos" prontos pra modelar com qual vídeo é a referência de cada um.

## Passo 5 — Fechar no chat

Liste os arquivos (links), dê 3–5 linhas com o achado principal e pergunte pra qual nicho/produto/mecanismo
modelar. A escrita das copies novas é com `ads-builder` / `creative-pattern-analysis` / `hook-lab` — não aqui.
Se o usuário quiser guardar na biblioteca, copie o `review.md` pro Obsidian em `Agente de Ads/03-Exemplos-Ads/`.
