# Airport GIS Backend

FastAPI və PostgreSQL/PostGIS əsaslı Airport GIS backend layihəsi.

## Development mühitinin başladılması

1. Lokal konfiqurasiya faylını yaradın və development credential-larını dəyişin:

   ```bash
   cp .env.example .env
   ```

2. Servisləri başladın:

   ```bash
   docker compose up -d --build
   ```

3. Servislərin vəziyyətini yoxlayın:

   ```bash
   docker compose ps
   curl http://localhost:8000/api/v1/health/ready
   ```

API sənədləri `http://localhost:8000/docs` ünvanında açılır.

PostgreSQL hostdan `localhost:5434` ünvanında əlçatandır. Konteyner daxilində
standart `5432` portu istifadə olunur.

Database məlumatları `postgres_data` adlı Docker volume-da saxlanır və
konteyner yenidən başladıldıqda itmir.

Servisləri dayandırmaq üçün:

```bash
docker compose down
```

`docker compose down -v` database volume-unu da silir; məlumatların qorunması
üçün `-v` parametrini yalnız məqsədli şəkildə istifadə edin.

## Database migration-ları

Migration yaratmaq, tətbiq etmək və geri qaytarmaq əmrləri
[`docs/migrations.md`](docs/migrations.md) sənədində saxlanılır.

## Authentication

İlk administratorun yaradılması, login, refresh və logout istifadəsi
[`docs/authentication.md`](docs/authentication.md) sənədində göstərilir.
