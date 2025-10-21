FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 安裝字型與時區資料（字型給 matplotlib 中文用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk tzdata \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# 你的程式碼
COPY . .

# ⚠️ 請把 dataAPI.py 內的字型設定改為 Linux 的 Noto CJK 路徑，例如：
# zh_font = fm.FontProperties(fname="/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc")

# 將執行時的工作目錄放在 /data（之後會掛 Volume）
WORKDIR /data

CMD ["python", "/app/dataAPI.py"]
