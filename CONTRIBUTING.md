# Contributing

## Local setup

Use Python 3.10+ and Bun 1.x (Node.js/npm also work for the frontend).

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest -q

cd ..\frontend
bun install
bun run build
```

## Running the application

Start the API from `backend`:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in a second terminal:

```powershell
cd frontend
bun run dev
```

The API is available at `http://localhost:8000`, and the Vite application is
available at the URL printed by Vite (normally `http://localhost:5173`).

## Validation

Before submitting changes, run `python -m pytest -q` and `bun run build`.
Changes to API behavior should update `docs/API_SPEC.md` and include an
endpoint test where practical.

## Commits

Use concise conventional commit subjects such as `feat:`, `fix:`, `test:`,
`docs:`, or `chore:`.
