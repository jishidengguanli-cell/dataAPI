# login.py
# 支援兩種方式：
# 1) QR 登入（預設）：TELEGRAM_LOGIN_METHOD=qr
# 2) 6位數碼登入：   TELEGRAM_LOGIN_METHOD=code + TELEGRAM_PHONE_NUMBER + TELEGRAM_LOGIN_CODE (+ TELEGRAM_2FA_PASSWORD 可選)
#
# 成功後會把 session 存在 TELEGRAM_SESSION 指定路徑（建議 /data/user），即 /data/user.session

import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_PATH = os.environ.get("TELEGRAM_SESSION", "user")
LOGIN_METHOD = os.environ.get("TELEGRAM_LOGIN_METHOD", "qr").lower().strip()

PHONE = os.environ.get("TELEGRAM_PHONE_NUMBER")           # e.g. +8869xxxxxxx
CODE  = os.environ.get("TELEGRAM_LOGIN_CODE")             # 6位數登入碼
PWD   = os.environ.get("TELEGRAM_2FA_PASSWORD", "")       # 若帳號開了兩步驟密碼

def log(msg: str):
    print(f"[login.py] {msg}", flush=True)

def print_ascii_qr(url: str) -> None:
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception as e:
        log(f"（可選）ASCII QR 產生失敗：{e}")
        log("請使用下方 URL 到任何 QR 產生器生成圖片，再用 Telegram App 掃描。")

async def login_with_qr(client: TelegramClient):
    log("選擇：QR 登入流程")
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        log(f"已登入：{me.username or me.id}；session 有效，無需重登。")
        return

    qr_login = await client.qr_login()
    log("請在 Telegram 手機 App：設定 → 裝置 → 連結桌面裝置，掃描下方 QR（或用 URL 產生 QR）：")
    log(qr_login.url)
    print_ascii_qr(qr_login.url)

    try:
        await qr_login.wait()  # 等待使用者掃描確認
        log("QR 登入成功，正在保存 session…")
    except Exception as e:
        log(f"登入失敗：{e}")
        raise

    if await client.is_user_authorized():
        me = await client.get_me()
        log(f"完成，已登入為：{me.username or me.id}")
        log(f"Session 檔：{SESSION_PATH}.session")
    else:
        raise RuntimeError("看起來仍未授權，請重試。")

async def login_with_code(client: TelegramClient):
    log("選擇：6位數碼登入流程")
    if not PHONE or not CODE:
        raise RuntimeError("缺少 TELEGRAM_PHONE_NUMBER 或 TELEGRAM_LOGIN_CODE。")

    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        log(f"已登入：{me.username or me.id}；session 有效，無需重登。")
        return

    log(f"向 {PHONE} 發送登入請求…（如果你已從 Telegram App 收到 6位數碼，直接繼續）")
    try:
        # 有些情況 send_code_request 才需要；若你已取得 CODE，也可直接 sign_in
        await client.send_code_request(PHONE)
    except Exception as e:
        log(f"send_code_request 可能無法或非必要：{e}（繼續嘗試 sign_in）")

    try:
        await client.sign_in(PHONE, CODE)
    except SessionPasswordNeededError:
        if not PWD:
            raise RuntimeError("此帳號開啟了兩步驟密碼，請在 Secrets 設 TELEGRAM_2FA_PASSWORD。")
        await client.sign_in(password=PWD)

    if await client.is_user_authorized():
        me = await client.get_me()
        log(f"完成，已登入為：{me.username or me.id}")
        log(f"Session 檔：{SESSION_PATH}.session")
    else:
        raise RuntimeError("仍未授權，請檢查電話/驗證碼/二步驟密碼。")

async def main():
    if not API_ID or not API_HASH:
        log("缺少 TELEGRAM_API_ID / TELEGRAM_API_HASH，請先在 Fly 後台 Secrets 設定。")
        sys.exit(1)

    # 建立 Client；SESSION_PATH 會生成 {SESSION_PATH}.session
    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)

    try:
        if LOGIN_METHOD == "code":
            await login_with_code(client)
        else:
            await login_with_qr(client)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"程式終止：{e}")
        sys.exit(2)
