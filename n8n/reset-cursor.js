const store = $getWorkflowStaticData('global');
const raw = $input.first().json || {};
const payload = (raw.body && typeof raw.body === 'object' && !Array.isArray(raw.body))
  ? raw.body
  : raw;
store.bridgeUrl = String(payload.bridge_url || raw.bridge_url || '').replace(/\/$/, '');
store.bridgeToken = String(payload.bridge_token || raw.bridge_token || '');
store.qaUrl = String(
  payload.qa_url || raw.qa_url || (store.bridgeUrl ? store.bridgeUrl + '/qa' : ''),
).replace(/\/$/, '');
store.qaDeckId = String(payload.qa_deck_id || raw.qa_deck_id || '');
store.callId = payload.call_id || raw.call_id || '';
store.slideCount = Number(
  (payload.status && payload.status.slide_count) || raw.slide_count || 0,
);
store.lastSlide = Number(
  (payload.status && payload.status.slide) || raw.current_slide || 1,
);
store.beatIndex = 0;
store.bookmark = null;
store.mode = 'presenting';
store.lastAdvanceAt = 0;
store.lastSpoken = '';
store.lastSpokenEn = '';
store.lineLockUntil = 0;
store.talkDone = false;
const pause = Number(payload.slide_pause_ms);
store.slidePauseMs = Number.isFinite(pause) && pause >= 0 ? pause : (store.slidePauseMs || 800);
return [{
  json: {
    ok: true,
    event: 'session_reset',
    call_id: store.callId,
    bridge_url: store.bridgeUrl,
    qa_url: store.qaUrl,
    qa_deck_id: store.qaDeckId,
    beat_index: 0,
    hint: store.bridgeUrl
      ? 'Cursor reset. You can POST presenter/deliver-next.'
      : 'bridge_url was empty. Start the local console with a live tunnel (do not click Execute workflow).',
  },
}];
