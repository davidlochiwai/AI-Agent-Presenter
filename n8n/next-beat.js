const store = $getWorkflowStaticData('global');
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

const beats = [
  {
    "seq": 1,
    "slide": 1,
    "actions": "goto_slide:1",
    "script_yue": "各位早晨，歡迎出席 Harbour AI 2026 年第二季業務匯報。今日會講公司現況、Harbour Presenter 產品、採用數據、客戶、財務，同埋下半年路線圖。",
    "script_en": "Good morning. Welcome to Harbour AI's Q2 2026 business review. We will cover the company, Harbour Presenter, adoption, customers, finance, and the second-half roadmap."
  },
  {
    "seq": 2,
    "slide": 2,
    "actions": "goto_slide:2",
    "script_yue": "呢頁係今日議程。我會先講公司同產品，之後睇採用數字、客戶案例、財務，同埋下半年路線圖。",
    "script_en": "This is the agenda. Company and product first, then adoption, customers, finance, and the second-half roadmap."
  },
  {
    "seq": 3,
    "slide": 3,
    "actions": "goto_slide:3",
    "script_yue": "Harbour AI 2019 年喺香港成立，而家 86 人，辦公室喺香港、新加坡同倫敦。我哋做企業語音工作流程，唔做消費級 App。今季主打產品係 Harbour Presenter。",
    "script_en": "Harbour AI was founded in Hong Kong in 2019. We have 86 people in Hong Kong, Singapore, and London. We build enterprise voice workflows, not a consumer app. This quarter's product is Harbour Presenter."
  },
  {
    "seq": 4,
    "slide": 4,
    "actions": "goto_slide:4",
    "script_yue": "Harbour Presenter 係粵語優先嘅語音簡報代理。佢跟預先寫好嘅稿講，唔會即場生稿。n8n 負責節奏，桌面 PowerPoint 跟住翻頁。觀眾一打斷，可以跳去相關一頁再接返。",
    "script_en": "Harbour Presenter is a Cantonese-first voice presenter. It reads a prepared script; it does not invent the talk. n8n directs pacing; desktop PowerPoint follows. After an interruption it can jump to the matching slide and resume."
  },
  {
    "seq": 5,
    "slide": 5,
    "actions": "goto_slide:5",
    "script_yue": "截至 2026 年 6 月 30 日，Harbour Presenter 有 41 間付費客戶、1,280 個活躍座位。今季淨新增 11 間，試用轉付費 38%。呢啲數唔包括舊嘅語音客服線。",
    "script_en": "As of 30 June 2026, Harbour Presenter has 41 paying customers and 1,280 active seats. Net new this quarter: 11. Trial-to-paid: 38%. These figures exclude the legacy voice-support line."
  },
  {
    "seq": 6,
    "slide": 6,
    "actions": "goto_slide:6",
    "script_yue": "三個代表客戶。海港銀行用嚟開粵語季度業績會；星航集團用嚟做新航線發佈會；維港零售喺 12 個城市嘅店長大會同步用呢套。合約金額我哋唔公開。",
    "script_en": "Three named customers: Harbour Bank for Cantonese quarterly results, Starline Group for route launches, and Victoria Retail for a 12-city store-manager meeting. Contract values are not disclosed."
  },
  {
    "seq": 7,
    "slide": 7,
    "actions": "goto_slide:7",
    "script_yue": "第二季產品年經常收入係 1,860 萬港元，係港幣唔係美元，較上一季升 22%，毛利率 71%，現金跑道大約 18 個月。",
    "script_en": "Q2 product ARR is HK$18.6 million, not US dollars, up 22% quarter on quarter. Gross margin 71%. Cash runway about 18 months."
  },
  {
    "seq": 8,
    "slide": 8,
    "actions": "goto_slide:8",
    "script_yue": "路線圖方面：2026 年第三季出企業單點登錄同審計日誌；第四季接 Azure 知識庫，觀眾提問可以翻頁；2027 年第一季先做廣東話同英語即場切換。我哋沒有公開 App Store 版計劃。",
    "script_en": "Roadmap: Q3 2026 enterprise SSO and audit logs; Q4 Azure knowledge-base Q&A with slide jumps; Cantonese/English live switch in Q1 2027. There is no public App Store plan."
  },
  {
    "seq": 9,
    "slide": 9,
    "actions": "goto_slide:9",
    "script_yue": "兩個主要風險。嘈雜會議室入面，粵語識別大約仲有 7% 錯字。另外試用隧道每次重開網址都會變，所以我哋需要 IT 批一個穩定域名，同埋再加兩名方案工程師。",
    "script_en": "Two risks: about 7% character error for Cantonese in noisy rooms, and ephemeral tunnel hostnames. We need IT to approve a stable domain and two more solutions engineers."
  },
  {
    "seq": 10,
    "slide": 10,
    "actions": "goto_slide:10",
    "script_yue": "團隊方面，產品同工程 51 人，客戶成功 14 人。而家請緊語音質素同現場實施。倫敦辦公室計劃 2026 年 9 月遷入新址，唔影響今季交付。",
    "script_en": "Headcount: 51 in product and engineering, 14 in customer success. We are hiring for speech quality and on-site implementation. The London office moves in September 2026; it does not affect this quarter's delivery."
  },
  {
    "seq": 11,
    "slide": 11,
    "actions": "goto_slide:11",
    "script_yue": "未來 30 日有四件事：完成三間銀行試點設計、凍結第三季 SSO 範圍、8 月 28 日董事會覆核，同埋下週發送會議紀錄同投影片。",
    "script_en": "Next 30 days: finish three bank pilot designs, freeze the Q3 SSO scope, board review on 28 August, and send minutes and slides next week."
  },
  {
    "seq": 12,
    "slide": 12,
    "actions": "goto_slide:12",
    "script_yue": "多謝各位。資料截至 2026 年 6 月 30 日，只供內部使用。",
    "script_en": "Thank you. Figures are as of 30 June 2026 and are internal only."
  }
];
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
