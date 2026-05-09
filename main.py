@app.post("/api/generate-report")
def generate_report(data: BirthInput, x_api_key: Optional[str] = Header(None)):

    check_api_key(x_api_key)

    # 🔐 收費鎖
    if not data.token or data.token != "PAID_OK":
        raise HTTPException(status_code=403, detail="請先完成付款")

    filename = f"wealth_report_{str(uuid.uuid4())[:8]}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(path, pagesize=A4)

    title = ParagraphStyle(...)
    body = ParagraphStyle(...)

    content = [
        Paragraph("個人財富命盤 AI 深度報告", title),
        ...
    ]

    doc.build(content)

    return {
        "status": "success",
        "download_url": f"/reports/{filename}",
        "filename": filename
    }
