"""Write sample_talk.pptx, script.xlsx, knowledge_sources/knowledge.xlsx, and n8n Next beat code from talk_content."""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from voice_app.talk_content import KNOWLEDGE, SCRIPT, SLIDES, n8n_beats, n8n_knowledge

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
N8N = ROOT / "n8n"
DECK_PATH = DATA / "sample_talk.pptx"
SCRIPT_PATH = DATA / "script.xlsx"
KNOWLEDGE_DIR = DATA / "knowledge_sources"
KNOWLEDGE_PATH = KNOWLEDGE_DIR / "knowledge.xlsx"

NAVY = RGBColor(0x1B, 0x3A, 0x4B)
GOLD = RGBColor(0xC4, 0xA3, 0x5A)
INK = RGBColor(0x1A, 0x24, 0x2A)
MUTED = RGBColor(0x5A, 0x6A, 0x72)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CREAM = RGBColor(0xF7, 0xF4, 0xEE)
FONT = "Microsoft JhengHei"

NEXT_BEAT_JS = r'''const store = $getWorkflowStaticData('global');
const raw = $input.first().json || {};
const payload = (raw.body && typeof raw.body === 'object' && !Array.isArray(raw.body))
  ? raw.body
  : raw;
const query = (raw.query && typeof raw.query === 'object') ? raw.query : {};
const dry = payload.dry === true || payload.dry === 'true'
  || query.dry === '1' || query.dry === 'true' || raw.dry === true;
const fromConsole = payload.source === 'console' || raw.source === 'console';
const args = payload.args || raw.args || {};
const requestCallId = String(
  payload.call_id || raw.call_id || args.call_id
  || (payload.call && payload.call.call_id) || '',
);

if (!fromConsole && store.callId && requestCallId && requestCallId !== String(store.callId)) {
  return [{
    json: {
      ok: false,
      skip_http: true,
      done: false,
      repeat: false,
      next_action: 'stay_silent',
      instruction: 'This request belongs to an inactive presentation. Stay silent.',
      spoken_text: '',
      spoken_text_en: '',
      actions: '',
      http_url: '',
      error: 'Stale call_id; the presentation cursor was not changed.',
    },
  }];
}

if (fromConsole) {
  const incomingBridge = String(
    payload.bridge_url || raw.bridge_url || query.bridge_url || store.bridgeUrl || '',
  ).replace(/\/$/, '');
  if (incomingBridge) store.bridgeUrl = incomingBridge;
  const incomingToken = String(payload.bridge_token || raw.bridge_token || '');
  if (incomingToken) store.bridgeToken = incomingToken;
  const incomingPause = Number(payload.slide_pause_ms);
  if (Number.isFinite(incomingPause) && incomingPause >= 0) store.slidePauseMs = incomingPause;
}

const beats = /*BEATS*/;
const speakOnly = 'Speak spoken_text verbatim in Cantonese. Stop at the last character. Do not continue into the next slide. After that one line, call deliver_next once. Never call it again in this turn.';
const lastLine = 'Speak spoken_text verbatim once. The prepared talk is then complete. Do not repeat it and do not call deliver_next on silence. Remain listening. If the audience asks a real question, call handle_audience_question.';

function holdMs(text) {
  const n = String(text || '').length;
  const pause = Number(store.slidePauseMs);
  const extra = Number.isFinite(pause) && pause >= 0 ? pause : 800;
  return Math.min(40000, Math.max(2500, Math.round((n / 3.8) * 1000 + 400))) + extra;
}

function silentDone() {
  store.talkDone = true;
  return [{
    json: {
      ok: true,
      skip_http: true,
      done: true,
      auto_continue: false,
      repeat: false,
      next_action: 'listen_for_questions',
      instruction: 'The prepared talk is finished. Do not repeat the last line and do not call deliver_next. Remain listening. If the audience asks a real question, call handle_audience_question.',
      spoken_text: '',
      spoken_text_en: '',
      actions: '',
      http_url: '',
      slide: store.lastSlide || null,
      seq: store.lastSeq || null,
      beat_index: store.beatIndex,
      beats_total: beats.length,
      bridge_url: store.bridgeUrl,
      error: '',
    },
  }];
}

if (store.beatIndex == null) store.beatIndex = 0;

if (store.mode === 'qa' && store.bookmark != null) {
  store.beatIndex = store.bookmark;
  store.bookmark = null;
  store.mode = 'presenting';
  store.lastAdvanceAt = 0;
  store.lineLockUntil = 0;
  store.talkDone = false;
}

const now = Date.now();

if (store.talkDone) {
  return silentDone();
}

if (!fromConsole && !dry && store.lineLockUntil && now < store.lineLockUntil) {
  return [{
    json: {
      ok: true,
      skip_http: true,
      done: false,
      auto_continue: false,
      repeat: true,
      next_action: 'stay_silent',
      instruction: 'Stay silent. Do not speak. Do not repeat the previous line. After the room is quiet, call deliver_next once.',
      spoken_text: '',
      spoken_text_en: '',
      actions: '',
      http_url: '',
      slide: store.lastSlide || null,
      seq: store.lastSeq || null,
      beat_index: store.beatIndex,
      beats_total: beats.length,
      bridge_url: store.bridgeUrl,
      error: '',
    },
  }];
}

if (!store.bridgeUrl) {
  return [{
    json: {
      ok: false,
      skip_http: true,
      error: 'No bridge URL. Use the local console button n8n: next beat (that POSTs bridge_url). Do not click Execute workflow.',
      spoken_text: '',
      actions: '',
      auto_continue: false,
      done: false,
      received_keys: Object.keys(raw),
    },
  }];
}

if (store.beatIndex >= beats.length) {
  return silentDone();
}

const beat = beats[store.beatIndex];
store.beatIndex += 1;
const isLast = store.beatIndex >= beats.length;
const skipHttp = dry || !beat.actions;
store.mode = 'presenting';
store.lastAdvanceAt = now;
store.lastSpoken = beat.script_yue;
store.lastSpokenEn = beat.script_en;
store.lastSlide = beat.slide;
store.lastSeq = beat.seq;
store.lineLockUntil = now + holdMs(beat.script_yue);
if (isLast) store.talkDone = true;
return [{
  json: {
    ok: true,
    skip_http: skipHttp,
    done: isLast,
    auto_continue: false,
    repeat: false,
    next_action: isLast ? 'listen_for_questions' : 'speak_then_wait_for_silence',
    instruction: isLast ? lastLine : speakOnly,
    spoken_text: beat.script_yue,
    spoken_text_en: beat.script_en,
    actions: beat.actions,
    slide: beat.slide,
    seq: beat.seq,
    beat_index: store.beatIndex,
    beats_total: beats.length,
    bridge_url: store.bridgeUrl,
    bridge_token: store.bridgeToken || '',
    http_url: skipHttp ? '' : (store.bridgeUrl + '/run'),
  },
}];
'''

