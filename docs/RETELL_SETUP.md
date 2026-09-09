# Configure the Retell voice agent

This app does two jobs:

1. The browser UI talks to your Retell agent with the official Web SDK
   (microphone + speakers).
2. The local Python director owns the script cursor and Q&A. Retell calls its
   public webhooks; this PC drives PowerPoint.

Retell’s cloud **cannot call localhost**. The director therefore needs a public
HTTPS tunnel, while the PowerPoint bridge and UI stay local.

## 1. Keys

1. Open [Retell](https://beta.retellai.com) → **API Keys** and copy a secret key.
2. Open your agent and copy its **Agent ID** (looks like `agent_...`).
3. Copy `.env.example` to `.env` in this project folder and fill:

```
RETELL_API_KEY=key_...
RETELL_AGENT_ID=agent_...
```

## 2. Public URL for tools

With `AUTO_TUNNEL=true`, `voice-app.cmd` starts a Cloudflare quick tunnel and
synchronizes `deliver_next` and `handle_audience_question` on the agent.

Leave `PUBLIC_BASE_URL` and `DIRECTOR_PUBLIC_URL` **empty** unless you have a
stable custom domain. Quick tunnels (`*.trycloudflare.com`) get a **new
hostname every start** and die when the app stops. Saving one in `.env` makes
Retell call a dead URL.

If no tunnel URL appears:

```powershell
winget install Cloudflare.cloudflared
```

Do **not** browse the tunnel URL. Use `http://127.0.0.1:8787` only.

## 3. Agent settings on retellai.com

Use a **single-prompt** or **multi-prompt** agent. Web calls must be enabled.

Startup syncs the canonical prompt from `voice_app/presenter_prompt.py`. If you
need to paste it by hand, copy that file.

Begin message: `各位早晨，而家開始今次簡報。`

Keep **only** these two custom functions. Turn off MCP slide tools and
`end_call`. **Talk After Action Completed** on, **Talk While Waiting** off.
Set each function **timeout to 20000 ms** (or more). Confirm **Backchannel**
off.

### deliver_next

URL: `…/webhook/presenter/deliver-next` (shown in the local console).

Parameters: `{ "type": "object", "properties": {} }`

### handle_audience_question

URL: `…/webhook/presenter/handle-question` (shown in the local console).

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

Silence between slides is `SLIDE_PAUSE_MS` in `.env` (default 800). The Retell
reminder uses the same time unless `RETELL_REMINDER_TRIGGER_MS` is set.

If later slides **flip in a burst** while the voice is still on an earlier
line, restart the local app. PowerPoint flips are queued until
`agent_stop_talking` for the previous line.

### MCP (legacy copilot only)

Do **not** enable MCP slide tools on the scripted presenter agent. They let the
model skip the script.

### Prebuilt

Do **not** add Retell’s built-in **end_call**. The UI **Stop** button always
ends the web call from this computer.

## 4. Run a session

1. Start Qdrant with `qdrant-local.cmd` if you need grounded Q&A.
2. Start the local app and open `http://127.0.0.1:8787`.
3. Paste the `.pptx` path → **Load deck**.
4. Check **Also start Retell voice** → **Start** (allow microphone).
5. **Stop** ends only the voice call. **End slideshow** closes the PowerPoint
   show.

Create-web-call tokens last 30 seconds, so the app creates the call only when
you press Start.

## Troubleshooting

**Start fails: agent … not found**

The Agent ID and API key must belong to the **same** Retell account. This app
prefers `.env` over a `RETELL_API_KEY` already set in Windows. Restart
`voice-app.cmd` after changing `.env`. Copy **Agent ID** from the agent — not
an LLM ID (`llm_…`) and not an agent from another login.

**Agent talks but slides do not move / hangs up after one reply**

1. After the call, this UI prints `Ended: … · tools: …`. `agent_hangup` with
   only `end_call` means the model hung up instead of calling `deliver_next`.
2. In Retell → the agent → **Functions / prebuilt**, **delete `end_call`**.
3. Confirm the console shows a live public director URL and that Retell
   function sync succeeded.

**Add Tools spinner never shows a list**

- Restart `voice-app.cmd` and wait for the new tunnel URL.
- Do not put a `*.trycloudflare.com` URL in `.env` as `PUBLIC_BASE_URL`.
