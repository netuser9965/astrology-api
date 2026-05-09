
# -*- coding: utf-8 -*-
import os, uuid
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
OUTPUT_DIR = "generated_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Secure Astrology Report API")
app.mount("/reports", StaticFiles(directory=OUTPUT_DIR), name="reports")

class BirthInput(BaseModel):token: Optional[str] = None
    name: Optional[str] = None
    birth_date: str
    birth_time: str
    birth_place: str
    gender: Optional[str] = None
    timezone: Optional[str] = "Asia/Taipei"

def check_api_key(x_api_key: Optional[str]):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

@app.get("/", response_class=HTMLResponse)
def home():
    return '<meta charset="utf-8"><h1>AI 財富命盤 API 已上線</h1><p><a href="/form">前往正式表單頁</a></p><p><a href="/docs">API Docs</a></p>'

@app.get("/form", response_class=HTMLResponse)
def form_page():
    html = """
<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>AI 財富命盤報告生成器</title>
<style>
body{font-family:Arial,"Noto Sans TC",sans-serif;background:#f5f6f8;margin:0;padding:40px 16px;color:#111}
.wrap{max-width:760px;margin:auto;background:#fff;border-radius:22px;padding:32px;box-shadow:0 8px 28px rgba(0,0,0,.08)}
h1{font-size:32px;margin-bottom:8px}.sub{color:#555;margin-bottom:28px;line-height:1.7}
label{display:block;margin:16px 0 6px;font-weight:700}
input,select{width:100%;box-sizing:border-box;padding:13px;border:1px solid #ccc;border-radius:10px;font-size:16px}
button{margin-top:24px;width:100%;padding:16px;background:#111;color:white;border:0;border-radius:12px;font-size:18px;font-weight:700;cursor:pointer}
.result{margin-top:24px;padding:18px;background:#f0f2f5;border-radius:14px;line-height:1.8}
.download{display:inline-block;margin-top:12px;background:#0f7b3f;color:white;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:700}
.note{margin-top:20px;color:#777;font-size:14px;line-height:1.6}
</style></head>
<body><div class="wrap">
<h1>AI 財富命盤報告生成器</h1>
<div class="sub">輸入出生資料後，系統會自動生成你的個人財富命盤 PDF 報告。<br>報告包含財富定位、收入模式、風險提醒與行動建議。</div>
<label>姓名</label><input id="name" placeholder="例如：王小明">
<label>出生日期</label><input id="birth_date" type="date">
<label>出生時間</label><input id="birth_time" type="time">
<label>出生地點</label><input id="birth_place" value="台北">
<label>性別</label><select id="gender"><option>男</option><option>女</option><option>其他</option></select>
<button onclick="generateReport()">生成 PDF 報告</button>
<div id="result" class="result" style="display:none;"></div>
<div class="note">目前為測試版：正式收費版會改成「付款成功後才生成完整 PDF」。</div>
</div>
<script>
async function generateReport(){
  const resultBox = document.getElementById("result");
  resultBox.style.display = "block";
  resultBox.innerHTML = "正在生成報告，請稍候...";
  const payload = {
    name: document.getElementById("name").value,
    birth_date: document.getElementById("birth_date").value,
    birth_time: document.getElementById("birth_time").value,
    birth_place: document.getElementById("birth_place").value,
    gender: document.getElementById("gender").value,
    timezone: "Asia/Taipei"
  };
  if (!payload.birth_date || !payload.birth_time || !payload.birth_place) {
    resultBox.innerHTML = "請填寫出生日期、時間與地點。"; return;
  }
  const res = await fetch("/api/generate-report", {
    method: "POST",
    headers: {"Content-Type":"application/json","X-API-Key":"__API_KEY__"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) { resultBox.innerHTML = "生成失敗：" + JSON.stringify(data); return; }
  resultBox.innerHTML = `<b>報告已生成成功！</b><br><a class="download" href="${data.download_url}" target="_blank">下載 PDF 報告</a>`;
}
</script></body></html>
"""
    return html.replace("__API_KEY__", API_KEY)

@app.post("/api/generate-report")
def generate_report(data: BirthInput, x_api_key: Optional[str] = Header(None)):
    check_api_key(x_api_key)
    filename = f"wealth_report_{str(uuid.uuid4())[:8]}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    title = ParagraphStyle("Title", fontName="STSong-Light", fontSize=20, leading=26)
    h = ParagraphStyle("Header", fontName="STSong-Light", fontSize=14, leading=20)
    body = ParagraphStyle("Body", fontName="STSong-Light", fontSize=11, leading=17)
    content = [
        Paragraph("個人財富命盤 AI 深度報告", title), Spacer(1, 20),
        Paragraph(f"姓名：{data.name or '未填'}", body),
        Paragraph(f"出生日期：{data.birth_date}", body),
        Paragraph(f"出生時間：{data.birth_time}", body),
        Paragraph(f"出生地點：{data.birth_place}", body),
        Paragraph(f"性別：{data.gender or '未填'}", body), Spacer(1, 20),
        Paragraph("一、財富定位", h),
        Paragraph("你屬於資源整合與長期累積型財富模式。此類型適合透過專業能力、系統化收入與長期策略逐步建立財富。", body),
        Paragraph("二、收入模式", h),
        Paragraph("適合知識型、顧問型、技術服務、內容產品、資料分析與系統化收入。", body),
        Paragraph("三、風險提醒", h),
        Paragraph("需避免情緒決策、過度槓桿與短期衝動操作。越能建立紀律與風控，越能穩定累積。", body),
        Paragraph("四、行動建議", h),
        Paragraph("1. 建立穩定現金流<br/>2. 發展專業技能<br/>3. 設定風險上限<br/>4. 長期資產配置<br/>5. 建立可複製的系統收入", body),
        Spacer(1, 20),
        Paragraph("免責聲明：本報告為占星與個人策略分析，不構成投資建議、法律建議或財務承諾。", body)
    ]
    doc.build(content)
    return {"status": "success", "download_url": f"/reports/{filename}", "filename": filename}