MERGE_JS = r'''const beat = $('Next beat').first().json;
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
'''

LEGACY_HANDLE_QUESTION_JS = r'''const store = $getWorkflowStaticData('global');
const raw = $input.first().json || {};
const payload = (raw.body && typeof raw.body === 'object' && !Array.isArray(raw.body))
  ? raw.body
  : raw;
const args = payload.args || raw.args || {};
const query = (raw.query && typeof raw.query === 'object') ? raw.query : {};

const incomingBridge = String(
  payload.bridge_url || raw.bridge_url || args.bridge_url || store.bridgeUrl || '',
).replace(/\/$/, '');
if (incomingBridge) store.bridgeUrl = incomingBridge;
const incomingToken = String(payload.bridge_token || raw.bridge_token || args.bridge_token || '');
if (incomingToken) store.bridgeToken = incomingToken;

function pickQuestion() {
  let q = payload.question || args.question || query.question || payload.text || '';
  if (!q && payload.call && payload.call.transcript) {
    const lines = String(payload.call.transcript).split('\n').reverse();
    for (const line of lines) {
      if (/^(User|user|Caller):/i.test(line)) {
        q = line.replace(/^[^:]+:\s*/, '');
        break;
      }
    }
  }
  return String(q || '').trim();
}

function scoreCard(question, card) {
  const q = question.toLowerCase();
  let n = 0;
  const keys = String(card.keywords || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  for (const key of keys) {
    if (key && q.includes(key.toLowerCase())) n += key.length >= 2 ? 2 : 1;
  }
  if (card.topic && q.includes(String(card.topic).toLowerCase())) n += 3;
  return n;
}

const cards = /*KNOWLEDGE*/;
const question = pickQuestion();
if (store.bookmark == null) store.bookmark = store.beatIndex == null ? 0 : store.beatIndex;
store.mode = 'qa';
store.lastAdvanceAt = 0;
store.lineLockUntil = 0;

if (!question) {
  return [{
    json: {
      ok: true,
      skip_http: true,
      slide_changed: false,
      spoken_text: '我未聽清楚問題。可以再問一次，或者我接返簡報。',
      spoken_grounding: '我未聽清楚問題。可以再問一次，或者我接返簡報。',
      next_action: 'speak_then_call_deliver_next',
      instruction: 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
      auto_continue: true,
      actions: '',
      http_url: '',
      slide: null,
    },
  }];
}

let best = null;
let bestScore = 0;
for (const card of cards) {
  const s = scoreCard(question, card);
  if (s > bestScore) {
    best = card;
    bestScore = s;
  }
}

if (!best || bestScore < 2) {
  return [{
    json: {
      ok: true,
      skip_http: true,
      decline: true,
      slide_changed: false,
      spoken_text: '呢條問題知識庫未有記載。我而家接返簡報。',
      spoken_grounding: '呢條問題知識庫未有記載。我而家接返簡報。',
      next_action: 'speak_then_call_deliver_next',
      instruction: 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
      auto_continue: true,
      actions: '',
      http_url: '',
      slide: null,
      question,
    },
  }];
}

const slide = best.slide == null || best.slide === '' ? null : Number(best.slide);
const shouldFlip = Number.isFinite(slide) && slide > 0 && store.bridgeUrl;
const spoken = String(best.fact_yue || '');
return [{
  json: {
    ok: true,
    skip_http: !shouldFlip,
    decline: false,
    slide_changed: !!shouldFlip,
    spoken_text: spoken,
    spoken_grounding: spoken,
    spoken_text_en: best.fact_en || '',
    next_action: 'speak_then_call_deliver_next',
    instruction: 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
    auto_continue: true,
    card_id: best.card_id,
    topic: best.topic,
    slide: slide,
    actions: shouldFlip ? ('goto_slide:' + slide) : '',
    http_url: shouldFlip ? (store.bridgeUrl + '/run') : '',
    bridge_token: store.bridgeToken || '',
    question,
    bookmark: store.bookmark,
  },
}];
'''

