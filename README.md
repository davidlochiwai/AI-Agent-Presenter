# AI Agent Presenter — PowerPoint action tester

Windows-only harness that drives **Microsoft PowerPoint** over COM and checks the presenter actions an AI agent will later take over.

The same `PresenterController` API is what the agent should call. This package only tests those actions; it does not generate speech or decide what to say.

## Voice agent (browser + Retell)

Local web console: load a `.pptx`, press **Start** / **Stop**. n8n directs the talk; this PC drives PowerPoint. The sample pack is a 12-slide Harbour AI Q2 review plus matching `data/script.xlsx` and knowledge files in `data/knowledge_sources`.

```powershell
copy .env.example .env
notepad .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m voice_app.sample_pack
voice-app.cmd
```

`voice-app.cmd` opens a dedicated AIRA window in Microsoft Edge. The default
layout uses the primary monitor with PowerPoint on the left 67% and AIRA on
the right 33%, while keeping the Windows taskbar visible.

The AIRA window normally shows only the large animated presenter and the
latest agent/user dialogue. Use the small gear button or press
`Ctrl+Shift+M` to open the maintenance console without interrupting the
Retell call. You can also open maintenance directly at
`http://127.0.0.1:8787/?view=maintenance`.

If either window is moved, choose **Arrange windows** in maintenance mode.
Set `PRESENTER_SPLIT_LAYOUT=false` to disable automatic placement, or adjust
`PRESENTER_SLIDE_RATIO` in `.env` (accepted range: `0.50`–`0.80`).

- Local n8n Docker setup and upgrade: [docs/LOCAL_N8N.md](docs/LOCAL_N8N.md)
- Grounded Azure OpenAI Q&A: [docs/QA_RAG.md](docs/QA_RAG.md)
- Q&A evaluation corpus and tests: [docs/QA_EVALUATION.md](docs/QA_EVALUATION.md)
- Existing n8n Cloud setup: [docs/N8N_DIRECTOR.md](docs/N8N_DIRECTOR.md)
- Retell voice: [docs/RETELL_SETUP.md](docs/RETELL_SETUP.md)

For the local director:

```powershell
.\n8n-local.cmd
.\voice-app.cmd
```

With `N8N_AUTO_TUNNEL=true` (set by `configure-local-n8n.ps1`), each `voice-app.cmd` start opens a fresh Cloudflare quick tunnel to n8n and patches Retell. Do not also run `n8n-quick-tunnel.cmd`.

## Requirements

- Windows with a desktop session (not a headless service)
- Microsoft PowerPoint (Office 2016 / Microsoft 365)
- Python 3.11+

## Setup

```powershell
cd "C:\Users\User\Documents\Data_Science\_TRIAL\AI Agent Presenter"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Commands

```powershell
python -m ppt_presenter probe          # can Python talk to PowerPoint?
python -m ppt_presenter list           # action catalog + live tests
python -m ppt_presenter test --smoke   # short run (windowed show)
python -m ppt_presenter test           # full COM action suite
python -m ppt_presenter test --presenter-view   # also starts real Presenter View (fullscreen)
python -m ppt_presenter status         # snapshot of an already-running show
```

Useful flags for `test`:

| Flag | Meaning |
| --- | --- |
| `--only next,goto,black` | Run named tests only |
| `--skip laser,pause` | Skip named tests |
| `--step` | Pause after each action so you can watch the slide |
| `--delay 0.5` | Extra settle time after each COM call |
| `--save-fixture fixtures\tester.pptx` | Keep the generated deck |
| `--json reports\last.json` | Machine-readable results |
| `--keep-open` | Leave PowerPoint open when the run finishes |

A live test **will open PowerPoint** and start a slide show. Default mode is a **windowed** show so it does not take over the whole screen. `--presenter-view` uses speaker mode and can go fullscreen.

## What is actually testable

COM can start/stop the show, move by animation or slide, blank to black/white, change pointer/pen/laser, ink a line, read speaker notes, and reset the slide timer.

Presenter View chrome — next-slide thumbnail, on-screen timer gadgets, “see all slides”, zoom — has **no COM write API**. Those stay listed in `ppt_presenter/catalog.py` so the agent does not pretend they are scriptable.

## Controller the agent will reuse

```python
from ppt_presenter import PresenterController

with PresenterController() as show:
    show.connect()
    show.open(r"C:\decks\talk.pptx")
    show.start(presenter_view=True, windowed=False)
    print(show.status().notes)
    show.next()
    show.black()
    show.resume()
    show.end()
```
