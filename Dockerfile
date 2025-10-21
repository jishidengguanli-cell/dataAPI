FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 安裝字型與時區資料（matplotlib 中文＋穩定）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# 放入原始碼
COPY . .

# 提示：請把 dataAPI.py 裡的字型路徑改為 Linux 版 Noto CJK：
# zh_font = fm.FontProperties(fname="/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc")

# 讓 Telethon 的 session、輸出的 CSV/PNG 可以持久化，將工作目錄切到 /data（會掛 Volume）
WORKDIR /data

# 預設執行你的腳本（保留原檔名即可）
CMD ["python", "/app/dataAPI.py"]
