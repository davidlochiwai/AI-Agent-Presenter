# Grounded Azure OpenAI Q&A

The presenter keeps its original deterministic talk path and adds a separate
Q&A branch:

```text
Retell handle_audience_question
  -> Python director (bookmark the script cursor)
  -> Azure OpenAI embeddings + Qdrant retrieval
  -> Azure OpenAI grounded JSON answer
  -> optional PowerPoint slide jump
  -> Retell speaks the answer
  -> deliver_next restores the bookmark
```

The Python director owns presentation state. The Q&A model cannot call
PowerPoint and cannot change the script cursor. It may only recommend a slide
from retrieved candidates. The director validates that recommendation before
converting it to `goto_slide:N`.

The Azure key stays in the local application's `.env`. It is not exposed to
Retell.

## Services

- Qdrant: `http://127.0.0.1:6333`
- FastAPI / Python director: `http://127.0.0.1:8787`
- Retell-to-director: the current Cloudflare or named-tunnel HTTPS origin

`qdrant-local.cmd` starts Qdrant with a named Docker volume.

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
knowledge-source document.

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

## Test without Retell

For the supplied multi-document evaluation corpus and automated test runner,
see [QA_EVALUATION.md](QA_EVALUATION.md).

1. Start Docker Desktop.
2. Run `qdrant-local.cmd`.
3. Run `voice-app.cmd`.
4. Open `http://127.0.0.1:8787` and load the sample deck.
5. Wait until **Q&A knowledge** reports ready.
6. Start the slideshow without Retell.
7. POST a test question to `http://127.0.0.1:8787/webhook/presenter/handle-question`
   using `Authorization: Bearer <DIRECTOR_WEBHOOK_TOKEN>`.

Example body:

```json
{
  "question": "公司現金仲可以維持幾耐？"
}
```

Expected result: a grounded Cantonese answer, source metadata, and slide 7 when
the confidence threshold allows the jump.

## Operational limitations

- Director state represents one active presentation. A mismatched Retell
  `call_id` is rejected.
- Quick-tunnel hostnames remain temporary; the app updates Retell each boot.
- The first index of a changed corpus uses Azure embedding calls and may take
  longer. Subsequent starts reuse Qdrant.
- Never expose Qdrant or the FastAPI bridge publicly.
