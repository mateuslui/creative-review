# Creative Review

Skill do Claude Code que lê anúncios em vídeo (copy + visual) e devolve a leitura completa pra modelar:
transcrição com timestamp, leitura cena a cena, leitura estratégica e o "como modelar".

## Instalação

1. Copie esta pasta para `~/.claude/skills/creative-review` (Mac/Linux) ou `%USERPROFILE%\.claude\skills\creative-review` (Windows).

2. Instale o ffmpeg:

```bash
brew install ffmpeg          # Mac
sudo apt install ffmpeg      # Linux
winget install ffmpeg        # Windows
```

3. Crie o ambiente Python da skill:

```bash
python3 -m venv ~/.claude/skills/creative-review/.venv
~/.claude/skills/creative-review/.venv/bin/pip install faster-whisper pillow
```

No Windows, troque `bin/pip` por `Scripts\pip`.

4. Teste:

```bash
~/.claude/skills/creative-review/.venv/bin/python ~/.claude/skills/creative-review/scripts/prepare.py <video.mp4> --out ~/Downloads/creative-review/teste
```

Na primeira execução o modelo de transcrição (`small`, cerca de 500MB) é baixado automaticamente.

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
