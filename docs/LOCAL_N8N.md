# Local n8n setup and upgrade

This guide moves the presenter director from n8n Cloud to a locally hosted n8n
container while keeping Retell in the cloud:

```text
Retell Cloud -> stable HTTPS -> local n8n -> private FastAPI bridge -> PowerPoint COM
```

The FastAPI bridge is no longer exposed publicly. Retell calls n8n, and n8n
calls the Windows host through Docker Desktop's `host.docker.internal`.

## What was detected on this PC

- Global npm n8n: `1.97.1`
- Node.js: `20.18.1`
- Current stable n8n: `2.36.8`
- Docker Desktop: installed (`27.4.0`, Compose `2.31.0`)
- No `database.sqlite` was found in the default `C:\Users\User\.n8n` folder

n8n's current npm package requires Node 24, and npm installations are officially
deprecated from n8n 3.0 (scheduled for October 2026). For that reason, this
project now runs the latest stable Docker image instead of upgrading the global
npm package in place.

The old npm package remains installed until the Docker setup passes the smoke
test. That gives you a simple rollback.

## Step 1 — Check for old local workflows

The default local folder currently has no workflow database. If you remember
creating important workflows in the old local n8n:

1. Stop here.
2. Check whether you previously set `N8N_USER_FOLDER` or used PostgreSQL.
3. Start n8n `1.97.1`.
4. Open **Settings → Migration Report** and resolve reported n8n 2.0 issues.
5. Export the workflows and encrypted credentials before continuing.

This project's active workflow has been in n8n Cloud, so normally there is
nothing to migrate from the old local npm installation.

## Step 2 — Start current stable n8n in Docker

Start Docker Desktop. Then run:

```powershell
cd "C:\Users\User\Documents\Data_Science\_TRIAL\AI Agent Presenter"
.\n8n-local.cmd
```

The script runs `compose.n8n.yml`, creates a persistent Docker volume named
`ai-agent-presenter_n8n_data`, starts the persistent Qdrant knowledge index,
and opens:

```text
http://127.0.0.1:5678
```

Qdrant listens only on `http://127.0.0.1:6333`. It is used by the grounded Q&A
path and is not exposed through the Cloudflare tunnel.

On the first launch, create the local n8n owner account. Use a strong password.
The Compose configuration keeps n8n's SSRF protection enabled and narrowly
allowlists only `host.docker.internal`, which is required for the HTTP Request
nodes to call the PowerPoint bridge.

Verify the installed version:

```powershell
docker compose -f compose.n8n.yml exec n8n n8n --version
```

Expected at the time this guide was written:

```text
2.36.8
```

The current image may log that its optional internal Python task runner could
not start. This workflow uses JavaScript Code nodes only, so that warning does
not affect the presenter.

Useful commands:

```powershell
.\n8n-local-logs.cmd
.\n8n-local-stop.cmd
.\n8n-local-upgrade.cmd
```

`n8n-local-upgrade.cmd` pulls the current stable image and recreates only the
container. The named data volume is retained.

## Step 3 — Import the PowerPoint Director workflow

The setup performed for this workspace has already imported and published the
workflow. Use these steps if you recreate the Docker volume or intentionally
start a fresh n8n instance:

1. Open `http://127.0.0.1:5678`.
2. Select **Import from File**.
3. Import:

   ```text
   C:\Users\User\Documents\Data_Science\_TRIAL\AI Agent Presenter\n8n\powerpoint-director.json
   ```

4. Open all three Webhook nodes and confirm:
   - `presenter/session`
   - `presenter/deliver-next`
   - `presenter/handle-question`
5. Save the workflow.
6. Publish it. In n8n 2.x, saving and publishing are separate actions.

Use Production URLs containing `/webhook/`, never `/webhook-test/`.

## Step 4 — Configure the local application

Keep the existing Retell values and `PRESENTER_TOOL_TOKEN` in the project
`.env`. Run the idempotent setup script; it backs up `.env`, preserves existing
Retell secrets, updates the local URLs, and creates a webhook token without
printing it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\configure-local-n8n.ps1
```

It configures these values:

```dotenv
PUBLIC_BASE_URL=
APP_HOST=0.0.0.0
AUTO_TUNNEL=false

N8N_SESSION_WEBHOOK_URL=http://127.0.0.1:5678/webhook/presenter/session
N8N_BRIDGE_URL=http://host.docker.internal:8787/api/bridge
N8N_WEBHOOK_TOKEN=<generated-secret>
```

Open `.env` locally when you need to copy `N8N_WEBHOOK_TOKEN` into the n8n
Header Auth credential. Do not paste it into chat or commit it.

There are two distinct tokens:

- `N8N_WEBHOOK_TOKEN` protects FastAPI/Retell → n8n.
- `PRESENTER_TOOL_TOKEN` protects n8n → FastAPI/PowerPoint.

The imported workflow now receives `PRESENTER_TOOL_TOKEN` during session reset
and uses it dynamically for slide callbacks. Do not paste it into the workflow.

`APP_HOST=0.0.0.0` is required because a Docker container cannot reach a
Windows process that listens only on loopback. Continue opening the UI through
`http://127.0.0.1:8787`; the middleware rejects the UI on other hostnames, and
the bridge still requires `PRESENTER_TOOL_TOKEN`. Restrict inbound port 8787
with Windows Firewall if this PC is on an untrusted LAN.

Restart `voice-app.cmd` after changing `.env`; the existing Python process does
not reload environment variables or source automatically.

## Step 5 — Protect the n8n webhooks

Do this before making local n8n publicly reachable:

