FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=180

# 安裝中文字型與時區（matplotlib 需要字型）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# 使用 BuildKit 的 pip 快取，可大量減少重複下載
# 並把 timeout 拉長，降低「連線被重置」造成的失敗
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
 && pip install -r requirements.txt --timeout 300

# 放入原始碼
COPY . .

# 你的程式內請改用 Linux 的 Noto CJK 路徑：
# zh_font = fm.FontProperties(fname="/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc")

# 讓輸出與 Telethon session 落到可掛載的資料夾
WORKDIR /data
CMD ["python", "/app/dataAPI.py"]
