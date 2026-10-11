import os
import requests

# 從 GitHub Secrets 環境變數讀取
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")


def main():
  print("🔍 檢查從 GitHub Secrets 讀取的憑證...")

  if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
    print(
        "❌ 讀取失敗：未抓到 LINE_TOKEN 或 LINE_USER_ID，請檢查 GitHub"
        " Secrets 設定。"
    )
    return

  print("✅ 成功讀取憑證，正在發送測試訊息至 LINE...")

  url = "https://api.line.me/v2/bot/message/push"
  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
  }
  payload = {
      "to": LINE_USER_ID,
      "messages": [{
          "type": "text",
          "text": (
              "🔔 【LINE 測試成功】\n這是一則透過 GitHub Secrets"
              " 讀取憑證所發送的測試訊息！"
          ),
      }],
  }

  try:
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    if res.status_code == 200:
      print("✅ LINE 測試訊息已成功發送！請檢查手機是否有收到通知。")
    else:
      print(
          f"❌ 發送失敗，狀態碼: {res.status_code}，錯誤訊息: {res.text}"
      )
  except Exception as e:
    print(f"❌ 發生例外錯誤: {e}")


if __name__ == "__main__":
  main()
