"""Single source of truth for the sample deck, script.xlsx, knowledge cards, and n8n beats."""

from __future__ import annotations

# Widescreen 16:9. Titles and bullets on each slide must match script_yue and knowledge facts.

SLIDES: list[dict] = [
    {
        "layout": "title",
        "title": "Harbour AI",
        "subtitle": "2026 年第二季業務匯報",
        "kicker": "語音簡報產品  ·  香港總部  ·  內部會議",
        "notes": "Title. After consent, speak beat 1. Auto-continue to agenda.",
    },
    {
        "layout": "content",
        "title": "今日議程",
        "bullets": [
            "公司一覽",
            "產品：Harbour Presenter",
            "採用數據（截至 2026 年 6 月）",
            "客戶案例",
            "財務摘要",
            "2026 下半年路線圖、風險、團隊、下一步",
        ],
        "notes": "Agenda. Auto-continue to company snapshot.",
    },
    {
        "layout": "content",
        "title": "公司一覽",
        "bullets": [
            "2019 年喺香港成立",
            "員工 86 人：香港、新加坡、倫敦",
            "主打企業語音工作流程，唔做消費級 App",
            "今季重點產品：Harbour Presenter",
        ],
        "notes": "Company. Knowledge k_company, k_founded, k_appstore.",
    },
    {
        "layout": "content",
        "title": "產品：Harbour Presenter",
        "bullets": [
            "粵語優先嘅語音簡報代理",
            "跟預先寫好嘅稿講，唔會即場生稿",
            "n8n 做導演，桌面 PowerPoint 跟住翻頁",
            "觀眾打斷之後，可以跳去相關一頁再接返",
        ],
        "notes": "Product. Knowledge k_product.",
    },
    {
        "layout": "content",
        "title": "採用數據（截至 2026 年 6 月 30 日）",
        "bullets": [
            "付費客戶 41 間",
            "活躍座位 1,280 個",
            "今季淨新增 11 間客戶",
            "試用轉付費 38%",
            "以上只計 Harbour Presenter，唔計舊語音客服線",
        ],
        "notes": "Adoption. Knowledge k_adoption. Auto-continue to customers.",
    },
    {
        "layout": "content",
        "title": "客戶案例",
        "bullets": [
            "海港銀行：粵語季度業績會",
            "星航集團：新航線發佈會",
            "維港零售：12 個城市店長大會同步",
            "合約金額唔公開",
        ],
        "notes": "Customers. Knowledge k_customer.",
    },
    {
        "layout": "content",
        "title": "財務摘要（2026 年第二季）",
        "bullets": [
            "產品年經常收入 1,860 萬港元（港幣，唔係美元）",
            "較上一季增長 22%",
            "毛利率 71%",
            "現金跑道約 18 個月",
            "內部數字，截至 6 月 30 日",
        ],
        "notes": "Finance. Knowledge k_finance, k_arr.",
    },
    {
        "layout": "content",
        "title": "2026 下半年路線圖",
        "bullets": [
            "第三季：企業單點登錄（SSO）同審計日誌",
            "第四季：知識庫問答翻頁（Azure OpenAI）",
            "2027 年第一季：廣東話同英語即場切換",
            "沒有公開 App Store 版計劃",
        ],
        "notes": "Roadmap. Knowledge k_roadmap, k_sso. Auto-continue.",
    },
    {
        "layout": "content",
        "title": "風險同需要嘅支持",
        "bullets": [
            "嘈雜會議室粵語識別仍有約 7% 錯字",
            "試用隧道每次重開，網址都會變",
            "需要 IT 批出穩定域名",
            "需要再加兩名方案工程師",
        ],
        "notes": "Risks. Knowledge k_risk, k_error_rate.",
    },
    {
        "layout": "content",
        "title": "團隊",
        "bullets": [
            "產品同工程 51 人",
            "客戶成功 14 人",
            "而家請緊：語音質素、現場實施",
            "倫敦辦公室計劃 2026 年 9 月遷入新址",
        ],
        "notes": "Team. Knowledge k_team.",
    },
    {
        "layout": "content",
        "title": "下一步（未來 30 日）",
        "bullets": [
            "完成三間銀行試點設計",
            "凍結第三季 SSO 範圍",
            "8 月 28 日董事會覆核",
            "下週發送會議紀錄同投影片",
        ],
        "notes": "Next 30 days. Knowledge k_next.",
    },
    {
        "layout": "title",
        "title": "多謝各位",
        "subtitle": "資料截至 2026 年 6 月 30 日",
        "kicker": "內部用途",
        "notes": "Close. Last beat; do not auto-continue.",
    },
]

