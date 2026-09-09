// Legacy deterministic matcher retained for rollback/reference.
// The published RAG workflow uses prepare-question.js and validate-question.js.
const store = $getWorkflowStaticData('global');
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

const cards = [
  {
    "card_id": "k_founded",
    "slide": 3,
    "topic": "成立年份",
    "keywords": "成立,創辦,2019,幾時開,founded,when",
    "fact_yue": "Harbour AI 2019 年喺香港成立。呢頁就係公司一覽。",
    "fact_en": "Harbour AI was founded in Hong Kong in 2019. That is the company snapshot slide."
  },
  {
    "card_id": "k_company",
    "slide": 3,
    "topic": "員工人數同地點",
    "keywords": "員工,人數,86,香港,新加坡,倫敦,office,headcount",
    "fact_yue": "而家 86 人；辦公室喺香港、新加坡同倫敦。唔好講成過百人。",
    "fact_en": "Headcount is 86. Offices: Hong Kong, Singapore, London. Do not say 100+."
  },
  {
    "card_id": "k_appstore",
    "slide": null,
    "topic": "有冇消費級 App",
    "keywords": "App Store,消費,公眾,download,consumer,手機 App",
    "fact_yue": "Harbour AI 唔做消費級 App，亦都沒有公開 App Store 版計劃。呢條唔使翻頁。",
    "fact_en": "There is no consumer app and no public App Store plan. Do not change slides."
  },
  {
    "card_id": "k_product",
    "slide": 4,
    "topic": "Harbour Presenter 係乜",
    "keywords": "Presenter,產品,粵語,跟稿,n8n,簡報代理,product",
    "fact_yue": "Harbour Presenter 係粵語優先語音簡報代理，跟預先寫好嘅稿講，唔即場生稿。n8n 做導演，PowerPoint 跟住翻頁。呢頁就係產品頁。",
    "fact_en": "Harbour Presenter is a Cantonese-first voice presenter that reads a prepared script. n8n directs; PowerPoint follows. That is the product slide."
  },
  {
    "card_id": "k_adoption",
    "slide": 5,
    "topic": "採用數字",
    "keywords": "41,1280,客戶,座位,38%,試用,採用,seats,customers",
    "fact_yue": "截至 2026 年 6 月 30 日：41 間付費客戶、1,280 個活躍座位、今季淨新增 11 間、試用轉付費 38%。只計 Harbour Presenter。",
    "fact_en": "As of 30 June 2026: 41 paying customers, 1,280 active seats, 11 net new this quarter, 38% trial-to-paid. Harbour Presenter only."
  },
  {
    "card_id": "k_customer",
    "slide": 6,
    "topic": "客戶名稱",
    "keywords": "海港銀行,星航,維港零售,客戶,案例,誰在用,who",
    "fact_yue": "公開講得出名嘅三間：海港銀行（粵語業績會）、星航集團（新航線發佈）、維港零售（12 城店長大會）。合約金額唔公開。",
    "fact_en": "Named references: Harbour Bank, Starline Group, Victoria Retail. Contract values are not disclosed."
  },
  {
    "card_id": "k_finance",
    "slide": 7,
    "topic": "財務摘要",
    "keywords": "收入,財務,ARR,毛利,22%,現金,runway,revenue",
    "fact_yue": "2026 年第二季：產品年經常收入 1,860 萬港元，季增長 22%，毛利率 71%，現金跑道約 18 個月。呢頁就係財務摘要。",
    "fact_en": "Q2 2026: product ARR HK$18.6m, +22% QoQ, 71% gross margin, ~18 months cash runway. That is the finance slide."
  },
  {
    "card_id": "k_arr",
    "slide": 7,
    "topic": "貨幣單位",
    "keywords": "美元,美金,USD,港幣,HKD,million,1860",
    "fact_yue": "1,860 萬係港元，唔係美元。唔好講成 US$18.6 million。",
    "fact_en": "HK$18.6 million, not US$18.6 million."
  },
  {
    "card_id": "k_roadmap",
    "slide": 8,
    "topic": "路線圖",
    "keywords": "路線圖,時間表,第三季,第四季,2027,roadmap,SSO,Azure",
    "fact_yue": "2026 第三季：SSO 同審計日誌。第四季：Azure 知識庫問答翻頁。2027 第一季：粵語／英語即場切換。沒有 App Store 版。",
    "fact_en": "Q3 2026 SSO and audit logs. Q4 Azure KB Q&A with slide jumps. Q1 2027 live language switch. No App Store edition."
  },
  {
    "card_id": "k_sso",
    "slide": 8,
    "topic": "單點登錄幾時有",
    "keywords": "SSO,單點登錄,登錄, entraid,okta,審計",
    "fact_yue": "企業單點登錄同審計日誌排喺 2026 年第三季，唔係而家已經有。",
    "fact_en": "Enterprise SSO and audit logs are scheduled for Q3 2026, not available now."
  },
  {
    "card_id": "k_risk",
    "slide": 9,
    "topic": "風險同請求",
    "keywords": "風險,域名,工程師,隧道,IT,support,risk",
    "fact_yue": "需要 IT 批穩定域名，同埋兩名方案工程師。試用隧道網址唔穩定。呢頁就係風險頁。",
    "fact_en": "Asks: a stable domain from IT, and two solutions engineers. Trial tunnels are unstable."
  },
  {
    "card_id": "k_error_rate",
    "slide": 9,
    "topic": "語音識別錯字",
    "keywords": "7%,錯字,嘈雜,識別,WER,accuracy,聽錯",
    "fact_yue": "嘈雜會議室入面，粵語識別大約仲有 7% 錯字。唔好講成已經完美。",
    "fact_en": "Cantonese recognition in noisy rooms still has about 7% character error. Do not claim it is perfect."
  },
  {
    "card_id": "k_team",
    "slide": 10,
    "topic": "團隊編制",
    "keywords": "團隊,51,14,請人,倫敦,9月,hiring,headcount",
    "fact_yue": "產品同工程 51 人，客戶成功 14 人；請緊語音質素同現場實施。倫敦辦公室 2026 年 9 月遷址，唔影響今季交付。",
    "fact_en": "51 product/engineering, 14 customer success. Hiring speech quality and on-site implementation. London office moves September 2026."
  },
  {
    "card_id": "k_next",
    "slide": 11,
    "topic": "未來 30 日",
    "keywords": "30日,下一步,董事會,8月28,試點,SSO範圍,next",
    "fact_yue": "未來 30 日：三間銀行試點設計、凍結第三季 SSO 範圍、8 月 28 日董事會覆核、下週發會議紀錄同投影片。",
    "fact_en": "Next 30 days: three bank pilots, freeze Q3 SSO scope, board review 28 August, send minutes and slides next week."
  },
  {
    "card_id": "k_asof",
    "slide": null,
    "topic": "數字截止日期",
    "keywords": "截至,幾時嘅數,as of,6月,cutoff",
    "fact_yue": "匯報入面嘅採用同財務數字，一律截至 2026 年 6 月 30 日。呢條唔使翻頁。",
    "fact_en": "Adoption and finance figures are as of 30 June 2026. Do not change slides."
  }
];
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
