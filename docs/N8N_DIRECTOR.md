# n8n Cloud as Director (step 1)

The local app is the **frontend + PowerPoint adapter**. n8n Cloud owns the script cursor. Retell is voice only.

## Smoke test (no Retell)

Leave **Also start Retell voice** unchecked. If a previous test already joined Retell, press **Stop**.

1. Re-import `n8n/powerpoint-director.json` **or** paste `n8n/next-beat.js` into **Next beat**, then **Publish**. The sample talk is 12 slides; beats come from `data/script.xlsx` via `python -m voice_app.sample_pack`.

### If the talk stops after slide 1

The Cloud **Next beat** node is still returning `do_not_speak` / empty `spoken_text` on the second `deliver_next` (idle gate / tooSoon). The agent then stays silent and never retries.

**Fix:** paste the current `n8n/next-beat.js` (it always increments; no idle reject). Publish. Restart the local app. **Start a new session**, do not resume. In n8n Executions, the second deliver-next run must show `spoken_text` for slide 2, not `do_not_speak: true`.

### If later slides flip in a burst

The agent chained several `deliver_next` calls before finishing the line, or **spoke two or more slides in one utterance** (no `agent_stop_talking` in between). Restart the local app. Extra queued slides now flip during that long utterance using the sample script length. You should see `Slide queue: catch-up during concatenated speech` in the console.
2. Use the current workflow export. **POST slide bridge** and **POST question slide** now derive `Authorization` from the `bridge_token` sent at session start; do not paste the token into the workflow.
3. Copy the **Production** URL of **Webhook session** (must contain `/webhook/presenter/session`, not `/webhook-test/`).
4. `.env`:

```
N8N_SESSION_WEBHOOK_URL=https://<your-n8n>/webhook/presenter/session
```

Restart `voice-app.cmd`.

5. Browser: **Load sample** → **Start** (voice off).
6. Confirm n8n Executions shows `session_reset` with a `bridge_url`.
7. Click **n8n: next beat** on the local console (do not click Execute workflow in n8n).

PowerPoint should move. The tool log should show JSON with `spoken_text`.

### If Next beat is red: `No bridge URL`

The Webhook node puts your JSON under `body`. Older Next beat code looked only at workflow static data and **threw**, so the run stopped before PowerPoint.

**In n8n:** double-click **Next beat**, replace the code with `n8n/next-beat.js` (never `throw`). If **Reset cursor** exists, paste `n8n/reset-cursor.js` there too. Save and **Publish**.

On **Has actions?** / **Call PowerPoint?**, wire the **false** output to **Merge result** (empty actions / no URL must still finish).

Then in the local console: confirm **Bridge URL** is a `trycloudflare` link → Load sample → **Start** (voice off) → **n8n: next beat**. Do not click Execute workflow.

### If the console shows `Unused Respond to Webhook node found`

n8n Cloud returns HTTP 500 if **any** leftover **Respond to Webhook** node is on the canvas while the Webhook nodes use **Using Last Node**. The first import had Respond nodes; later versions do not. A partial update leaves both.

**Fastest fix in n8n (do not re-import):**

1. Open **PowerPoint Director**.
2. Delete every **Respond to Webhook** node (names like Respond session / Respond deliver-next).
3. On each Webhook: Respond = **Using Last Node** → **First Entry JSON**.
4. **Save** and **Publish**.

Then Load sample → Start (voice off) → **n8n: next beat**.

### If n8n still shows “waiting” / no response

You clicked **Execute workflow** or **Listen for test event**. That waits forever until something POSTs the *test* URL. Cancel it. Use **Production** URL only, or the local **n8n: next beat** button.

If the local button times out and the Python console never prints `POST /api/bridge/run`, n8n Cloud cannot reach the Cloudflare tunnel. Paste a dry-run body from n8n:

```json
{ "dry": true, "bridge_url": "https://YOUR-TUNNEL/api/bridge" }
```

to `POST …/webhook/presenter/deliver-next`. You should get `spoken_text` immediately with `skip_http`. Then we know the webhook works and the hang is the tunnel/HTTP node.

## Retell

Only after the smoke test: check **Also start Retell voice**. Point Retell `deliver_next` at n8n `presenter/deliver-next`, and `handle_audience_question` at `presenter/handle-question`. The local app refreshes the PowerPoint bridge token in n8n at every session start.

## Bridge contract

Authenticated with `Authorization: Bearer <PRESENTER_TOOL_TOKEN>`.

| Call | Body | Effect |
| --- | --- | --- |
| `GET /api/bridge` | | Catalog + live status |
| `POST /api/bridge/run` | `{"actions":"goto_slide:3; next"}` | Run COM actions in order |

