# 綠界金流接法：收費 → 自動生成 PDF

正確流程：

1. WordPress 商品頁
   商品：個人財富命盤 AI 深度報告
   價格：NT$299

2. 用戶付款
   WooCommerce + 綠界外掛

3. 付款成功後
   後端收到付款成功通知
   才呼叫 /api/generate-report

4. 生成 PDF
   PDF 連結寫入訂單備註
   或 Email 給客戶

安全原則：
- 不要在 WordPress 前端公開 API Key
- 真正收費版應該由後端呼叫 API
- 前端只顯示付款狀態與下載連結
