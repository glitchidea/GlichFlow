FROM python:3.9-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Proje dosyalarını kopyala
COPY . .

# Statik dosyaları topla
RUN python manage.py collectstatic --noinput

# Gunicorn ile uygulamayı başlat
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:6062"]
