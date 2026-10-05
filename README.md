# MiruvWeb

Interní webová aplikace se správou uživatelů, evidencí pohonných hmot, dovolených a výkonu, včetně notifikací.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **Frontend:** Vue 3, TypeScript, Vite, Pinia

## Spuštění přes Docker Compose

```bash
docker compose up --build
```

- Backend běží na `http://localhost:8000`
- Frontend běží na `http://localhost:3000`

Výchozí admin účet (lze přepsat přes env proměnné, viz `docker-compose.yml`):

- uživatel: `admin`
- heslo: `admin`

## Lokální vývoj

### Backend
#### Windows
```bash
cd backend
source .venv/Scripts/Activate
uvicorn main:app --reload
```
#### Linux
```
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm run dev -- --port 3000
```

### Co udělat na lokále po merge
```
git sync
git push
```

## Konfigurace

Backend čte nastavení z proměnných prostředí (viz `docker-compose.yml`):

- `CORS_ORIGINS` – povolené originy pro CORS
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` – přihlašovací údaje výchozího admina
- `SECRET_KEY` – tajný klíč pro podepisování JWT (v produkci nutné změnit)
