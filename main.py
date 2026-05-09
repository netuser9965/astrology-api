# -*- coding: utf-8 -*-
"""
安全版 AI 占星財富報告 API
安裝：
pip install fastapi uvicorn reportlab pydantic
啟動：
uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import uuid
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
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


class BirthInput(BaseModel):
    name: Optional[str] = None
    birth_date: str
    birth_time: str
    birth_place: str
    gender: Optional[str] = None
    timezone: Optional[str] = "Asia/Taipei"


def check_api_key(x_api_key: Optional[str]):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


@app.post("/api/generate-report")
def generate_report(data: BirthInput, x_api_key: Optional[str] = Header(None)):
    check_api_key(x_api_key)

    report_id = str(uuid.uuid4())[:8]
    filename = f"wealth_report_{report_id}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    title = ParagraphStyle("Title", fontName="STSong-Light", fontSize=20, leading=26)
    body = ParagraphStyle("Body", fontName="STSong-Light", fontSize=11, leading=17)

    content = []
    content.append(Paragraph("個人財富命盤 AI 深度報告", title))
    content.append(Spacer(1, 20))
    content.append(Paragraph(f"姓名：{data.name or '未填'}", body))
    content.append(Paragraph(f"出生日期：{data.birth_date}", body))
    content.append(Paragraph(f"出生時間：{data.birth_time}", body))
    content.append(Paragraph(f"出生地點：{data.birth_place}", body))
    content.append(Paragraph(f"性別：{data.gender or '未填'}", body))
    content.append(Spacer(1, 20))
    content.append(Paragraph("【財富定位】", body))
    content.append(Paragraph("你屬於資源整合與長期累積型財富模式，適合透過專業能力、系統化收入與長期策略建立財富。", body))
    content.append(Spacer(1, 12))
    content.append(Paragraph("【風險提醒】", body))
    content.append(Paragraph("需避免情緒決策、過度槓桿與短期衝動操作。", body))

    doc.build(content)

    return {
        "status": "success",
        "download_url": f"/reports/{filename}",
        "filename": filename
    }


@app.get("/")
def home():
    return {"service": "Secure Astrology API", "status": "running"}
