# Harbour Presenter security and data-handling notes

Document ID: EVAL-SECURITY-2026-06  
Status: Internal evaluation reference  
Effective date: 30 June 2026

This is fictional test material for the Harbour AI demonstration.

## Data-flow boundaries

The PowerPoint file remains on the presentation computer. Local n8n directs the
script, and the private FastAPI bridge controls desktop PowerPoint. The raw
PowerPoint bridge is not intended to be reachable from the public internet.

Audience questions and the retrieved reference snippets needed to answer those
questions are sent to the configured Azure OpenAI resource. Retell processes
the live voice conversation. Customers must approve the selected Azure region,
Retell configuration, and retention settings before production use.

## Demonstration retention policy

For this evaluation environment:

- raw meeting audio storage is disabled by default;
- generated call transcripts are retained for 30 days;
- operational audit events are retained for 90 days;
- source PowerPoint files and knowledge documents remain on the local
  presentation computer;
- Qdrant stores embeddings and metadata locally on that computer.

If a customer explicitly enables raw-audio recording, that choice requires a
separate written approval. The default answer to “does the system retain raw
audio?” is therefore no for this evaluation environment.

## Access controls

The design uses two independent bearer secrets:

- the n8n webhook token protects Retell and the local application when they
  call n8n;
- the presenter-tool token protects calls from n8n to the private FastAPI
  PowerPoint bridge.

The secrets must not be logged, spoken, placed in slide notes, or copied into a
knowledge document.

Enterprise single sign-on and enhanced audit-log export are roadmap features
scheduled for the third quarter of 2026. They must not be described as already
available.

Recommended visual support for security-boundary questions: slide 4 for the
product architecture. Use slide 8 only for SSO or audit-log roadmap questions.