LEGACY_MERGE_QA_JS = r'''const ask = $('Answer question').first().json;
let bridge = {};
try { bridge = $input.first().json || {}; } catch (e) { bridge = { error: String(e) }; }
const bridgeError = bridge.error || bridge.message || '';
return [{
  json: {
    ok: ask.ok !== false && !bridgeError,
    mode: 'qa',
    done: false,
    auto_continue: true,
    slide_changed: !!ask.slide_changed,
    spoken_text: ask.spoken_text || '',
    spoken_grounding: ask.spoken_grounding || ask.spoken_text || '',
    spoken_text_en: ask.spoken_text_en || '',
    next_action: ask.next_action || 'speak_then_call_deliver_next',
    instruction: ask.instruction || 'Speak spoken_text verbatim. Stop. Then call deliver_next. Do not recap or invite questions.',
    slide: (bridge.status && bridge.status.slide) || ask.slide || null,
    card_id: ask.card_id || '',
    bookmark: ask.bookmark,
    applied: bridge.applied || [],
    error: ask.error || bridgeError || '',
  },
}];
'''


def _set_run(paragraph, text: str, size: int, color: RGBColor, bold: bool = False) -> None:
    paragraph.clear()
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = FONT


def _fill(shape, color: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _textbox(slide, left, top, width, height, text: str, size: int, color: RGBColor, bold: bool = False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    _set_run(p, text, size, color, bold)
    return box


def _notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def _footer(slide, index: int, total: int) -> None:
    _textbox(
        slide,
        Inches(0.7),
        Inches(7.05),
        Inches(10.5),
        Inches(0.3),
        "Harbour AI  ·  2026 Q2 內部匯報  ·  資料截至 6 月 30 日",
        11,
        MUTED,
    )
    _textbox(
        slide,
        Inches(11.4),
        Inches(7.05),
        Inches(1.2),
        Inches(0.3),
        f"{index} / {total}",
        11,
        MUTED,
        align=PP_ALIGN.RIGHT,
    )


def _add_title_slide(prs: Presentation, spec: dict, index: int, total: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), Emu(0), prs.slide_width, prs.slide_height)
    _fill(bg, NAVY)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(2.35), Inches(2.2), Inches(0.08))
    _fill(accent, GOLD)
    _textbox(slide, Inches(0.7), Inches(1.5), Inches(12), Inches(0.5), spec.get("kicker") or "", 16, GOLD, bold=True)
    _textbox(slide, Inches(0.7), Inches(2.55), Inches(12), Inches(1.4), spec["title"], 54, WHITE, bold=True)
    _textbox(slide, Inches(0.7), Inches(4.2), Inches(12), Inches(1.0), spec.get("subtitle") or "", 24, CREAM)
    _notes(slide, spec.get("notes") or "")
    footer = _textbox(slide, Inches(0.7), Inches(7.05), Inches(10.5), Inches(0.3), "Harbour AI  ·  2026 Q2 內部匯報", 11, RGBColor(0xA8, 0xB8, 0xC0))
    _ = footer
    _textbox(slide, Inches(11.4), Inches(7.05), Inches(1.2), Inches(0.3), f"{index} / {total}", 11, RGBColor(0xA8, 0xB8, 0xC0), align=PP_ALIGN.RIGHT)


