# 安全版 API + WordPress 按鈕套件

## 檔案
- main.py：安全版 FastAPI
- frontend_demo.html：外部表單頁，可呼叫 API
- wordpress_button.html：WordPress 按鈕跳轉範例
- ecpay_payment_flow.md：綠界接法流程
- requirements.txt：套件清單

## 安裝
pip install -r requirements.txt

## 設定 API Key

Windows PowerShell:
$env:ASTRO_API_KEY="你的超長安全金鑰"

Mac / Linux:
export ASTRO_API_KEY="你的超長安全金鑰"

## 啟動
uvicorn main:app --reload --host 0.0.0.0 --port 8000

## 測試
http://127.0.0.1:8000/docs

## WordPress.com 注意
WordPress.com 會封鎖 script/form/input。
建議：
WordPress 放按鈕 → 跳到外部表單頁 → 外部表單頁呼叫 API。
