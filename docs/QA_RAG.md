# Grounded Azure OpenAI Q&A

The presenter keeps its original deterministic talk path and adds a separate
Q&A branch:

```text
Retell handle_audience_question
  -> local n8n (bookmark the script cursor)
  -> private FastAPI Q&A endpoint
  -> Azure OpenAI embeddings + Qdrant retrieval
  -> Azure OpenAI grounded JSON answer
  -> n8n validation
  -> optional private PowerPoint slide jump
  -> Retell speaks the answer
  -> deliver_next restores the bookmark
```

n8n remains the director. The Q&A model cannot call PowerPoint and cannot
change the script cursor. It may only recommend a slide from retrieved
candidates. n8n validates that recommendation before converting it to
`goto_slide:N`.

The Azure key stays in the local application's `.env`. It is not stored in the
workflow export or exposed to Retell. This also avoids disabling n8n 2.x's
default protection against environment-variable access in Code nodes.

## Services

- n8n: `http://127.0.0.1:5678`
- Qdrant: `http://127.0.0.1:6333`
- FastAPI: `http://127.0.0.1:8787`
- n8n-to-FastAPI: `http://host.docker.internal:8787/api/bridge`
- Retell-to-n8n: the current Cloudflare or named-tunnel HTTPS origin

`n8n-local.cmd` starts both n8n and Qdrant. Both use named Docker volumes.

## Azure OpenAI configuration

Create two Azure OpenAI deployments:

1. A chat model that supports JSON response mode.
2. An embedding model.

Add these values to `.env`:

```dotenv
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=YOUR-KEY
AZURE_OPENAI_API_VERSION=YOUR-SUPPORTED-API-VERSION
AZURE_OPENAI_CHAT_DEPLOYMENT=YOUR-CHAT-DEPLOYMENT-NAME
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=YOUR-EMBEDDING-DEPLOYMENT-NAME

QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=presenter_knowledge
QA_KNOWLEDGE_DIR=data/knowledge_sources
QA_AUTO_INDEX=true
QA_ALWAYS_SELECT_SLIDE=true
```

Azure uses deployment names, which may differ from underlying model names.
Restart `voice-app.cmd` after changing `.env`.

The selected slide descriptions, document chunks, and audience questions are
sent to the configured Azure OpenAI resource. Confirm the resource region,
retention policy, and document classification are acceptable before indexing
confidential material.

If any Azure setting is absent, the application stays operational but Q&A uses
safe abstention only. If Qdrant is temporarily unavailable while Azure is
configured, the app can use in-memory vectors for that process. If Azure
generation fails or the evidence does not pass validation, it gives the fixed
safe-abstention response without changing slides.

## Knowledge ingestion

Loading a deck starts indexing in the background. The index contains:

- every slide's visible text;
- tables and chart series readable from the PPTX;
- speaker notes;
- the prepared presenter script in `data/script.xlsx`;
- `.txt`, `.md`, `.csv`, `.json`, `.xlsx`, and `.xlsm` files under
  `data/knowledge_sources` only (including `knowledge.xlsx` fact cards).

`data/knowledge.xlsx` is not used. Put every knowledge file in
`knowledge_sources`.

The PowerPoint file and knowledge files are hashed together. An unchanged
corpus reuses the persistent Qdrant index on restart. After a successful
Qdrant sync, points that do not belong to the current hash are deleted, so
removed knowledge files do not keep old vectors. Use **Reindex Q&A** in the
console after changing content while the app is running.

Current extraction covers text, tables, chart values, and notes. A screenshot
or diagram with no text needs a written description in speaker notes or a
knowledge-source document. Vision-based slide description can be added later
as an ingestion-only step without changing the live Q&A path.

## Retrieval and answer validation

The same question embedding searches two record types, and the results are
fused with local lexical matching so names, numbers, and exact terminology
retain weight:

- `knowledge`: factual answer evidence;
- `slide`: visual candidates.

The chat model receives only the top records and must return structured JSON.
The local service then verifies:

- the answer is non-empty and grounded by retrieved source IDs;
- confidence meets `QA_MIN_ANSWER_CONFIDENCE`;
- the slide is one of the retrieved candidates;
- slide confidence meets `QA_MIN_SLIDE_CONFIDENCE`;
- the slide differs from the current slide.

The response includes source labels and confidence values for diagnostics, but
Retell speaks only `spoken_text`.

With `QA_ALWAYS_SELECT_SLIDE=true`, every grounded answer selects the most
relevant valid slide. A line such as `Recommended visual support for this
section: slide 10` in the cited source is treated as explicit authored metadata
and takes priority over semantic slide selection.

Useful tuning:

```dotenv
QA_TOP_K_KNOWLEDGE=6
QA_TOP_K_SLIDES=3
QA_MIN_ANSWER_CONFIDENCE=0.35
QA_MIN_SLIDE_CONFIDENCE=0.45
QA_AZURE_TIMEOUT_S=12
```

Raise confidence thresholds to reduce incorrect answers or unnecessary slide
jumps. Lower them only after inspecting real retrieval logs.

## n8n Q&A branch

Import or update `n8n/powerpoint-director.json`, preserve Header Auth on all
three webhooks, then publish it. The Q&A branch is:

```text
Webhook handle-question
  -> Prepare question
  -> Call Q&A agent
  -> Validate Q&A
  -> Flip for question?
  -> POST question slide
  -> Merge question
```

`Prepare question` stores the original `beatIndex` as `bookmark`.
`Call Q&A agent` calls the authenticated private endpoint
`/api/bridge/qa`. `Validate Q&A` constructs slide actions only from a validated
integer within the loaded deck's range. After Retell speaks, its next
`deliver_next` call restores `beatIndex` from `bookmark`.

## Test without Retell

For the supplied multi-document evaluation corpus and automated test runner,
see [QA_EVALUATION.md](QA_EVALUATION.md).

1. Start Docker Desktop.
2. Run `n8n-local.cmd`.
3. Run `voice-app.cmd`.
4. Open `http://127.0.0.1:8787` and load the sample deck.
5. Wait until **Q&A knowledge** reports ready.
6. Start the slideshow without Retell.
7. POST a test question to the local n8n production webhook using the same
   `Authorization: Bearer <N8N_WEBHOOK_TOKEN>` header.

Example body:

```json
{
  "question": "公司現金仲可以維持幾耐？"
}
```

Expected result: a grounded Cantonese answer, source metadata, and slide 7 when
the confidence threshold allows the jump.

## Operational limitations

- n8n workflow static state still represents one active presentation. Multiple
  simultaneous calls require a transactional state store keyed by `call_id`.
  The Docker configuration therefore limits production executions to one at a
  time, and the workflow rejects a mismatched Retell `call_id`.
- Quick-tunnel hostnames remain temporary; the app updates Retell each boot.
- The first index of a changed corpus uses Azure embedding calls and may take
  longer. Subsequent starts reuse Qdrant.
- Never expose Qdrant or the FastAPI bridge publicly.
