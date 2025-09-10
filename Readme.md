## Quick start

1. Copy env:
   cp app/backend/.env.example app/backend/.env

   # edit SMTP and secrets

2. Build & run:
   docker compose up --build

3. API:
   http://localhost:8080/docs

### Data

- Postgres data persists in the `pg_data` named Docker volume.

### Migrations

- Alembic runs automatically on container start: `alembic upgrade head`.
