# Konfigurasi Environment Stock Analyzer

## File `.env`

File `.env` digunakan untuk menyimpan konfigurasi aplikasi agar dapat diubah dengan mudah tanpa mengubah kode.

### Isi File `.env`

```bash
# Konfigurasi Flask App
FLASK_APP=app.py
FLASK_ENV=development

# Base URL untuk API
API_BASE_URL=http://127.0.0.1:5000

# Port Flask
FLASK_PORT=5000
```

### Cara Mengubah Base URL

Jika Anda ingin menjalankan aplikasi di komputer lain atau port yang berbeda:

1. **Untuk development lokal (default)**:
   ```bash
   API_BASE_URL=http://127.0.0.1:5000
   ```

2. **Untuk akses dari jaringan lokal** (ganti dengan IP komputer Anda):
   ```bash
   API_BASE_URL=http://192.168.1.100:5000
   ```

3. **Untuk production server**:
   ```bash
   API_BASE_URL=https://your-domain.com
   ```

## Instalasi Dependencies

Setelah clone atau update repository, install dependencies:

```bash
pip install -r requirements.txt
```

## Menjalankan Aplikasi

1. Pastikan file `.env` sudah ada di root folder project
2. Jalankan aplikasi Flask:
   ```bash
   python app.py
   ```
3. Buka browser dan akses sesuai `API_BASE_URL` yang dikonfigurasi

## Struktur Konfigurasi

- **`FLASK_APP`**: File utama Flask application
- **`FLASK_ENV`**: Environment mode (development/production)
- **`API_BASE_URL`**: Base URL yang digunakan oleh frontend untuk memanggil API
- **`FLASK_PORT`**: Port yang digunakan Flask server

## Catatan Penting

- File `.env` **tidak boleh** di-commit ke Git (sudah ada di `.gitignore`)
- Setiap developer dapat memiliki konfigurasi `.env` masing-masing
- Frontend (index.html) akan otomatis menggunakan `API_BASE_URL` dari environment variable
