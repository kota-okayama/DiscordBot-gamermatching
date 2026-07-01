FROM python:3.10-slim

WORKDIR /app

# 標準出力をバッファリングしないように設定
ENV PYTHONUNBUFFERED=1

# タイムゾーンを日本時間 (JST) に設定し、日本語フォントをインストール
ENV TZ=Asia/Tokyo
RUN apt-get update && apt-get install -y tzdata fonts-noto-cjk && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 依存パッケージを先にコピーしてキャッシュを活用
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー（.dockerignore で .env は除外される）
COPY . .

CMD ["python", "main.py"]
