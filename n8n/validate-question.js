const prepared = $('Prepare question').first().json || {};
let agent = {};
try {
  agent = $input.first().json || {};
} catch (error) {
  agent = { ok: false, error: String(error) };
}

const question = String(prepared.question || '').trim();
const defaultText = question
  ? '呢條問題我喺現有資料搵唔到可靠答案。我而家接返簡報。'
  : '我未聽清楚問題。可以再問一次，或者我接返簡報。';
const usable = agent.ok === true && typeof agent.spoken_text === 'string'
  && agent.spoken_text.trim().length > 0;
const spokenText = usable ? agent.spoken_text.trim() : defaultText;

let slide = Number(agent.slide || 0);
let recommendedSlide = Number(agent.recommended_slide || agent.slide || 0);
const slideCount = Number(prepared.slide_count || 0);
if (!Number.isInteger(slide) || slide < 1 || (slideCount > 0 && slide > slideCount)) {
  slide = 0;
}
if (
  !Number.isInteger(recommendedSlide)
  || recommendedSlide < 1
  || (slideCount > 0 && recommendedSlide > slideCount)
) {
  recommendedSlide = 0;
}
const shouldFlip = usable
  && agent.should_change_slide === true
  && slide > 0
  && slide !== Number(prepared.current_slide || 0)
  && !!prepared.bridge_url;

return [{
  json: {
    ok: usable,
    mode: String(agent.mode || 'safe_abstention'),
    answerable: usable && agent.answerable !== false,
    decline: !usable || agent.answerable === false,
    auto_continue: true,
    done: false,
    slide_changed: shouldFlip,
    spoken_text: spokenText,
    spoken_grounding: spokenText,
    spoken_text_en: usable ? String(agent.spoken_text_en || '') : '',
    next_action: 'speak_then_call_deliver_next',
    instruction: String(
      agent.instruction
      || 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
    ),
    slide: shouldFlip ? slide : null,
    recommended_slide: recommendedSlide || null,
    answer_confidence: Number(agent.answer_confidence || 0),
    slide_confidence: Number(agent.slide_confidence || 0),
    source_ids: Array.isArray(agent.source_ids) ? agent.source_ids : [],
    sources: Array.isArray(agent.sources) ? agent.sources : [],
    skip_http: !shouldFlip,
    actions: shouldFlip ? ('goto_slide:' + slide) : '',
    http_url: shouldFlip ? (prepared.bridge_url + '/run') : '',
    bridge_token: prepared.bridge_token || '',
    question,
    bookmark: prepared.bookmark,
    presentation_done: !!prepared.presentation_done,
    agent_error: usable ? '' : String(agent.error || agent.message || 'Q&A agent unavailable'),
  },
}];
