# Friendly Med Pal 2.0

Lightweight medication tracking demo rebuilt for reliability: static HTML + vanilla JS frontend and a clean FastAPI backend with SQLite.

## Features

- Patients: create & list
- Drugs: create & list
- Deliveries: schedule, list, update status (pending/delivered/missed/cancelled)
- Aggregate stats (patients, drugs, pending deliveries)
- API health indicator (automatic ping)

## Structure

```
friendly-med-pal-main/
	index.html          # Frontend (open directly in browser)
	server/             # Backend package
		main.py           # FastAPI app + SQLite models
		requirements.txt  # Python deps
```

The legacy React + Vite code remains under `src/` but is not required for the new simplified flow.

## Run Backend (Windows PowerShell)

Pure Python dependencies only (Flask). No Rust toolchain needed.

```powershell
cd friendly-med-pal-main
python -m venv .venv            # or: py -m venv .venv
. .venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r server/requirements.txt
py -m server.main               # or: python server/main.py
```

Flask serves at http://127.0.0.1:8000

Health check: http://127.0.0.1:8000/api/health

## Use Frontend

Open `index.html` directly (double‑click) OR optionally serve:

```powershell
python -m http.server 5173
```

Then browse http://127.0.0.1:5173/index.html

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Health check |
| POST | /api/patients | Create patient |
| GET | /api/patients | List patients |
| POST | /api/drugs | Create drug |
| GET | /api/drugs | List drugs |
| POST | /api/deliveries | Create delivery |
| GET | /api/deliveries | List deliveries |
| PATCH | /api/deliveries/{id}/status | Update delivery status |

## Data Storage

SQLite file auto-created at `server/data.db`. Delete it to reset data.

## Notes

- All CORS origins allowed (demo only, not production safe)
- No authentication or validation beyond basics
- Keep the terminal running to serve the API

## Cleaning Up Legacy Code

You can remove the `src/` directory and build config files if you no longer need the original React implementation.

## License

MIT (adjust as needed).