1. In n8n, create a **Header Auth** credential.
2. Header name: `Authorization`.
3. Header value:

   ```text
   Bearer <the exact N8N_WEBHOOK_TOKEN from .env>
   ```

4. Apply this credential to all three Webhook nodes.
5. Save and publish again.

The Python client automatically sends this header when
`N8N_WEBHOOK_TOKEN` is configured.

## Step 6 — Smoke-test locally without Retell

1. Confirm Docker n8n is running.
2. Restart `voice-app.cmd`.
3. Open `http://127.0.0.1:8787`.
4. Load a PowerPoint deck or click **Load sample**.
5. Leave **Also start Retell voice** unchecked.
6. Click **Start**.
7. Confirm the n8n execution for `presenter/session` returns `session_reset`.
8. Click **n8n: next beat**.
9. Confirm:
   - n8n runs **Next beat** and **POST slide bridge**.
   - PowerPoint moves.
   - The local console reports `POST /api/bridge/run`.
   - The browser tool log contains `spoken_text`.

If n8n cannot call `host.docker.internal:8787`, test:

```powershell
docker compose -f compose.n8n.yml exec n8n node -e "fetch('http://host.docker.internal:8787/health').then(r=>r.text()).then(console.log)"
```

If this still fails after restarting FastAPI with `APP_HOST=0.0.0.0`, confirm
Docker Desktop is running, `host.docker.internal` resolves inside the container,
and Windows Firewall is not blocking the Docker network.

## Step 7 — Give Retell a public route to n8n

Retell Cloud still cannot call localhost.

### Automatic temporary tunnel

The default local setup lets `voice-app.cmd` own a Cloudflare quick tunnel.
Enable it by running the setup script without a public URL:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\configure-local-n8n.ps1
```

This sets `N8N_AUTO_TUNNEL=true` and clears stale
`N8N_PUBLIC_WEBHOOK_URL` values. On every application startup, FastAPI:

1. Waits for local n8n `/healthz` on port 5678.
2. Starts `cloudflared` against that port.
3. Captures the new `https://...trycloudflare.com` hostname and writes it to `.env` for display (it is not reused on the next start).
4. Health-checks the public tunnel.
5. Updates Retell's `deliver_next` and `handle_audience_question` URLs.
6. Updates both Retell functions' authorization header.
7. Stops that tunnel when the app shuts down.

Do not run `n8n-quick-tunnel.cmd` at the same time as automatic mode. That
script is retained only as a manual diagnostic fallback.

### Stable named tunnel

A named Cloudflare Tunnel remains the preferred production option. With a
Cloudflare-managed domain:

```powershell
cloudflared tunnel login
cloudflared tunnel create presenter-n8n
cloudflared tunnel route dns presenter-n8n presenter-n8n.example.com
```

Create `%USERPROFILE%\.cloudflared\config.yml` using the tunnel ID returned by
Cloudflare:

```yaml
tunnel: <tunnel-uuid>
credentials-file: C:\Users\User\.cloudflared\<tunnel-uuid>.json

ingress:
  - hostname: presenter-n8n.example.com
    service: http://127.0.0.1:5678
  - service: http_status:404
```

Run it:

```powershell
cloudflared tunnel run presenter-n8n
```

Save the public origin:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\configure-local-n8n.ps1 `
  -PublicWebhookUrl "https://presenter-n8n.example.com"
```

Passing a public URL sets `N8N_AUTO_TUNNEL=false`. Recreate n8n so it displays
the correct Production webhook URLs:

```powershell
docker compose -f compose.n8n.yml up -d --force-recreate n8n
```

## Step 8 — Point Retell at local n8n

On startup, the local app now finds these two Retell custom functions and keeps
their URL, authorization header, method, timeout, and speech behavior synced.
Keep only these two functions:

### `deliver_next`

```text
POST https://presenter-n8n.example.com/webhook/presenter/deliver-next
```

Parameters:

```json
{ "type": "object", "properties": {} }
```

### `handle_audience_question`

```text
POST https://presenter-n8n.example.com/webhook/presenter/handle-question
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

If automatic synchronization reports an error, configure both functions
manually with:

```text
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

Use a timeout of at least 30 seconds. Keep **Talk After Action Completed** on
and **Talk While Waiting** off. Do not enable the fallback PowerPoint MCP tools
on this scripted presenter.

## Step 9 — Full voice test

1. Restart n8n and the named tunnel.
2. Restart `voice-app.cmd`.
3. Load the deck.
4. Select **Also start Retell voice**.
5. Click **Start** and allow microphone access.
6. Confirm Retell calls local n8n's `deliver-next` Production webhook.
7. Confirm n8n calls the private FastAPI bridge.
8. Ask one known question and verify the Q&A workflow and slide jump.

For Azure OpenAI retrieval, source-document ingestion, confidence controls,
fallback behavior, and the updated Q&A node graph, continue with
[QA_RAG.md](QA_RAG.md).

## Step 10 — Remove the old npm installation

Only after the complete voice test passes:

```powershell
npm uninstall -g n8n
where.exe n8n
```

Node 20 can remain installed for other projects. Docker n8n carries its own
compatible Node runtime.

## Updating and rollback

Upgrade to the newest stable Docker image:

```powershell
.\n8n-local-upgrade.cmd
```

Before a major upgrade, export workflows/credentials and review the n8n
Migration Report. To roll back, change the image in `compose.n8n.yml` to a
known-good version, for example:

```yaml
image: docker.n8n.io/n8nio/n8n:2.36.8
```

Then recreate the container. Database migrations may require `n8n db:revert`;
follow the release-specific n8n documentation rather than only changing the
image tag.
