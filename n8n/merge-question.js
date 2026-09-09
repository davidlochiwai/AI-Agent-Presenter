const ask = $('Validate Q&A').first().json;
let bridge = {};
try { bridge = $input.first().json || {}; } catch (e) { bridge = { error: String(e) }; }
const bridgeError = bridge.error || bridge.message || '';
return [{
  json: {
    ok: ask.ok !== false && !bridgeError,
    mode: 'qa',
    done: false,
    auto_continue: true,
    answerable: ask.answerable !== false,
    decline: !!ask.decline,
    slide_changed: !!ask.slide_changed,
    spoken_text: ask.spoken_text || '',
    spoken_grounding: ask.spoken_grounding || ask.spoken_text || '',
    spoken_text_en: ask.spoken_text_en || '',
    next_action: ask.next_action || 'speak_then_call_deliver_next',
    instruction: ask.instruction || 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
    slide: (bridge.status && bridge.status.slide) || ask.slide || null,
    recommended_slide: ask.recommended_slide || null,
    card_id: ask.card_id || '',
    bookmark: ask.bookmark,
    presentation_done: !!ask.presentation_done,
    qa_mode: ask.mode || '',
    answer_confidence: ask.answer_confidence || 0,
    slide_confidence: ask.slide_confidence || 0,
    source_ids: ask.source_ids || [],
    sources: ask.sources || [],
    applied: bridge.applied || [],
    error: ask.error || ask.agent_error || bridgeError || '',
  },
}];