def _add_content_slide(prs: Presentation, spec: dict, index: int, total: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), Emu(0), prs.slide_width, prs.slide_height)
    _fill(bg, CREAM)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), Emu(0), prs.slide_width, Inches(1.35))
    _fill(bar, NAVY)
    gold = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), Inches(1.35), prs.slide_width, Inches(0.06))
    _fill(gold, GOLD)
    _textbox(slide, Inches(0.7), Inches(0.35), Inches(12), Inches(0.8), spec["title"], 28, WHITE, bold=True)
    box = slide.shapes.add_textbox(Inches(0.7), Inches(1.8), Inches(12), Inches(5.0))
    tf = box.text_frame
    tf.word_wrap = True
    bullets = spec.get("bullets") or []
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(14)
        _set_run(p, "•  " + line, 22, INK, bold=False)
    _notes(slide, spec.get("notes") or "")
    _footer(slide, index, total)


def write_sample_deck(path: Path | None = None) -> Path:
    path = Path(path or DECK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    total = len(SLIDES)
    for i, spec in enumerate(SLIDES, start=1):
        if spec.get("layout") == "title":
            _add_title_slide(prs, spec, i, total)
        else:
            _add_content_slide(prs, spec, i, total)
    prs.save(str(path))
    return path


def _style_header(ws, headers: list[str]) -> None:
    fill = PatternFill("solid", fgColor="1B3A4B")
    font = Font(name="Calibri", bold=True, color="FFFFFF")
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(1, col, name)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def _write_sheet(ws, rows: list[dict], headers: list[str], widths: dict[str, int]) -> None:
    wrap = Alignment(wrap_text=True, vertical="top")
    body = Font(name="Calibri", size=11)
    _style_header(ws, headers)
    for r, row in enumerate(rows, start=2):
        for c, key in enumerate(headers, start=1):
            value = row.get(key, "")
            if value is None:
                value = ""
            cell = ws.cell(r, c, value)
            cell.font = body
            cell.alignment = wrap
        ws.row_dimensions[r].height = 48
    for c, key in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(c)].width = widths.get(key, 18)
    ws.row_dimensions[1].height = 22


def write_script_xlsx(path: Path | None = None) -> Path:
    path = Path(path or SCRIPT_PATH)
    wb = Workbook()
    ws = wb.active
    ws.title = "script"
    headers = ["seq", "slide", "actions", "script_yue", "script_en", "notes"]
    _write_sheet(ws, SCRIPT, headers, {
        "seq": 8, "slide": 8, "actions": 16, "script_yue": 55, "script_en": 55, "notes": 28,
    })
    note = wb.create_sheet("readme")
    note["A1"] = "The agent reads every beat in order unless the audience interrupts. There is no ask-to-continue pause."
    note["A2"] = "seq and slide must match sample_talk.pptx. Regenerated by: python -m voice_app.sample_pack"
    note.column_dimensions["A"].width = 120
    wb.save(path)
    return path


