FROM python:3.11-slim

# 컴카드 PPT → 미리보기 변환용 LibreOffice(+한글 폰트). SOFFICE_PATH 없이 PATH의 soffice를 쓴다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-impress fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
