const beat = $('Next beat').first().json;
let bridge = {};
try { bridge = $input.first().json || {}; } catch (e) { bridge = { error: String(e) }; }
const bridgeError = bridge.error || bridge.message || '';
return [{
  json: {
    ok: beat.ok !== false && !bridgeError,
    done: !!beat.done,
    auto_continue: !!beat.auto_continue && !beat.done,
    repeat: !!beat.repeat,
    next_action: beat.next_action || '',
    instruction: beat.instruction || '',
    do_not_speak: !!beat.do_not_speak,
    spoken_text: beat.spoken_text || '',
    spoken_text_en: beat.spoken_text_en || '',
    slide: (bridge.status && bridge.status.slide) || beat.slide || null,
    seq: beat.seq || null,
    applied: bridge.applied || [],
    error: beat.error || bridgeError || '',
    bridge_http: bridge,
  },
}];
