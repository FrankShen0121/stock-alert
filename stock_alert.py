import datetime
import json
import os
import pytz
import requests
import yfinance as yf

# ==========================================
# 1. 憑證與環境設定
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

TW_TZ = pytz.timezone("Asia/Taipei")
STATE_FILE = "alerted_state.json"
REPORT_FILE = "report.md"

# ==========================================
# 2. 44 檔監控股票清單與均線參數
# ==========================================
STOCKS = {
    "1504": {"name": "東元", "ma": 23, "type": ".TW"},
    "1711": {"name": "永光", "ma": 30, "type": ".TW"},
    "1795": {"name": "美時", "ma": 23, "type": ".TW"},
    "2301": {"name": "光寶科", "ma": 20, "type": ".TW"},
    "2303": {"name": "聯電", "ma": 27, "type": ".TW"},
    "2308": {"name": "台達電", "ma": 26, "type": ".TW"},
    "2313": {"name": "華通", "ma": 19, "type": ".TW"},
    "2317": {"name": "鴻海", "ma": 19, "type": ".TW"},
    "2324": {"name": "仁寶", "ma": 19, "type": ".TW"},
    "2327": {"name": "國巨", "ma": 19, "type": ".TW"},
    "2330": {"name": "台積電", "ma": 26, "type": ".TW"},
    "2337": {"name": "旺宏", "ma": 30, "type": ".TW"},
    "2338": {"name": "光罩", "ma": 26, "type": ".TW"},
    "2344": {"name": "華邦電", "ma": 19, "type": ".TW"},
    "2345": {"name": "智邦", "ma": 30, "type": ".TW"},
    "2347": {"name": "聯強", "ma": 38, "type": ".TW"},
    "2353": {"name": "宏碁", "ma": 17, "type": ".TW"},
    "2367": {"name": "耀華", "ma": 26, "type": ".TW"},
    "2376": {"name": "技嘉", "ma": 30, "type": ".TW"},
    "2382": {"name": "廣達", "ma": 23, "type": ".TW"},
    "2383": {"name": "台光電", "ma": 22, "type": ".TW"},
    "2385": {"name": "群光", "ma": 25, "type": ".TW"},
    "2395": {"name": "研華", "ma": 22, "type": ".TW"},
    "2408": {"name": "南亞科", "ma": 14, "type": ".TW"},
    "2409": {"name": "友達", "ma": 18, "type": ".TW"},
    "2454": {"name": "聯發科", "ma": 29, "type": ".TW"},
    "2472": {"name": "立隆電", "ma": 24, "type": ".TW"},
    "2485": {"name": "兆赫", "ma": 27, "type": ".TW"},
    "2498": {"name": "宏達電", "ma": 23, "type": ".TW"},
    "2610": {"name": "華航", "ma": 17, "type": ".TW"},
    "2646": {"name": "星宇航空", "ma": 23, "type": ".TW"},
    "3008": {"name": "大立光", "ma": 25, "type": ".TW"},
    "3017": {"name": "奇鋐", "ma": 19, "type": ".TW"},
    "3231": {"name": "緯創", "ma": 26, "type": ".TW"},
    "3450": {"name": "聯鈞", "ma": 20, "type": ".TW"},
    "3481": {"name": "群創", "ma": 20, "type": ".TW"},
    "3707": {"name": "漢磊", "ma": 18, "type": ".TWO"},
    "3711": {"name": "日月光投控", "ma": 31, "type": ".TW"},
    "5347": {"name": "世界", "ma": 28, "type": ".TWO"},
    "6116": {"name": "彩晶", "ma": 16, "type": ".TW"},
    "6191": {"name": "精成科", "ma": 18, "type": ".TW"},
    "6284": {"name": "佳邦", "ma": 24, "type": ".TWO"},
    "6443": {"name": "元晶", "ma": 19, "type": ".TW"},
    "8069": {"name": "元太", "ma": 22, "type": ".TWO"},
}


# ==========================================
# 3. 狀態讀寫函式 (避免重複推播)
# ==========================================
def load_state() -> set:
    today_str = datetime.datetime.now(TW_TZ).strftime("%Y-%m-%d")
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    return set(data.get("alerted", []))
        except Exception:
            pass
    return set()


def save_state(alerted_set: set):
    today_str = datetime.datetime.now(TW_TZ).strftime("%Y-%m-%d")
    data = {"date": today_str, "alerted": list(alerted_set)}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ==========================================
# 4. LINE 推播函式
# ==========================================
def send_line_push(msg_text: str) -> bool:
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️ 警告：未設定 LINE_TOKEN 或 LINE_USER_ID，略過推播。")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": msg_text}],
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ LINE 發送失敗: {e}")
        return False


