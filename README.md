# 🏗️ BuildFlow AI — Intelligent Construction Project Management

> An AI-powered construction management platform built with FastAPI, Next.js, Google Gemini, and ChromaDB.

---

## 📋 Table of Contents

- [Features Overview](#features-overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)

---

## ✨ Features Overview

| Feature | Description |
|---|---|
| 🤖 **Chat Agent** | Natural-language Q&A over project data powered by Gemini Pro |
| 📄 **Doc-Gen** | Auto-generate PDF progress reports, BOQ sheets, and site summaries |
| 📊 **Analytics Dashboard** | Real-time KPIs, budget burn-down charts, progress heatmaps |
| 🔗 **Multi-Agent Pipeline** | Orchestrated agents for cost estimation, delay prediction, and risk scoring |
| 🗂️ **Vector Search** | Semantic search across all project documents via ChromaDB |
| 📁 **Data Import** | Upload CSV / Excel project data with instant ingestion |

---

## 🏛️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                          │
│                    Next.js 14  (port 3000)                     │
└───────────────────────────┬────────────────────────────────────┘
                            │ HTTP / REST
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND  (port 8000)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  /chat        │  │  /analytics  │  │  /generate-doc       │ │
│  │  Gemini Pro   │  │  Pandas/     │  │  ReportLab PDF       │ │
│  │  RAG Agent    │  │  scikit-learn│  │  Generator           │ │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘ │
│         │                                                       │
│  ┌──────▼──────────────────────────────────────────────────┐   │
│  │              Multi-Agent Orchestrator                    │   │
│  │   Cost Agent │ Delay Agent │ Risk Agent │ Summary Agent  │   │
│  └──────┬───────────────────────────────────────────────────┘  │
│         │                                                       │
│  ┌──────▼───────────────────┐  ┌────────────────────────────┐  │
│  │   ChromaDB Vector Store  │  │   CSV / Excel Data Store   │  │
│  │   (Semantic Search)      │  │   backend/data/projects.csv│  │
│  └──────────────────────────┘  └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   Google Gemini API     │
              │   (LLM + Embeddings)    │
              └─────────────────────────┘
```

---

## ✅ Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Node.js** | 18+ | For the Next.js frontend |
| **Python** | 3.10+ | For the FastAPI backend |
| **pip** | Latest | Python package manager |
| **Google Gemini API Key** | — | [Get yours here](https://aistudio.google.com/app/apikey) |
| **Docker** *(optional)* | 24+ | For containerised deployment |

---

## 🚀 Local Setup

### 1. Clone / Open the Project

```bash
cd "c:/Users/Mr/Desktop/Excel Automation"
```

### 2. Configure Environment Variables

```bash
# Copy the example file and fill in your values
copy .env.example .env
```

Edit `.env` and replace `your_gemini_api_key_here` with your actual Gemini API key.

---

### 3. Backend Setup (FastAPI)

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at **http://localhost:8000**
Interactive docs at **http://localhost:8000/docs**

---

### 4. Frontend Setup (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at **http://localhost:3000**

---

## 🔐 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Google Gemini API key |
| `CHROMADB_PATH` | `./chroma_db` | Path to persist ChromaDB vector store |
| `GENERATED_DOCS_PATH` | `./generated_docs` | Output folder for generated PDFs |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed CORS origin for the frontend |

---

## 📡 API Endpoints

### Projects

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/projects` | List all projects with filters |
| `GET` | `/api/projects/{id}` | Get single project details |
| `POST` | `/api/projects` | Create a new project |
| `PUT` | `/api/projects/{id}` | Update project data |
| `DELETE` | `/api/projects/{id}` | Delete a project |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analytics/summary` | KPI summary (budget, progress, status breakdown) |
| `GET` | `/api/analytics/budget` | Budget vs. spent analysis per project |
| `GET` | `/api/analytics/delay-risk` | ML-powered delay risk scores |
| `GET` | `/api/analytics/phase-distribution` | Project count by phase |

### AI Chat Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a natural-language query to the Gemini agent |
| `GET` | `/api/chat/history` | Retrieve conversation history |
| `DELETE` | `/api/chat/history` | Clear conversation history |

### Document Generation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate-doc/progress-report` | Generate a PDF progress report for a project |
| `POST` | `/api/generate-doc/boq` | Generate a Bill of Quantities sheet |
| `POST` | `/api/generate-doc/summary` | Generate an executive summary PDF |
| `GET` | `/api/docs/list` | List all previously generated documents |
| `GET` | `/api/docs/download/{filename}` | Download a generated document |

### Data Import

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/import/csv` | Upload a CSV file to replace/append project data |
| `POST` | `/api/import/excel` | Upload an Excel (.xlsx) file |
| `GET` | `/api/import/status` | Check the status of the last import |

### Multi-Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/agents/run` | Trigger the multi-agent pipeline for a project |
| `GET` | `/api/agents/results/{project_id}` | Retrieve agent pipeline results |

---

## 🐳 Docker Deployment

```bash
# From the project root
docker-compose up --build

# Run in detached mode
docker-compose up --build -d

# Stop all services
docker-compose down
```

Services:
- **Backend** → http://localhost:8000
- **Frontend** → http://localhost:3000

---

## 📁 Project Structure

```
Excel Automation/
├── .env.example              # Environment variable template
├── .env                      # Your local secrets (git-ignored)
├── docker-compose.yml        # Multi-service Docker configuration
├── README.md                 # This file
│
├── backend/
│   ├── Dockerfile            # Python 3.11-slim container
│   ├── requirements.txt      # Python dependencies
│   ├── main.py               # FastAPI application entry point
│   ├── routers/              # API route handlers
│   │   ├── projects.py
│   │   ├── analytics.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── agents.py
│   ├── services/             # Business logic & AI integrations
│   │   ├── gemini_service.py
│   │   ├── chromadb_service.py
│   │   ├── pdf_service.py
│   │   └── analytics_service.py
│   ├── models/               # Pydantic data models
│   │   └── schemas.py
│   ├── data/
│   │   └── projects.csv      # Sample dataset (50 projects)
│   ├── generated_docs/       # Output PDFs (auto-created)
│   └── chroma_db/            # Vector store (auto-created)
│
└── frontend/
    ├── Dockerfile            # Node 18 container
    ├── package.json
    ├── app/                  # Next.js 14 App Router pages
    │   ├── page.tsx          # Dashboard
    │   ├── projects/
    │   ├── analytics/
    │   ├── chat/
    │   └── documents/
    └── components/           # Reusable React components
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| **Backend** | FastAPI, Python 3.11, Uvicorn |
| **AI / LLM** | Google Gemini Pro (via `google-generativeai`) |
| **Vector DB** | ChromaDB (local persistent store) |
| **Data** | Pandas, NumPy, scikit-learn |
| **PDF Gen** | ReportLab |
| **Containers** | Docker, Docker Compose |

---

## 📄 License

MIT License — © 2026 Excel Automation / BuildFlow AI Team
