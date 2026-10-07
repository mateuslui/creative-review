# Creative Review

Skill do Claude Code que lê anúncios em vídeo (copy + visual) e devolve a leitura completa pra modelar:
transcrição com timestamp, leitura cena a cena, leitura estratégica e o "como modelar".

## Instalação

Precisa do **Claude Code** instalado no computador. A skill roda comando local (ffmpeg, Whisper) e lê arquivo
no disco, então não funciona no Claude do navegador nem no app de celular.

### Mac

```bash
git clone https://github.com/mateuslui/creative-review.git ~/.claude/skills/creative-review
```

```bash
brew install ffmpeg
```

```bash
cd ~/.claude/skills/creative-review && python3 -m venv .venv && .venv/bin/pip install faster-whisper pillow
```

Se o `brew` não existir, instale o Homebrew primeiro em https://brew.sh.

### Windows (PowerShell)

```powershell
winget install Git.Git ; winget install Python.Python.3.12 ; winget install Gyan.FFmpeg
```

Feche e abra o PowerShell depois dessa linha, para o PATH atualizar.

```powershell
git clone https://github.com/mateuslui/creative-review.git "$env:USERPROFILE\.claude\skills\creative-review"
```

```powershell
cd "$env:USERPROFILE\.claude\skills\creative-review" ; python -m venv .venv ; .venv\Scripts\pip install faster-whisper pillow
```

### Linux

```bash
git clone https://github.com/mateuslui/creative-review.git ~/.claude/skills/creative-review
sudo apt install ffmpeg
cd ~/.claude/skills/creative-review && python3 -m venv .venv && .venv/bin/pip install faster-whisper pillow
```

### Depois de instalar

Reinicie o Claude Code. A skill aparece como `/creative-review`.

Na primeira execução o modelo de transcrição (`small`, cerca de 500MB) é baixado automaticamente.

## Atualizar

```bash
cd ~/.claude/skills/creative-review && git pull
```

No Windows:

```powershell
cd "$env:USERPROFILE\.claude\skills\creative-review" ; git pull
```

## Uso

No Claude Code, dentro da pasta onde estão os vídeos:

```
/creative-review <arquivo ou pasta de vídeos>
```

Ou simplesmente mande os vídeos e peça para ler, decupar ou modelar.

## Saída

Para cada vídeo, uma pasta com:

- `manifest.json` — duração, orientação, número de cortes, plano médio
- `transcript.md` — transcrição com timestamp
- `hook/` — quadros de 0 a 3s, a cada 0,5s
- `sheets/` — folhas de contato 3x2 com timestamp, uma por trecho e por corte de cena
- `review.md` — a leitura final (escrita pelo Claude)

Em lote, um `sintese.md` na raiz com os padrões que se repetem.

## Opções do prepare.py

- `--lang en` força o idioma da transcrição
- `--interval 1.0` mais quadros, para vídeo de corte rápido
- `--model medium` transcrição mais precisa e mais lenta
- `--out <pasta>` define a pasta de saída
