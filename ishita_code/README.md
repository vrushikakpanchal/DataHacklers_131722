# SENTINEL — GenAI Cybersecurity Content Transformation Platform

SENTINEL is a GenAI-powered cybersecurity content transformation platform designed to convert unstructured cybersecurity information such as incident reports, threat intelligence, advisories, and vulnerability information into structured and actionable cybersecurity advisories.

The platform combines deterministic fact extraction, RAG-based threat intelligence retrieval, AI-powered content generation, validation, and database persistence into a single integrated workflow.

## Key Features

- Transform unstructured cybersecurity content into structured advisories
- Deterministic extraction and locking of important facts such as CVEs, IPs, URLs, hashes, products, and versions
- RAG-based retrieval of relevant cybersecurity intelligence
- Integration with NVD, CISA KEV, and CERT-In datasets
- AI-powered advisory generation using Ollama and `gpt-oss:120b-cloud`
- Validation of generated content against extracted facts and retrieved evidence
- SQLite-based persistence of transformations and generated outputs
- Review and approval workflow
- React-based dashboard and output interface
- FastAPI backend with REST APIs
- End-to-end integration between frontend, backend, RAG, AI generation, validation, and database

## Technology Stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS  
**Backend:** Python, FastAPI, Pydantic, SQLAlchemy  
**Database:** SQLite  
**AI:** Ollama — `gpt-oss:120b-cloud`  
**RAG:** NVD, CISA KEV, and CERT-In datasets

## System Workflow

```text
User Input
    ↓
Frontend
    ↓
FastAPI Backend
    ↓
Input / Document Processing
    ↓
Fact Extraction & Fact Locking
    ↓
RAG Retrieval
    ↓
NVD / CISA KEV / CERT-In Evidence
    ↓
Ollama — gpt-oss:120b-cloud
    ↓
Structured Cybersecurity Advisory
    ↓
Validation
    ↓
SQLite Persistence
    ↓
Output / Review Interface
SIH154-2/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── rag/
│   ├── tests/
│   ├── acceptance_test.py
│   └── .env.example
│
├── datasets/
│   ├── NVD CVE dataset
│   ├── CISA KEV dataset
│   └── CERT-In documents
│
├── src/
│   └── frontend application
│
├── public/
├── package.json
├── package-lock.json
└── README.md
Setup
Clone the Repository
git clone https://github.com/vrushikakpanchal/GenAI-SIH-2026.git
cd GenAI-SIH-2026

To use this implementation:

git checkout ishita
Frontend Setup

Install dependencies:

npm install

Start the frontend:

npm run dev

The frontend normally runs at:

http://localhost:5173
Backend Setup

Create and activate a virtual environment:

cd backend
python -m venv .venv
.venv\Scripts\activate

Install the required backend dependencies.

Create a local environment file:

backend/.env

using backend/.env.example as the template.

Ollama Setup

Ollama must be installed and running locally.

The project uses:

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud

The AI model is an external dependency and is not included in the repository. Each developer must have their own Ollama setup and access.

Start the backend from the backend directory:

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Backend:

http://localhost:8000

API documentation:

http://localhost:8000/docs
Datasets and RAG

The required datasets are included in the datasets/ directory and are used by the RAG pipeline for retrieving relevant cybersecurity evidence.

The current implementation includes:

NVD CVE data
CISA Known Exploited Vulnerabilities (KEV)
CERT-In advisories
CERT-In vulnerability documents

The datasets do not need to be downloaded separately for the current implementation.

Testing

Run the backend test suite:

python -m pytest

Run the end-to-end acceptance test:

python backend/acceptance_test.py

The integrated workflow has been verified across the frontend, FastAPI backend, fact-locking layer, RAG retrieval, Ollama generation, validation, and database persistence.

Important Notes
Do not commit .env files, API keys, passwords, or other secrets.
Do not commit node_modules/ or Python virtual environments.
Do not add AI model files to the repository.
Do not hardcode machine-specific file paths.
Ollama is an external dependency and must be configured separately on each developer's machine.
The existing datasets and RAG/database setup should not be deleted or replaced without coordinating with the team.
Keep new functionality integrated with the existing architecture rather than creating parallel implementations.