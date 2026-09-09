const store = $getWorkflowStaticData('global');
const raw = $input.first().json || {};
const payload = (raw.body && typeof raw.body === 'object' && !Array.isArray(raw.body))
  ? raw.body
  : raw;
const args = payload.args || raw.args || {};
const query = (raw.query && typeof raw.query === 'object') ? raw.query : {};
const requestCallId = String(
  payload.call_id || raw.call_id || args.call_id
  || (payload.call && payload.call.call_id) || '',
);
const staleSession = !!(store.callId && requestCallId && requestCallId !== String(store.callId));

function pickQuestion() {
  let question = payload.question || args.question || query.question || payload.text || '';
  if (!question && payload.call && payload.call.transcript) {
    const lines = String(payload.call.transcript).split('\n').reverse();
    for (const line of lines) {
      if (/^(User|user|Caller):/i.test(line)) {
        question = line.replace(/^[^:]+:\s*/, '');
        break;
      }
    }
  }
  return String(question || '').trim();
}

if (!staleSession && store.bookmark == null) {
  store.bookmark = store.beatIndex == null ? 0 : store.beatIndex;
}
if (!staleSession) {
  store.mode = 'qa';
  store.lastAdvanceAt = 0;
  store.lineLockUntil = 0;
}

return [{
  json: {
    ok: true,
    question: staleSession ? '' : pickQuestion(),
    qa_url: store.qaUrl || (store.bridgeUrl ? store.bridgeUrl + '/qa' : ''),
    bridge_url: store.bridgeUrl || '',
    bridge_token: store.bridgeToken || '',
    call_id: store.callId || '',
    qa_deck_id: store.qaDeckId || '',
    current_slide: store.lastSlide || null,
    slide_count: store.slideCount || null,
    bookmark: store.bookmark,
    presentation_done: !!store.talkDone,
    stale_session: staleSession,
  },
}];
