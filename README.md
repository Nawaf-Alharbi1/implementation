# THIQA — Car Insurance Recommendation Demo

THIQA is a university graduation-project prototype for personalized car-insurance recommendations. It demonstrates a three-agent pipeline using **mock insurer APIs** and sample prices. These prices are simulated and are **not real quotes from Saudi insurers**.

## Architecture

1. **Agent 1 — Data Receiver & Retrieval:** validates the request, calls the mock insurer endpoints in parallel, and normalizes the returned offers.
2. **Agent 2 — Recommendation:** filters eligible offers and ranks them using weighted criteria and the selected priority.
3. **Agent 3 — Explainer:** returns a plain-language explanation of the selected offer.
4. **Node.js / Express:** serves the website and forwards `POST /api/recommend` to the Python agents service.

## Run locally (Windows)

### First-time setup

Install Python 3.10+ and Node.js, then run these commands from the repository folder:

```bat
cd agents
python -m pip install -r requirements.txt
cd ..\server
npm install
cd ..
```

### Start the demo

Double-click `run-website.bat`. It opens separate terminal windows for:
- Mock insurer APIs: `http://127.0.0.1:8001`
- Python agents: `http://127.0.0.1:8000`
- Website: `http://localhost:3000`

Open `http://localhost:3000` in your browser. Keep all three terminal windows open while testing.

If the batch file is blocked, start each service manually in a separate terminal from the repository folder:

```bat
cd agents
python -m uvicorn mock_insurer_api:app --host 127.0.0.1 --port 8001
```

```bat
cd agents
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```bat
cd server
npm start
```

## Quick health checks

- Website/server: open `http://localhost:3000/api/health`
- Python agents: open `http://127.0.0.1:8000/health`
- Interactive API docs: open `http://127.0.0.1:8000/docs`

## Run tests

```bat
cd agents
python -m pytest tests -v
```

Tests use simulated insurer responses; they do not contact real insurance companies.

## Important current limitations

- **Mock data only:** insurer prices, ratings, and other provider characteristics are demo values. No real insurer API credentials or production insurer integration are included.
- **Database persistence is not connected to the recommendation flow yet.** The API returns a recommendation, but this demo does not currently save the request, retrieved quotes, selected quote, or explanation to the database.
- **Login, registration, and an admin dashboard are not implemented in the current server files.** The interface should be treated as a demonstration, not a production service.
- The web form sends a sample vehicle value by default; edit it to test different values.
- Do not enter real national ID numbers or other sensitive personal information into this demo.

The prototype demonstrates the three-agent recommendation flow. Database persistence, authentication, and real insurer integration remain implementation tasks.
