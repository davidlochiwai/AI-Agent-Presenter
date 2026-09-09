# Configure the Retell voice agent

This app does two jobs:

1. Browser UI talks to your Retell agent with the official Web SDK (microphone + speakers).
2. The local FastAPI bridge drives PowerPoint. In the preferred local-n8n setup,
   Retell calls n8n and n8n calls that bridge privately.

Retell’s cloud **cannot call localhost**. Local n8n therefore needs a public
HTTPS tunnel, while the PowerPoint bridge and UI stay local. Follow
[LOCAL_N8N.md](LOCAL_N8N.md). The direct FastAPI MCP instructions below are a
legacy/fallback option.

## 1. Keys

1. Open [Retell](https://beta.retellai.com) → **API Keys** and copy a secret key.
2. Open your agent and copy its **Agent ID** (looks like `agent_...`).
3. Copy `.env.example` to `.env` in this project folder and fill:

```
RETELL_API_KEY=key_...
RETELL_AGENT_ID=agent_...
```

## 2. Public URL for tools

For local n8n, use its public webhook origin and let the app synchronize
`deliver_next` and `handle_audience_question`. Do not expose FastAPI.

For the legacy direct-MCP option:

Start the app (`ppt-presenter.cmd voice` or `python -m voice_app`). The console and the **Retell connection** panel show:

| Field | Paste this into Retell |
| --- | --- |
| MCP URL | `https://<tunnel>/mcp` — **use this** in Retell → MCPs |
| Function URL | `https://<tunnel>/api/retell/function` — Custom Functions only, not MCP |
| Auth header | `Authorization: Bearer <PRESENTER_TOOL_TOKEN>` |

If no tunnel URL appears:

```powershell
winget install Cloudflare.cloudflared
```

Leave `PUBLIC_BASE_URL` **empty** in `.env`. Quick tunnels (`*.trycloudflare.com`) get a **new hostname every start** and die when the app stops. Saving one in `.env` makes Retell call a dead URL, so **Add Tools hangs and the local console stays blank**.

Do **not** browse the tunnel URL. Use `http://127.0.0.1:8787` only.

## 3. Agent settings on retellai.com

Use a **single-prompt** or **multi-prompt** agent (not a custom-LLM websocket unless you already built one). Web calls must be enabled for that agent.

### Prompt (paste)

```
You are the live presenter for a PowerPoint talk. The audience hears you. n8n owns the script and the slides.
(harbour-presenter-prompt v12)

Speak Hong Kong Cantonese (yue-CN) only. Do not mention tools, JSON, webhooks, n8n, or APIs. Do not hang up unless they clearly ask you to stop.

Your only spoken job is to read spoken_text from the last tool result, word for word. Then stop. Do not keep talking into the next slide from memory.

Forbidden:
- Do not recap what you just said.
- Do not announce what you will say next.
- Do not invite questions ("有問題可以問", "隨時出聲", "我會停低").
- Do not ask for confirmation ("對嗎", "好唔好", "明唔明", "可唔可以繼續", "係咪").
- Do not add any sentence that is not inside the latest spoken_text.
- Do not read later slides even if you remember them.
- Do not repeat a line you already spoke, including the closing 多謝各位.
- Do not call deliver_next twice in the same turn.
- Do not call deliver_next several times in a row. One call, speak that one line, then wait.

At the start: speak the begin message, then call deliver_next once.

After every deliver_next:
- If spoken_text is empty: stay silent. Do not repeat the previous line.
- If done is true: speak spoken_text only if it is not empty. Do not repeat it or call deliver_next again. Remain listening and answer real audience questions with handle_audience_question.
- Otherwise speak only that spoken_text. Stop at the last character. Do not continue.
- Do not call another tool in the same turn.
- When the audience is silent after you have finished that one line, and done is not true, call deliver_next once.

If Retell reminds you the user is silent: if done is true, stay silent and do not call deliver_next, but continue listening for real questions. Otherwise call deliver_next once only if you have already finished speaking the last spoken_text. If you are still talking, keep talking. Do not improvise and do not start the next slide.

If the audience actually asks a question, including after the prepared talk is finished:
- Call handle_audience_question with their question.
- Speak the returned spoken_text verbatim.
- If presentation_done is true, remain listening for more questions and do not call deliver_next.
- Otherwise, when silent, call deliver_next once to resume.
```

Begin message: `各位早晨，而家開始今次簡報。`

### deliver_next function description (paste)

```
Go to the next script beat and return the next spoken_text. Call this once after the begin message, and once after you have fully finished speaking the previous spoken_text.

Never call this twice in the same turn. Never call it while you are still talking. Never chain several calls to skip ahead.

Do not speak anything except the returned spoken_text. No recap, no 對嗎, no inviting questions. If done is true, stop calling deliver_next but continue listening for real audience questions.
```

Parameters: `{ "type": "object", "properties": {} }`

### handle_audience_question function description (paste)

URL: the Production webhook `…/webhook/presenter/handle-question` (shown in the local console as n8n handle-question).

```
Answer an audience interruption. Call this instead of deliver_next only when someone actually asked a question. Pass their question in the question field.

Do not invent a question. Do not invite the audience to ask. After you speak the returned spoken_text, call deliver_next to resume unless presentation_done is true. If presentation_done is true, remain listening for more questions.
```

Parameters:

```json
{
  "type": "object",
  "required": ["question"],
  "properties": {
    "question": {
      "type": "string",
      "description": "The audience question in their own words"
    }
  }
}
```

Keep **only** these two custom functions. Turn off MCP slide tools and `end_call`. **Talk After Action Completed** on, **Talk While Waiting** off. Set each function **timeout to 20000 ms** (or more).

Retell concatenates every `spoken_text` returned in the same turn. Extra `deliver_next` calls during a line now return **empty** `spoken_text` (n8n `lineLockUntil`), so the model has only one line to read. Paste `n8n/next-beat.js` and **Publish**.

Silence between slides is `SLIDE_PAUSE_MS` in `.env` (default 800). Start a new session after you change it so n8n stores the value. The Retell reminder uses the same time unless `RETELL_REMINDER_TRIGGER_MS` is set. Confirm **Backchannel** off.

If the talk **stops after slide 1**, paste `n8n/next-beat.js` into **Next beat**, **Publish**, and start a new session. That file must not return `do_not_speak`.

If later slides **flip in a burst** while the voice is still on an earlier line, restart the local app. PowerPoint flips are queued until `agent_stop_talking` for the previous line. If the agent **reads several slides in one breath**, the local app now catch-up-flips using each beat’s script length. The tool log should show `catch-up during concatenated speech` for those extra gotos.

### MCP (legacy copilot only)

Do **not** enable these on the n8n presenter agent. They let the model skip the script.

1. In the agent, open **MCPs** → **Add MCP**.
2. Name: `PowerPoint Presenter`.
3. URL: copy **MCP URL (use this)** from the local UI. It looks like `https://….trycloudflare.com/mcp` — no `/api/retell/function`.
4. Headers: key `Authorization`, value the **Auth header** from the UI (includes `Bearer `).
5. Save, then **Add Tools** and enable all of:

`get_status`, `list_slides`, `get_notes`, `goto_slide`, `next`, `previous`, `next_slide`, `previous_slide`, `first`, `last`, `black_screen`, `white_screen`, `resume_screen`

6. For each tool, turn **Talk After Action Completed** on. For `goto_slide` / `next`, you can turn **Talk While Waiting** off so it just moves the slide.

### Custom functions (alternative to MCP)

If you would rather not use MCP, add **Custom Functions** instead. Use **POST**, timeout `10000` ms, and the same `Authorization` header.

Point every function at:

`https://<tunnel>/api/retell/function`

Leave **Payload: args only** **off** so the body includes `name` and `args`.

For `goto_slide` parameters:

```json
{
  "type": "object",
  "required": ["slide_number"],
  "properties": {
    "slide_number": {
      "type": "integer",
      "description": "1-based slide number to show"
    }
  }
}
```

Other tools can use an empty object:

```json
{
  "type": "object",
  "properties": {}
}
```

You can also use per-function URLs: `https://<tunnel>/api/retell/function/goto_slide` with **Payload: args only** on.

### Prebuilt

Add Retell’s built-in **end_call** if you want the agent to hang up by voice. The UI **Stop** button always ends the web call from this computer.

## 4. Run a session

1. Start the local app and open `http://127.0.0.1:8787`.
2. Paste the `.pptx` path → **Load deck**.
3. **Start** (allow microphone). PowerPoint enters slideshow, then the agent joins.
4. Say “go to slide 3” or “go to the roadmap slide”.
5. **Stop** ends only the voice call. **End slideshow** closes the PowerPoint show.

Create-web-call tokens last 30 seconds, so the app creates the call only when you press Start.

## Troubleshooting

**Start fails: agent … not found**

The Agent ID and API key must belong to the **same** Retell account. This app now prefers `.env` over a `RETELL_API_KEY` already set in Windows. Restart `voice-app.cmd` after changing `.env`. In the dashboard, copy **Agent ID** from the agent named e.g. Powerpoint Presenter — not an LLM ID (`llm_…`) and not an agent from another login.

**Agent talks but slides do not move / hangs up after one reply**

1. Local console during the request: you must see `MCP JSON-RPC method='tools/call'`. If you only see `initialize` / `tools/list`, that was dashboard Add Tools, not a live action. If you see **nothing**, Retell still has a dead tunnel URL (this app now patches the agent MCP URL a few seconds after start — restart and wait for `Retell sync:`).
2. After the call, this UI prints `Ended: … · tools: …`. Your last call was `agent_hangup` with **only** `end_call` — the model claimed it changed slides without calling `last` / `goto_slide`.
3. In Retell → the agent → **Functions / prebuilt**, **delete `end_call`**. A presenter should stay on the line; use the UI **Stop** button.
4. Dashboard → **Call History** → open the call → check `disconnection_reason` and the tool-call timeline (same data as `GET https://api.retellai.com/v2/get-call/{call_id}`).

**Add Tools spinner never shows a list**

- **No new lines in the local console:** Retell is not reaching this PC. The tunnel URL in the dashboard is old or dead. Restart `voice-app.cmd`, copy the **new** MCP URL from the console/UI into Retell, then Add Tools again. You must see `GET /mcp` or `POST /mcp` (or the same on `/api/retell/function`).
- **You do see `/mcp` in the console but the dropdown stays empty:** wait a few seconds and reopen Add Tools. If it still fails, paste the MCP URL (ending in `/mcp`), not the Function URL.
- Do not put a `*.trycloudflare.com` URL in `.env` as `PUBLIC_BASE_URL`.