SCRIPT: list[dict] = [
    {
        "seq": 1,
        "slide": 1,
        "actions": "goto_slide:1",
        "script_yue": "各位早晨，歡迎出席 Harbour AI 2026 年第二季業務匯報。今日會講公司現況、Harbour Presenter 產品、採用數據、客戶、財務，同埋下半年路線圖。",
        "script_en": "Good morning. Welcome to Harbour AI's Q2 2026 business review. We will cover the company, Harbour Presenter, adoption, customers, finance, and the second-half roadmap.",
        "notes": "After audience consent. Auto-continue.",
    },
    {
        "seq": 2,
        "slide": 2,
        "actions": "goto_slide:2",
        "script_yue": "呢頁係今日議程。我會先講公司同產品，之後睇採用數字、客戶案例、財務，同埋下半年路線圖。",
        "script_en": "This is the agenda. Company and product first, then adoption, customers, finance, and the second-half roadmap.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 3,
        "slide": 3,
        "actions": "goto_slide:3",
        "script_yue": "Harbour AI 2019 年喺香港成立，而家 86 人，辦公室喺香港、新加坡同倫敦。我哋做企業語音工作流程，唔做消費級 App。今季主打產品係 Harbour Presenter。",
        "script_en": "Harbour AI was founded in Hong Kong in 2019. We have 86 people in Hong Kong, Singapore, and London. We build enterprise voice workflows, not a consumer app. This quarter's product is Harbour Presenter.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 4,
        "slide": 4,
        "actions": "goto_slide:4",
        "script_yue": "Harbour Presenter 係粵語優先嘅語音簡報代理。佢跟預先寫好嘅稿講，唔會即場生稿。n8n 負責節奏，桌面 PowerPoint 跟住翻頁。觀眾一打斷，可以跳去相關一頁再接返。",
        "script_en": "Harbour Presenter is a Cantonese-first voice presenter. It reads a prepared script; it does not invent the talk. n8n directs pacing; desktop PowerPoint follows. After an interruption it can jump to the matching slide and resume.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 5,
        "slide": 5,
        "actions": "goto_slide:5",
        "script_yue": "截至 2026 年 6 月 30 日，Harbour Presenter 有 41 間付費客戶、1,280 個活躍座位。今季淨新增 11 間，試用轉付費 38%。呢啲數唔包括舊嘅語音客服線。",
        "script_en": "As of 30 June 2026, Harbour Presenter has 41 paying customers and 1,280 active seats. Net new this quarter: 11. Trial-to-paid: 38%. These figures exclude the legacy voice-support line.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 6,
        "slide": 6,
        "actions": "goto_slide:6",
        "script_yue": "三個代表客戶。海港銀行用嚟開粵語季度業績會；星航集團用嚟做新航線發佈會；維港零售喺 12 個城市嘅店長大會同步用呢套。合約金額我哋唔公開。",
        "script_en": "Three named customers: Harbour Bank for Cantonese quarterly results, Starline Group for route launches, and Victoria Retail for a 12-city store-manager meeting. Contract values are not disclosed.",
        "notes": "Auto-continue to finance.",
    },
    {
        "seq": 7,
        "slide": 7,
        "actions": "goto_slide:7",
        "script_yue": "第二季產品年經常收入係 1,860 萬港元，係港幣唔係美元，較上一季升 22%，毛利率 71%，現金跑道大約 18 個月。",
        "script_en": "Q2 product ARR is HK$18.6 million, not US dollars, up 22% quarter on quarter. Gross margin 71%. Cash runway about 18 months.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 8,
        "slide": 8,
        "actions": "goto_slide:8",
        "script_yue": "路線圖方面：2026 年第三季出企業單點登錄同審計日誌；第四季接 Azure 知識庫，觀眾提問可以翻頁；2027 年第一季先做廣東話同英語即場切換。我哋沒有公開 App Store 版計劃。",
        "script_en": "Roadmap: Q3 2026 enterprise SSO and audit logs; Q4 Azure knowledge-base Q&A with slide jumps; Cantonese/English live switch in Q1 2027. There is no public App Store plan.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 9,
        "slide": 9,
        "actions": "goto_slide:9",
        "script_yue": "兩個主要風險。嘈雜會議室入面，粵語識別大約仲有 7% 錯字。另外試用隧道每次重開網址都會變，所以我哋需要 IT 批一個穩定域名，同埋再加兩名方案工程師。",
        "script_en": "Two risks: about 7% character error for Cantonese in noisy rooms, and ephemeral tunnel hostnames. We need IT to approve a stable domain and two more solutions engineers.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 10,
        "slide": 10,
        "actions": "goto_slide:10",
        "script_yue": "團隊方面，產品同工程 51 人，客戶成功 14 人。而家請緊語音質素同現場實施。倫敦辦公室計劃 2026 年 9 月遷入新址，唔影響今季交付。",
        "script_en": "Headcount: 51 in product and engineering, 14 in customer success. We are hiring for speech quality and on-site implementation. The London office moves in September 2026; it does not affect this quarter's delivery.",
        "notes": "Auto-continue.",
    },
    {
        "seq": 11,
        "slide": 11,
        "actions": "goto_slide:11",
        "script_yue": "未來 30 日有四件事：完成三間銀行試點設計、凍結第三季 SSO 範圍、8 月 28 日董事會覆核，同埋下週發送會議紀錄同投影片。",
        "script_en": "Next 30 days: finish three bank pilot designs, freeze the Q3 SSO scope, board review on 28 August, and send minutes and slides next week.",
        "notes": "Auto-continue to close.",
    },
    {
        "seq": 12,
        "slide": 12,
        "actions": "goto_slide:12",
        "script_yue": "多謝各位。資料截至 2026 年 6 月 30 日，只供內部使用。",
        "script_en": "Thank you. Figures are as of 30 June 2026 and are internal only.",
        "notes": "Last beat. done after this; do not auto-continue.",
    },
]

