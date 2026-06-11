# 台股每日成交量與週轉率前100排名爬蟲工具 - 實作計劃

## 1. 專案目標
- 每天 **下午 4 點 (臺灣時間)** 自動執行
- 取得當日臺股 (TWSE + TPEx) **成交量前 100** 與 **週轉率前 100**
- 合併排名，考慮成交量相對比例 (例如成交量 / 總市場成交量)
- 輸出 Markdown / CSV / Excel 報告，可寄信或存檔

## 2. 推薦技術棧
- **Python 3.10+**
- **FinMind** (主要資料來源) + TWSE OpenAPI 補充
- **pandas** 資料處理
- **schedule** 或 **cron** / Windows Task Scheduler 定時
- **smtplib** 或 **yagmail** 寄報告
- 可選：`requests`, `beautifulsoup4`, `openpyxl`

## 3. 資料來源與取得方式
### 主要：FinMind (最推薦)
```python
from FinMind.data import DataLoader
dl = DataLoader()
df = dl.taiwan_stock_daily(start_date=today)  # 當日
info = dl.taiwan_stock_info()  # 股本資料