def write_knowledge_xlsx(path: Path | None = None) -> Path:
    path = Path(path or KNOWLEDGE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "knowledge"
    headers = ["card_id", "slide", "topic", "keywords", "fact_yue", "fact_en"]
    rows = [dict(card) for card in KNOWLEDGE]
    _write_sheet(ws, rows, headers, {
        "card_id": 16, "slide": 10, "topic": 22, "keywords": 40, "fact_yue": 55, "fact_en": 55,
    })
    note = wb.create_sheet("readme")
    note["A1"] = "Empty slide = answer without flipping PowerPoint. A number = go to that 1-based slide when this card is used."
    note["A2"] = "Q&A uses these approved facts as retrieval evidence. Unsupported or failed retrieval returns a safe abstention."
    note.column_dimensions["A"].width = 120
    wb.save(path)
    return path


def write_n8n_beat_code() -> tuple[Path, Path]:
    beats_json = json.dumps(n8n_beats(), ensure_ascii=False, indent=2)
    js_path = N8N / "next-beat.js"
    js_path.write_text(NEXT_BEAT_JS.replace("/*BEATS*/", beats_json), encoding="utf-8")
    prepare_path = N8N / "prepare-question.js"
    validate_path = N8N / "validate-question.js"
    merge_path = N8N / "merge-result.js"
    merge_path.write_text(MERGE_JS, encoding="utf-8")
    merge_qa_path = N8N / "merge-question.js"
    workflow_path = N8N / "powerpoint-director.json"
    if workflow_path.exists():
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        _upsert_qa_workflow(
            workflow,
            js_path,
            prepare_path,
            validate_path,
            merge_qa_path,
        )
        workflow_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return js_path, workflow_path


def _node(workflow: dict, name: str) -> dict | None:
    for node in workflow["nodes"]:
        if node.get("name") == name:
            return node
    return None


def _upsert_qa_workflow(
    workflow: dict,
    beat_path: Path,
    prepare_path: Path,
    validate_path: Path,
    merge_qa_path: Path,
) -> None:
    reset_path = N8N / "reset-cursor.js"
    beat_js = beat_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    prepare_js = prepare_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    validate_js = validate_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    merge_qa_js = merge_qa_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if (node := _node(workflow, "Next beat")):
        node["parameters"]["jsCode"] = beat_js
    if (node := _node(workflow, "Merge result")):
        node["parameters"]["jsCode"] = MERGE_JS
    if (node := _node(workflow, "Reset cursor")) and reset_path.exists():
        node["parameters"]["jsCode"] = reset_path.read_text(encoding="utf-8").replace("\r\n", "\n")

    stub = (
        _node(workflow, "Prepare question")
        or _node(workflow, "Question stub")
        or _node(workflow, "Answer question")
    )
    if stub:
        stub["name"] = "Prepare question"
        stub["id"] = stub.get("id") or "code-prepare-question"
        stub["parameters"]["jsCode"] = prepare_js
        stub["position"] = [240, 560]

    names = {n["name"] for n in workflow["nodes"]}
    for if_name in ("Call PowerPoint?", "Flip for question?"):
        if_node = _node(workflow, if_name)
        conditions = (
            (if_node or {})
            .get("parameters", {})
            .get("conditions", {})
            .get("conditions", [])
        )
        for condition in conditions:
            operator = condition.get("operator") or {}
            if operator.get("type") == "boolean" and operator.get("operation") == "notEqual":
                operator["operation"] = "notEquals"

    talk_body = "={{ JSON.stringify({ actions: $json.actions, spoken_text: $json.spoken_text, seq: $json.seq, slide: $json.slide }) }}"
    qa_body = "={{ JSON.stringify({ actions: $json.actions, interrupt: true }) }}"
    http_talk = _node(workflow, "POST slide bridge")
    if http_talk:
        http_params = json.loads(json.dumps(http_talk["parameters"]))
        options = http_params.setdefault("options", {})
        options["timeout"] = 20000
        http_params["jsonBody"] = talk_body
    else:
        http_params = {
            "method": "POST",
            "url": "={{ $json.http_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $json.bridge_token }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": talk_body,
            "options": {"timeout": 20000, "response": {"response": {"neverError": True}}},
        }
    headers = http_params.setdefault("headerParameters", {}).setdefault("parameters", [])
    auth_header = next((item for item in headers if item.get("name") == "Authorization"), None)
    if auth_header:
        auth_header["value"] = "={{ 'Bearer ' + $json.bridge_token }}"
    else:
        headers.append({"name": "Authorization", "value": "={{ 'Bearer ' + $json.bridge_token }}"})
    if http_talk:
        http_talk["parameters"] = http_params
        http_talk["onError"] = "continueErrorOutput"
    agent_http_params = {
        "method": "POST",
        "url": "={{ $json.qa_url }}",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Authorization", "value": "={{ 'Bearer ' + $json.bridge_token }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": (
            "={{ JSON.stringify({ question: $json.question, current_slide: "
            "$json.current_slide, call_id: $json.call_id }) }}"
        ),
        "options": {
            "timeout": 28000,
            "response": {"response": {"neverError": True}},
        },
    }
    qa_http_params = json.loads(json.dumps(http_params))
    qa_http_params["jsonBody"] = qa_body
    qa_http_params.setdefault("options", {})["timeout"] = 20000
    if (qa_http := _node(workflow, "POST question slide")):
        qa_http["parameters"] = qa_http_params
        qa_http["onError"] = "continueErrorOutput"
    if_params = {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [
                {
                    "id": "do-http-qa",
                    "leftValue": "={{ $json.skip_http }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "notEquals"},
                }
            ],
            "combinator": "and",
        },
        "options": {},
    }
    extras = [
        {
            "parameters": agent_http_params,
            "id": "http-qa-agent",
            "name": "Call Q&A agent",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [470, 560],
            "onError": "continueErrorOutput",
        },
        {
            "parameters": {"jsCode": validate_js},
            "id": "code-validate-qa",
            "name": "Validate Q&A",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [700, 560],
        },
        {
            "parameters": if_params,
            "id": "if-qa-http",
            "name": "Flip for question?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [920, 560],
        },
        {
            "parameters": qa_http_params,
            "id": "http-qa",
            "name": "POST question slide",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1150, 480],
            "onError": "continueErrorOutput",
        },
        {
            "parameters": {"jsCode": merge_qa_js},
            "id": "code-merge-qa",
            "name": "Merge question",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1390, 560],
        },
    ]
    for extra in extras:
        existing = _node(workflow, extra["name"])
        if existing:
            existing.update(extra)
        else:
            workflow["nodes"].append(extra)

    workflow["connections"]["POST slide bridge"] = {
        "main": [
            [{"node": "Merge result", "type": "main", "index": 0}],
            [{"node": "Merge result", "type": "main", "index": 0}],
        ]
    }
    workflow["connections"]["Webhook handle-question"] = {
        "main": [[{"node": "Prepare question", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Prepare question"] = {
        "main": [[{"node": "Call Q&A agent", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Call Q&A agent"] = {
        "main": [
            [{"node": "Validate Q&A", "type": "main", "index": 0}],
            [{"node": "Validate Q&A", "type": "main", "index": 0}],
        ]
    }
    workflow["connections"]["Validate Q&A"] = {
        "main": [[{"node": "Flip for question?", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Flip for question?"] = {
        "main": [
            [{"node": "POST question slide", "type": "main", "index": 0}],
            [{"node": "Merge question", "type": "main", "index": 0}],
        ]
    }
    workflow["connections"]["POST question slide"] = {
        "main": [
            [{"node": "Merge question", "type": "main", "index": 0}],
            [{"node": "Merge question", "type": "main", "index": 0}],
        ]
    }
    workflow["connections"].pop("Question stub", None)
    workflow["connections"].pop("Answer question", None)



def write_all() -> dict[str, Path]:
    DATA.mkdir(parents=True, exist_ok=True)
    N8N.mkdir(parents=True, exist_ok=True)
    if len(SLIDES) != len(SCRIPT):
        raise SystemExit(f"Slide count {len(SLIDES)} != script beats {len(SCRIPT)}")
    for row in SCRIPT:
        if not 1 <= int(row["slide"]) <= len(SLIDES):
            raise SystemExit(f"Script seq {row['seq']} points at missing slide {row['slide']}")
    written = {}
    for key, fn in (("deck", write_sample_deck), ("script", write_script_xlsx), ("knowledge", write_knowledge_xlsx)):
        try:
            written[key] = fn()
        except PermissionError:
            print(f"Skip {key}: file is open in another program. Close it and re-run python -m voice_app.sample_pack")
    js_path, wf_path = write_n8n_beat_code()
    written["next_beat"] = js_path
    written["workflow"] = wf_path
    for stale in (DATA / "script.csv", DATA / "knowledge.csv", DATA / "knowledge.xlsx"):
        if stale.exists():
            stale.unlink()
            written[stale.name] = stale
    return written


def main() -> None:
    for label, path in write_all().items():
        print(f"{label}: {path}")
    print(f"{len(SLIDES)} slides, {len(SCRIPT)} beats, {len(KNOWLEDGE)} knowledge cards.")
    print(
        "Import n8n/powerpoint-director.json, configure Header Auth on its three "
        "webhooks, then Publish."
    )


if __name__ == "__main__":
    main()
