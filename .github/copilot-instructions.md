# Drug Delivery Management System

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

A multi-implementation drug delivery management system with Flask/FastAPI backends and static HTML frontend. The recommended stack is Python Flask + Static HTML + Vanilla JavaScript for reliability and simplicity.

## Working Effectively

### Recommended Setup (Flask + Static HTML)
- Install Python dependencies: `pip3 install -r server/requirements.txt` -- takes 5-10 seconds
- Start Flask backend: `cd server && python3 main.py` -- starts in 3-5 seconds at http://127.0.0.1:8000
- Test backend health: `curl http://127.0.0.1:8000/api/health`
- Start static frontend: `cd friendly-med-pal-main && python3 -m http.server 5173` -- serves at http://127.0.0.1:5173
- Access application: Open http://127.0.0.1:5173/index.html in browser

### Alternative Setup (FastAPI + Static HTML)
- Install FastAPI dependencies: `cd friendly-med-pal-main && pip3 install -r backend/requirements.txt` -- takes 15-20 seconds
- **CRITICAL:** Run from parent directory: `cd friendly-med-pal-main && uvicorn backend.api:app --host 127.0.0.1 --port 8001` -- starts in 3-5 seconds
- **DO NOT** run uvicorn from inside the backend/ directory (import errors)
- Test backend: `curl http://127.0.0.1:8001/api/health`
- API docs available at: http://127.0.0.1:8001/docs

### Node.js/React Frontend (NOT RECOMMENDED)
- **AVOID:** The React frontend has broken HTML parsing due to duplicate DOCTYPE declarations
- `npm install` -- takes 40-45 seconds. Set timeout to 60+ minutes. NEVER CANCEL.
- `npm run build` -- FAILS due to HTML parsing errors in index.html
- `npm run lint` -- has warnings but completes
- Use the static HTML frontend instead

## Validation

### Required End-to-End Testing
After making changes, ALWAYS validate with these specific scenarios:

1. **Backend API Testing:**
   ```bash
   # Test health check
   curl http://127.0.0.1:8000/api/health
   
   # Create a patient
   curl -X POST http://127.0.0.1:8000/api/patients \
     -H "Content-Type: application/json" \
     -d '{"name": "Test Patient", "age": 30, "condition": "Test condition"}'
   
   # List patients
   curl http://127.0.0.1:8000/api/patients
   
   # Create a drug
   curl -X POST http://127.0.0.1:8000/api/drugs \
     -H "Content-Type: application/json" \
     -d '{"name": "Test Drug", "dosage": "500mg"}'
   ```

2. **Frontend Testing:**
   - Access http://127.0.0.1:5173/index.html
   - Verify all sections load: Dashboard, Patients, Drugs, Deliveries
   - Test adding a patient via the form
   - Test adding a drug via the form
   - Test scheduling a delivery
   - Verify data appears in the tables

### Manual Browser Testing
- **ALWAYS** open the application in a browser after backend changes
- Test patient creation flow: Fill form → Submit → Verify in patient list
- Test drug creation flow: Fill form → Submit → Verify in drug list  
- Test delivery scheduling: Select patient → Select drug → Set date → Submit
- Verify real-time updates and auto-refresh functionality

## Build and Test Times
- **pip3 install server dependencies:** 5-10 seconds
- **pip3 install FastAPI dependencies:** 15-20 seconds  
- **npm install:** 40-45 seconds. Set timeout to 60+ minutes. NEVER CANCEL.
- **Server startup:** 3-5 seconds for both Flask and FastAPI
- **NEVER CANCEL** any build or install command. Wait for completion.

## Common Issues and Troubleshooting

### FastAPI Import Errors
- **Problem:** `ImportError: attempted relative import with no known parent package`
- **Solution:** Always run uvicorn from the `friendly-med-pal-main/` directory, not from `backend/`
- **Correct:** `cd friendly-med-pal-main && uvicorn backend.api:app --host 127.0.0.1 --port 8001`

### React Build Failures
- **Problem:** `[vite:build-html] Unable to parse HTML; parse5 error code misplaced-doctype`
- **Solution:** Use the static HTML frontend instead. The React build is broken.
- **Workaround:** The static HTML in `index.html` has duplicate DOCTYPE declarations

### Database Issues
- **Reset data:** Delete `server/data.db` or `backend/drug_delivery.db` to reset
- **Permissions:** SQLite files are auto-created with proper permissions

### Port Conflicts
- **Flask backend:** Default port 8000
- **FastAPI backend:** Use port 8001 to avoid conflicts
- **Static frontend:** Default port 5173

## Repository Structure

```
drug-delivery-managment-system/
├── server/                     # Flask backend (RECOMMENDED)
│   ├── main.py                # Flask app entry point
│   ├── requirements.txt       # Python dependencies (flask, flask-cors)
│   └── data.db               # SQLite database (auto-created)
├── friendly-med-pal-main/     # Main application directory
│   ├── index.html            # Static HTML frontend (RECOMMENDED)
│   ├── backend/              # FastAPI backend (alternative)
│   │   ├── api.py           # FastAPI app entry point
│   │   ├── service.py       # Business logic
│   │   ├── database.py      # Database schema
│   │   └── requirements.txt # FastAPI dependencies
│   ├── src/                  # React frontend (BROKEN - do not use)
│   ├── package.json          # Node.js dependencies
│   └── vite.config.ts        # Vite configuration
└── .github/
    └── copilot-instructions.md  # This file
```

## API Endpoints

Both Flask and FastAPI backends implement the same REST API:

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Health check |
| GET | /api/stats | Aggregate statistics |
| POST | /api/patients | Create patient |
| GET | /api/patients | List patients |
| POST | /api/drugs | Create drug |
| GET | /api/drugs | List drugs |
| POST | /api/deliveries | Create delivery |
| GET | /api/deliveries | List deliveries |
| PATCH | /api/deliveries/{id}/status | Update delivery status |
| POST | /api/seed | Insert demo data |

## Key Technologies

- **Backend:** Python 3.12+, Flask (recommended) or FastAPI
- **Database:** SQLite (auto-created, file-based)
- **Frontend:** Static HTML + Vanilla JavaScript + Tailwind CSS
- **Testing:** Manual browser testing, curl for API testing
- **Development:** No build step required for recommended stack

## Quick Commands Reference

```bash
# Start Flask backend
cd server && python3 main.py

# Start FastAPI backend  
cd friendly-med-pal-main && uvicorn backend.api:app --host 127.0.0.1 --port 8001

# Start static frontend
cd friendly-med-pal-main && python3 -m http.server 5173

# Install dependencies
pip3 install -r server/requirements.txt                    # Flask
pip3 install -r friendly-med-pal-main/backend/requirements.txt  # FastAPI

# Test API health
curl http://127.0.0.1:8000/api/health   # Flask
curl http://127.0.0.1:8001/api/health   # FastAPI

# Reset database
rm server/data.db                        # Flask
rm friendly-med-pal-main/backend/drug_delivery.db  # FastAPI
```

## Development Workflow

1. **Make backend changes:** Edit Flask (`server/main.py`) or FastAPI (`friendly-med-pal-main/backend/`)
2. **Restart server:** Kill and restart the Python process
3. **Test API:** Use curl commands or API testing tools
4. **Test frontend:** Refresh browser and test user flows
5. **Validate:** Run through complete user scenarios
6. **NEVER** attempt to build the React frontend - it's broken

Always prioritize the Flask + Static HTML stack for reliability and development speed.