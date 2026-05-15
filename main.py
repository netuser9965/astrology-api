# -*- coding: utf-8 -*-
import os
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

API_KEY = os.getenv("ASTRO_API_KEY", "CHANGE_ME_TO_A_SECRET_KEY")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://astrology-api-l5tr.onrender.com"
)

PAYMENT_PAGE_URL = os.getenv(
    "PAYMENT_PAGE_URL",
    "https://astrology-api-l5tr.onrender.com/success"
)

OUTPUT_DIR = "generated_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Secure Astrology Report API")
app.mount("/reports", StaticFiles(directory=OUTPUT_DIR), name="reports")


class BirthInput(BaseModel):
    token: Optional[str] = None
    name: Optional[str] = None
    birth_date: str
    birth_time: str
    birth_place: str
    gender: Optional[str] = None
    timezone: Optional[str] = "Asia/Taipei"
    plan: Optional[str] = "free"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


def check_api_key(x_api_key: Optional[str]):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


def normalize_plan(plan: Optional[str]) -> str:
    if not plan:
        return "free"

    plan = plan.lower().strip()

    allowed = ["free", "starter", "standard", "deep"]

    if plan not in allowed:
        return "free"

    return plan


def get_plan_title(plan: str) -> str:
    titles = {
        "free": "免費星盤報告",
        "starter": "入門版財富命盤報告",
        "standard": "標準版財富命盤報告",
        "deep": "深度版財富命盤報告",
    }

    return titles.get(plan, "免費星盤報告")