# ==========================================
# 5. 主執行邏輯與報告生成
# ==========================================
def main():
    now_tw = datetime.datetime.now(TW_TZ)
    time_str = now_tw.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{time_str}] 開始批次下載與掃描 44 檔台股價格...")

    alerted_today = load_state()
    scanned_count = 0
    triggered_list = []
    error_list = []

    # 準備批次下載的 ticker 清單
    ticker_symbols = [f"{code}{info['type']}" for code, info in STOCKS.items()]

    try:
        # 批次下載歷史資料 (period='60d', threads=True 加速下載)
        data = yf.download(
            ticker_symbols, period="60d", interval="1d", group_by="ticker", progress=False, threads=True
        )
    except Exception as e:
        print(f"❌ 批次下載 Yahoo Finance 資料失敗: {e}")
        return

    for code, info in STOCKS.items():
        ticker_symbol = f"{code}{info['type']}"
        ma_period = info["ma"]
        stock_name = info["name"]

        try:
            # 從批次下載結果中萃取單一股票資料
            if len(ticker_symbols) == 1:
                df = data
            else:
                if ticker_symbol not in data:
                    error_list.append(f"{stock_name} ({code}): 無法取得市場資料")
                    continue
                df = data[ticker_symbol]

            # 清除可能存在的 NaN 列
            df = df.dropna(subset=["Close", "Volume"])

            # 確保資料長度足夠（需要包含均線期數 + 前 3 天 + 今天，至少 ma_period + 3）
            min_required = ma_period + 3
            if len(df) < min_required:
                error_list.append(f"{stock_name} ({code}): 歷史資料不足 (僅有 {len(df)} 筆，至少需 {min_required} 筆)")
                continue

            # 計算整體的移動平均線序列
            df["MA"] = df["Close"].rolling(window=ma_period).mean()

            # 計算突破門檻（昨日 MA * 1.01）
            yesterday_df = df.iloc[:-1]
            prev_ma = yesterday_df["Close"].tail(ma_period).mean()
            threshold_price = round(float(prev_ma) * 1.01, 2)

            current_price = round(float(df["Close"].iloc[-1]), 2)
            current_vol = int(df["Volume"].iloc[-1] // 1000)
            yesterday_vol = int(df["Volume"].iloc[-2] // 1000)

            # -------------------------------------------------------------
            # 條件：突破前三天（倒數第 4 天、倒數第 3 天、倒數第 2 天）
            # 收盤價皆須在當日 MA 之下
            # -------------------------------------------------------------
            recent_3days = df.iloc[-4:-1]
            is_below_ma_3days = all(recent_3days["Close"] < recent_3days["MA"])

            scanned_count += 1
            is_triggered = (current_price >= threshold_price) and is_below_ma_3days

            if is_triggered and code not in alerted_today:
                alerted_today.add(code)
                triggered_list.append({
                    "name": stock_name,
                    "code": code,
                    "price": current_price,
                    "threshold": threshold_price,
                    "ma_period": ma_period,
                    "volume": current_vol,
                    "yesterday_vol": yesterday_vol
                })

        except Exception as e:
            error_list.append(f"{stock_name} ({code}): {e}")

    save_state(alerted_today)

    # ==========================================
    # 6. 組合統一的 LINE 總結訊息並發送（不論有無突破皆發送）
    # ==========================================
    line_msg = (
        f"📊 【台股均線監控執行報告】\n"
        f"------------------------\n"
        f"🕒 執行時間：{time_str}\n"
        f"📈 掃描狀態：成功掃描 {scanned_count} / {len(STOCKS)} 檔\n"
    )

    if triggered_list:
        line_msg += f"\n🚨 【今日新觸發突破】({len(triggered_list)} 檔)\n"
        for item in triggered_list:
            line_msg += (
                f"• {item['name']} ({item['code']})\n"
                f"  - 現價：{item['price']} 元\n"
                f"  - 門檻 ({item['ma_period']}MA)：{item['threshold']} 元\n"
                f"  - 成交量：{item['volume']:,} 張\n"
            )
    else:
        line_msg += f"\n📌 狀態：截至目前無新符合突破條件的股票。"

    if error_list:
        line_msg += f"\n\n⚠️ 異常數：{len(error_list)} 筆"

    # 發送 LINE 總結訊息
    if send_line_push(line_msg):
        print("✅ LINE 執行報告推播成功！")
    else:
        print("❌ LINE 執行報告推播失敗！")

    # ==========================================
    # 7. 生成 Markdown 執行報告 (report.md)
    # ==========================================
    report_content = f"""# 📊 台股均線監控系統執行報告

- **最後執行時間**：`{time_str}` (台灣時間)
- **狀態**：`運行成功`
- **成功掃描股票數**：`{scanned_count} / {len(STOCKS)}` 檔

---

## 🚨 今日觸發突破清單（含前三天在均線下濾網）
"""
    if triggered_list:
        report_content += "| 股票名稱 | 代號 | 當前股價 | 突破門檻價 |\n|:---:|:---:|:---:|:---:|\n"
        for item in triggered_list:
            report_content += f"| {item['name']} | {item['code']} | {item['price']} | {item['threshold']} |\n"
    else:
        report_content += "*截至目前為止，今日尚無股票符合突破條件（或未符合前三天在均線下之條件）。*\n"

    report_content += "\n---\n\n## ⚠️ 異常與錯誤紀錄\n"
    if error_list:
        for err in error_list:
            report_content += f"- {err}\n"
    else:
        report_content += "*本次執行無任何錯誤或資料異常。*\n"

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_content)
    print("📝 執行報告 report.md 已成功生成！")


if __name__ == "__main__":
    main()
