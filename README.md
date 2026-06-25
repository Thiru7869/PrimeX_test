# PrimeX AI

A personal, single-user AI Operating System (chat, document intelligence,
RAG, memory, and agents) built on free-tier infrastructure for learning and
portfolio purposes.

## Structure
- `frontend/` — Next.js app (deploys to Vercel)
- `backend/`  — FastAPI app (deploys to Render)
- `docs/`     — architecture and design docs
- `.github/`  — CI workflows

## Run locally

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000/api/v1/health

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
Open http://localhost:3000