def get_plan_content(plan: str, data: BirthInput):
    if plan == "free":
        return [
            ("一、基本命盤摘要",
             "這是一份免費版星盤摘要，提供你的出生資料、基本能量方向與初步財富傾向。若需要完整宮位、相位、財運、事業與年度策略，可升級完整報告。"),

            ("二、財富傾向",
             "你的財富模式需要從長期累積、專業能力與穩定規劃開始。免費版僅提供簡要方向，適合作為了解命盤的第一步。"),

            ("三、行動建議",
             "建議先建立穩定現金流、記錄收入支出、培養可長期變現的技能，避免衝動投資與短期情緒決策。"),
        ]

    if plan == "starter":
        return [
            ("一、個人財富定位",
             "你屬於需要透過專業能力與穩定累積來建立財富的類型。入門版著重於基本性格、收入模式與財務習慣分析。"),

            ("二、收入模式",
             "適合知識型服務、技術服務、內容產品、顧問服務、斜槓收入與穩定現金流累積。"),

            ("三、風險提醒",
             "需要避免短期衝動、過度相信單一機會，以及沒有風控就投入大量資金。"),
        ]

    if plan == "standard":
        return [
            ("一、財富定位",
             "你適合建立系統化財富模式，透過專業能力、資源整合、長期規劃與穩定收入逐步放大財務成果。"),

            ("二、事業與收入方向",
             "標準版建議你把重點放在可複製的服務、可持續累積的技能、可轉化為產品的知識，以及能帶來長期回報的資產配置。"),

            ("三、感情與合作對財務的影響",
             "合作、人脈與伴侶關係可能影響你的財務決策。需要建立清楚界線，避免因情緒、人情或短期誘惑而破壞財務節奏。"),

            ("四、風險與修正策略",
             "你需要建立風險上限、現金流安全墊，以及定期檢討機制。越能紀律化，越能穩定累積財富。"),
        ]

    return [
        ("一、深度財富定位",
         "你的人生財富主題不只是賺錢，而是如何把能力、資源、時間與選擇整合成長期系統。深度版強調人生課題、財務模式與長期策略。"),

        ("二、核心收入模式",
         "你適合發展專業型、顧問型、內容型、技術型或系統型收入。當你的能力能被產品化、流程化、規模化，財富成長速度會明顯提高。"),

        ("三、事業策略",
         "你的事業需要避免頻繁換方向。最有利的策略是選定一個可長期累積的主軸，持續優化產品、客戶、流程與信任感。"),

        ("四、財務風險",
         "需特別注意過度槓桿、短線衝動、追逐熱門機會，以及因壓力而做出錯誤決策。越能先建立安全邊界，越能承受更大的成長。"),

        ("五、年度行動建議",
         "建議建立三層架構：第一層是穩定現金流，第二層是技能與產品化，第三層是長期資產配置。這會讓你的財富不是靠運氣，而是靠系統累積。"),
    ]


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <meta charset="utf-8">
    <h1>AI 財富命盤 API 已上線</h1>
    <p><a href="/form">前往正式表單頁</a></p>
    <p><a href="/success">付款成功測試頁</a></p>
    <p><a href="/docs">API Docs</a></p>
    """


@app.get("/form", response_class=HTMLResponse)
def form_page():
    return f"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>AI 財富命盤報告生成器</title>
  <style>
    body {{
      font-family: Arial, "Noto Sans TC", sans-serif;
      background: #f5f6f8;
      margin: 0;
      padding: 40px 16px;
      color: #111;
    }}
    .wrap {{
      max-width: 760px;
      margin: auto;
      background: #fff;
      border-radius: 22px;
      padding: 32px;
      box-shadow: 0 8px 28px rgba(0,0,0,.08);
    }}
    h1 {{
      font-size: 32px;
      margin-bottom: 8px;
    }}
    .sub {{
      color: #555;
      margin-bottom: 28px;
      line-height: 1.7;
    }}
    label {{
      display: block;
      margin: 16px 0 6px;
      font-weight: 700;
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      padding: 13px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 16px;
    }}
    button {{
      margin-top: 24px;
      width: 100%;
      padding: 16px;
      background: #111;
      color: white;
      border: 0;
      border-radius: 12px;
      font-size: 18px;
      font-weight: 700;
      cursor: pointer;
    }}
    .result {{
      margin-top: 24px;
      padding: 18px;
      background: #f0f2f5;
      border-radius: 14px;
      line-height: 1.8;
      display: none;
    }}
  </style>
</head>

<body>
  <div class="wrap">
    <h1>AI 財富命盤報告生成器</h1>

    <div class="sub">
      輸入出生資料後，系統會保存資料並前往付款頁。<br>
      付款完成後會自動生成你的 PDF 財富命盤報告。
    </div>

    <label>姓名</label>
    <input id="name" placeholder="例如：王小明">

    <label>出生日期</label>
    <input id="birth_date" type="date">

    <label>出生時間</label>
    <input id="birth_time" type="time">

    <label>出生地點</label>
    <input id="birth_place" value="台北">

    <label>性別</label>
    <select id="gender">
      <option>男</option>
      <option>女</option>
      <option>其他</option>
    </select>

    <button onclick="goToPayment()">解鎖完整 PDF 報告</button>

    <div id="result" class="result"></div>
  </div>

<script>
function goToPayment() {{
  const resultBox = document.getElementById("result");

  const payload = {{
    name: document.getElementById("name").value,
    birth_date: document.getElementById("birth_date").value,
    birth_time: document.getElementById("birth_time").value,
    birth_place: document.getElementById("birth_place").value,
    gender: document.getElementById("gender").value,
    timezone: "Asia/Taipei",
    plan: "deep"
  }};

  if (!payload.birth_date || !payload.birth_time || !payload.birth_place) {{
    resultBox.style.display = "block";
    resultBox.innerHTML = "請填寫出生日期、時間與地點。";
    return;
  }}

  localStorage.setItem("astroData", JSON.stringify(payload));

  window.location.href = "{PAYMENT_PAGE_URL}";
}}
</script>

</body>
</html>
    """


