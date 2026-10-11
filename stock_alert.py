import datetime
import json
import os
import pytz
import requests
import yfinance as yf

# ==========================================
# 1. 憑證設定 (從環境變數讀取 GitHub Secrets)
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

TW_TZ = pytz.timezone("Asia/Taipei")
STATE_FILE = "alerted_state.json"

# ==========================================
# 2. 39 檔監控股票清單與均線參數
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
    "3707": {"name": "漢磊", "ma": 18, "type": ".TW"},
    "3711": {"name": "日月光投控", "ma": 31, "type": ".TW"},
    "5347": {"name": "世界", "ma": 28, "type": ".TW"},
    "6116": {"name": "彩晶", "ma": 16, "type": ".TW"},
    "6191": {"name": "精成科", "ma": 18, "type": ".TW"},
    "6284": {"name": "佳邦", "ma": 24, "type": ".TW"},
    "6443": {"name": "元晶", "ma": 19, "type": ".TW"},
    "8069": {"name": "元太", "ma": 22, "type": ".TWO"},
}


# ==========================================
# 3. 狀態讀寫函式 (避免重複推播)
# ==========================================
def load_state():
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


def save_state(alerted_set):
  today_str = datetime.datetime.now(TW_TZ).strftime("%Y-%m-%d")
  data = {"date": today_str, "alerted": list(alerted_set)}
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)


# ==========================================
# 4. LINE 推播函式
# ==========================================
def send_line_push(msg_text):
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
    print(f"LINE 發送失敗: {e}")
    return False


# ==========================================
# 5. 主執行邏輯
# ==========================================
def main():
  now_tw = datetime.datetime.now(TW_TZ)
  print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] 開始掃描 39 檔台股價格...")

  alerted_today = load_state()

  for code, info in STOCKS.items():
    if code in alerted_today:
      continue

    ticker_symbol = f"{code}{info['type']}"
    ma_period = info["ma"]
    stock_name = info["name"]

    try:
      stock = yf.Ticker(ticker_symbol)
      df = stock.history(period="60d", interval="1d")

      if len(df) < ma_period + 1:
        continue

      yesterday_df = df.iloc[:-1]
      prev_ma = yesterday_df["Close"].tail(ma_period).mean()
      threshold_price = round(prev_ma * 1.01, 2)

      current_price = round(df["Close"].iloc[-1], 2)
      current_vol = int(df["Volume"].iloc[-1] // 1000)
      yesterday_vol = int(df["Volume"].iloc[-2] // 1000)

      if current_price >= threshold_price:
        message = (
            f"📈 【台股均線突破提醒】\n"
            f"------------------------\n"
            f"1. 股票名稱 (代號)：{stock_name} ({code})\n"
            f"2. 當前股價：{current_price} 元\n"
            f"3. 突破價格 (前日{ma_period}MA x 1.01)：{threshold_price} 元\n"
            f"4. 成交量資訊：\n"
            f"   • 當前成交量：{current_vol:,} 張\n"
            f"   • 昨天成交量：{yesterday_vol:,} 張"
        )

        if send_line_push(message):
          print(f"✅ 成功發送推播：{stock_name} ({code})")
          alerted_today.add(code)

    except Exception as e:
      print(f"❌ 處理 {code} {stock_name} 時出錯: {e}")

  save_state(alerted_today)


if __name__ == "__main__":
  main()