KNOWLEDGE: list[dict] = [
    {
        "card_id": "k_founded",
        "slide": 3,
        "topic": "成立年份",
        "keywords": "成立,創辦,2019,幾時開,founded,when",
        "fact_yue": "Harbour AI 2019 年喺香港成立。呢頁就係公司一覽。",
        "fact_en": "Harbour AI was founded in Hong Kong in 2019. That is the company snapshot slide.",
    },
    {
        "card_id": "k_company",
        "slide": 3,
        "topic": "員工人數同地點",
        "keywords": "員工,人數,86,香港,新加坡,倫敦,office,headcount",
        "fact_yue": "而家 86 人；辦公室喺香港、新加坡同倫敦。唔好講成過百人。",
        "fact_en": "Headcount is 86. Offices: Hong Kong, Singapore, London. Do not say 100+.",
    },
    {
        "card_id": "k_appstore",
        "slide": "",
        "topic": "有冇消費級 App",
        "keywords": "App Store,消費,公眾,download,consumer,手機 App",
        "fact_yue": "Harbour AI 唔做消費級 App，亦都沒有公開 App Store 版計劃。呢條唔使翻頁。",
        "fact_en": "There is no consumer app and no public App Store plan. Do not change slides.",
    },
    {
        "card_id": "k_product",
        "slide": 4,
        "topic": "Harbour Presenter 係乜",
        "keywords": "Presenter,產品,粵語,跟稿,n8n,簡報代理,product",
        "fact_yue": "Harbour Presenter 係粵語優先語音簡報代理，跟預先寫好嘅稿講，唔即場生稿。n8n 做導演，PowerPoint 跟住翻頁。呢頁就係產品頁。",
        "fact_en": "Harbour Presenter is a Cantonese-first voice presenter that reads a prepared script. n8n directs; PowerPoint follows. That is the product slide.",
    },
    {
        "card_id": "k_adoption",
        "slide": 5,
        "topic": "採用數字",
        "keywords": "41,1280,客戶,座位,38%,試用,採用,seats,customers",
        "fact_yue": "截至 2026 年 6 月 30 日：41 間付費客戶、1,280 個活躍座位、今季淨新增 11 間、試用轉付費 38%。只計 Harbour Presenter。",
        "fact_en": "As of 30 June 2026: 41 paying customers, 1,280 active seats, 11 net new this quarter, 38% trial-to-paid. Harbour Presenter only.",
    },
    {
        "card_id": "k_customer",
        "slide": 6,
        "topic": "客戶名稱",
        "keywords": "海港銀行,星航,維港零售,客戶,案例,誰在用,who",
        "fact_yue": "公開講得出名嘅三間：海港銀行（粵語業績會）、星航集團（新航線發佈）、維港零售（12 城店長大會）。合約金額唔公開。",
        "fact_en": "Named references: Harbour Bank, Starline Group, Victoria Retail. Contract values are not disclosed.",
    },
    {
        "card_id": "k_finance",
        "slide": 7,
        "topic": "財務摘要",
        "keywords": "收入,財務,ARR,毛利,22%,現金,runway,revenue",
        "fact_yue": "2026 年第二季：產品年經常收入 1,860 萬港元，季增長 22%，毛利率 71%，現金跑道約 18 個月。呢頁就係財務摘要。",
        "fact_en": "Q2 2026: product ARR HK$18.6m, +22% QoQ, 71% gross margin, ~18 months cash runway. That is the finance slide.",
    },
    {
        "card_id": "k_arr",
        "slide": 7,
        "topic": "貨幣單位",
        "keywords": "美元,美金,USD,港幣,HKD,million,1860",
        "fact_yue": "1,860 萬係港元，唔係美元。唔好講成 US$18.6 million。",
        "fact_en": "HK$18.6 million, not US$18.6 million.",
    },
    {
        "card_id": "k_roadmap",
        "slide": 8,
        "topic": "路線圖",
        "keywords": "路線圖,時間表,第三季,第四季,2027,roadmap,SSO,Azure",
        "fact_yue": "2026 第三季：SSO 同審計日誌。第四季：Azure 知識庫問答翻頁。2027 第一季：粵語／英語即場切換。沒有 App Store 版。",
        "fact_en": "Q3 2026 SSO and audit logs. Q4 Azure KB Q&A with slide jumps. Q1 2027 live language switch. No App Store edition.",
    },
    {
        "card_id": "k_sso",
        "slide": 8,
        "topic": "單點登錄幾時有",
        "keywords": "SSO,單點登錄,登錄, entraid,okta,審計",
        "fact_yue": "企業單點登錄同審計日誌排喺 2026 年第三季，唔係而家已經有。",
        "fact_en": "Enterprise SSO and audit logs are scheduled for Q3 2026, not available now.",
    },
    {
        "card_id": "k_risk",
        "slide": 9,
        "topic": "風險同請求",
        "keywords": "風險,域名,工程師,隧道,IT,support,risk",
        "fact_yue": "需要 IT 批穩定域名，同埋兩名方案工程師。試用隧道網址唔穩定。呢頁就係風險頁。",
        "fact_en": "Asks: a stable domain from IT, and two solutions engineers. Trial tunnels are unstable.",
    },
    {
        "card_id": "k_error_rate",
        "slide": 9,
        "topic": "語音識別錯字",
        "keywords": "7%,錯字,嘈雜,識別,WER,accuracy,聽錯",
        "fact_yue": "嘈雜會議室入面，粵語識別大約仲有 7% 錯字。唔好講成已經完美。",
        "fact_en": "Cantonese recognition in noisy rooms still has about 7% character error. Do not claim it is perfect.",
    },
    {
        "card_id": "k_team",
        "slide": 10,
        "topic": "團隊編制",
        "keywords": "團隊,51,14,請人,倫敦,9月,hiring,headcount",
        "fact_yue": "產品同工程 51 人，客戶成功 14 人；請緊語音質素同現場實施。倫敦辦公室 2026 年 9 月遷址，唔影響今季交付。",
        "fact_en": "51 product/engineering, 14 customer success. Hiring speech quality and on-site implementation. London office moves September 2026.",
    },
    {
        "card_id": "k_next",
        "slide": 11,
        "topic": "未來 30 日",
        "keywords": "30日,下一步,董事會,8月28,試點,SSO範圍,next",
        "fact_yue": "未來 30 日：三間銀行試點設計、凍結第三季 SSO 範圍、8 月 28 日董事會覆核、下週發會議紀錄同投影片。",
        "fact_en": "Next 30 days: three bank pilots, freeze Q3 SSO scope, board review 28 August, send minutes and slides next week.",
    },
    {
        "card_id": "k_asof",
        "slide": "",
        "topic": "數字截止日期",
        "keywords": "截至,幾時嘅數,as of,6月,cutoff",
        "fact_yue": "匯報入面嘅採用同財務數字，一律截至 2026 年 6 月 30 日。呢條唔使翻頁。",
        "fact_en": "Adoption and finance figures are as of 30 June 2026. Do not change slides.",
    },
]


def n8n_knowledge() -> list[dict]:
    cards = []
    for row in KNOWLEDGE:
        slide = row.get("slide")
        if slide == "" or slide is None:
            slide = None
        else:
            slide = int(slide)
        cards.append(
            {
                "card_id": row["card_id"],
                "slide": slide,
                "topic": row["topic"],
                "keywords": row["keywords"],
                "fact_yue": row["fact_yue"],
                "fact_en": row["fact_en"],
            }
        )
    return cards


def n8n_beats() -> list[dict]:
    return [
        {
            "seq": row["seq"],
            "slide": row["slide"],
            "actions": row["actions"],
            "script_yue": row["script_yue"],
            "script_en": row["script_en"],
        }
        for row in SCRIPT
    ]
