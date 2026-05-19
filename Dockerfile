FROM python:3.12-slim

WORKDIR /app

# gcc dibutuhkan untuk compile beberapa dependency (cffi, dll)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6 \
 && apt-get clean && apt-get autoremove -y

# Install Python dependencies (layer terpisah agar re-build cepat)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-warm matplotlib font cache saat build image, bukan saat runtime
RUN python -c 'import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot'

# Copy source code
COPY app.py downloader.py ./
COPY templates/ templates/

# Cache dir; akan di-override oleh bind-mount saat docker compose up
RUN mkdir -p cache

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV API_BASE_URL=http://localhost:5000
ENV FLASK_PORT=5000

CMD ["python", "app.py"]