@app.get("/success", response_class=HTMLResponse)
def success_page():
    return f"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>正在生成報告</title>
  <style>
    body {{
      font-family: Arial, "Noto Sans TC", sans-serif;
      background: #f5f6f8;
      padding: 40px 16px;
      color: #111;
    }}
    .wrap {{
      max-width: 720px;
      margin: auto;
      background: #fff;
      border-radius: 22px;
      padding: 32px;
      box-shadow: 0 8px 28px rgba(0,0,0,.08);
      text-align: center;
    }}
    .download {{
      display: inline-block;
      margin-top: 20px;
      background: #0f7b3f;
      color: white;
      padding: 14px 22px;
      border-radius: 10px;
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>

<body>
  <div class="wrap" id="box">
    <h1>付款成功</h1>
    <p>正在生成你的 PDF 報告，請稍候...</p>
  </div>

<script>
async function generatePDF() {{
  const box = document.getElementById("box");
  const data = JSON.parse(localStorage.getItem("astroData"));

  if (!data) {{
    box.innerHTML = "<h2>找不到出生資料</h2><p>請重新回到表單頁填寫。</p><p><a href='/form'>回表單頁</a></p>";
    return;
  }}

  data.token = "PAID_OK";

  const res = await fetch("/api/generate-report", {{
    method: "POST",
    headers: {{
      "Content-Type": "application/json",
      "X-API-Key": "{API_KEY}"
    }},
    body: JSON.stringify(data)
  }});

  const result = await res.json();

  if (!res.ok) {{
    box.innerHTML = "<h2>生成失敗</h2><p>" + JSON.stringify(result) + "</p>";
    return;
  }}

  box.innerHTML = `
    <h1>報告已生成成功</h1>
    <p>請點下方按鈕下載你的 PDF 報告。</p>
    <a class="download" href="${{result.download_url}}" target="_blank">下載 PDF 報告</a>
  `;
}}

generatePDF();
</script>

</body>
</html>
    """


@app.post("/api/generate-report")
def generate_report(data: BirthInput, x_api_key: Optional[str] = Header(None)):
    check_api_key(x_api_key)

    plan = normalize_plan(data.plan)

    if plan != "free":
        if not data.token or data.token != "PAID_OK":
            raise HTTPException(status_code=403, detail="請先完成付款")

    filename = f"wealth_report_{str(uuid.uuid4())[:8]}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    title = ParagraphStyle(
        "Title",
        fontName="STSong-Light",
        fontSize=20,
        leading=26,
    )

    header = ParagraphStyle(
        "Header",
        fontName="STSong-Light",
        fontSize=14,
        leading=20,
        spaceBefore=14,
        spaceAfter=8,
    )

    body = ParagraphStyle(
        "Body",
        fontName="STSong-Light",
        fontSize=11,
        leading=17,
        spaceAfter=8,
    )

    plan_title = get_plan_title(plan)
    plan_sections = get_plan_content(plan, data)

    content = [
        Paragraph(plan_title, title),
        Spacer(1, 20),

        Paragraph(f"姓名：{data.name or '未填'}", body),
        Paragraph(f"出生日期：{data.birth_date}", body),
        Paragraph(f"出生時間：{data.birth_time}", body),
        Paragraph(f"出生地點：{data.birth_place}", body),
        Paragraph(f"性別：{data.gender or '未填'}", body),
        Paragraph(f"時區：{data.timezone or '未填'}", body),
        Paragraph(f"報告方案：{plan}", body),
        Spacer(1, 20),
    ]

    if data.latitude is not None and data.longitude is not None:
        content.append(Paragraph(f"出生地經緯度：{data.latitude}, {data.longitude}", body))
        content.append(Spacer(1, 10))

    for section_title, section_text in plan_sections:
        content.append(Paragraph(section_title, header))
        content.append(Paragraph(section_text, body))

    content.extend([
        Spacer(1, 20),
        Paragraph(
            "免責聲明：本報告為占星與個人策略分析，僅供自我探索、娛樂與參考，不構成投資建議、法律建議、醫療建議或財務承諾。",
            body,
        ),
    ])

    doc.build(content)

    download_url = f"{BASE_URL}/reports/{filename}"

    return {
        "status": "success",
        "plan": plan,
        "download_url": download_url,
        "filename": filename,
    }
