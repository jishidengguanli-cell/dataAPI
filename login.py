# login.py
# 作用：在 Fly.io 上執行一次 Telegram「QR 登入」
# 成功後會把 session 檔存到 TELEGRAM_SESSION 指定的路徑（建議 /data/user）
# 需要的環境變數：TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION

import os
import sys
import asyncio
from telethon import TelegramClient

# 讀環境變數
API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_PATH = os.environ.get("TELEGRAM_SESSION", "user")  # 會寫成 /data/user.session

if not API_ID or not API_HASH:
    print("[login.py] 缺少 TELEGRAM_API_ID / TELEGRAM_API_HASH，請先在 Fly 後台 Secrets 設定。")
    sys.exit(1)

# Optional：嘗試在日誌輸出 ASCII QR（若容器有安裝 qrcode，就能在 Logs 看到 2D 條碼）
def print_ascii_qr(url: str) -> None:
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception as e:
        # 沒安裝 qrcode 或失敗就忽略，直接印 URL
        print(f"[login.py]（可選）ASCII QR 產生失敗：{e}")
        print("[login.py] 請改用下方 URL 於任何 QR 產生器轉為 QR 後，打開 Telegram App 掃描。")

async def do_login():
    # 用 SESSION_PATH 作為 session 名稱/路徑；將會生成 {SESSION_PATH}.session
    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"[login.py] 已登入：{me.username or me.id}；session 仍有效，無需重登。")
        await client.disconnect()
        return

    print("[login.py] 尚未授權，進入 QR 登入流程…")
    # 產生一次性 QR 登入，請用 Telegram 手機 App 掃描：設定 → 裝置 → 連結桌面裝置
    qr_login = await client.qr_login()

    print("[login.py] 請在 Telegram 手機 App：設定 → 裝置 → 連結桌面裝置，掃描本 QR。")
    print("[login.py] 若 Logs 未顯示 QR 圖，請使用以下 URL 生成 QR：")
    print(qr_login.url)
    print_ascii_qr(qr_login.url)

    # 等待用戶掃描並確認（通常幾秒內完成）
    try:
        await qr_login.wait()
        print("[login.py] QR 登入成功！正在保存 session…")
    except Exception as e:
        print(f"[login.py] 登入失敗：{e}")
        await client.disconnect()
        sys.exit(2)

    # 再次確認授權狀態
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"[login.py] 完成，已登入為：{me.username or me.id}")
        print(f"[login.py] Session 檔已寫入：{SESSION_PATH}.session")
    else:
        print("[login.py] 看起來仍未授權，請重試一次。")
        await client.disconnect()
        sys.exit(3)

    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(do_login())
    except KeyboardInterrupt:
        print("[login.py] 中斷。")
