# Harbour Presenter deployment-readiness guide

Document ID: EVAL-DEPLOYMENT-2026-06  
Status: Internal evaluation reference  
Effective date: 30 June 2026

This is fictional test material for the Harbour AI demonstration.

## Supported presentation computer

The demonstration configuration requires:

- Windows 11;
- licensed Microsoft 365 desktop PowerPoint;
- Docker Desktop for local n8n and Qdrant;
- a working microphone and speaker;
- outbound HTTPS access to Retell, Azure OpenAI, and Cloudflare;
- at least 8 GB of available memory and 5 GB of free disk space.

The PowerPoint automation process must run in an interactive signed-in desktop
session. It is not designed to run as a headless Windows service.

## Network readiness

The customer must complete the network check at least two business days before
the live presentation. The check confirms outbound HTTPS on port 443 and local
access to:

- `127.0.0.1:5678` for n8n;
- `127.0.0.1:6333` for Qdrant;
- `127.0.0.1:8787` for the presenter console.

Ports 5678, 6333, and 8787 should not be exposed directly to the public
internet. Retell reaches only the authenticated n8n webhooks through the
approved Cloudflare hostname.

## Content freeze and rehearsal

The final PowerPoint file, script, and knowledge sources should be frozen one
business day before the event. After any content change, the operator must load
the deck again or select **Reindex Q&A**, then wait until Q&A knowledge reports
ready.

The recommended minimum is one complete rehearsal after the content freeze.
Customer pilots may require additional rehearsals; Harbour Bank completed
three.

## Start-of-day checklist

1. Start Docker Desktop.
2. Run `n8n-local.cmd`.
3. Run `voice-app.cmd`.
4. Confirm n8n and Qdrant report healthy.
5. Load the final deck and wait for Q&A indexing.
6. Verify the public n8n tunnel and Retell function synchronization.
7. Run one scripted beat and one known Q&A question before admitting the
   audience.

Recommended visual support for architecture and workflow questions: slide 4.
Recommended visual support for tunnel-risk questions: slide 9.

