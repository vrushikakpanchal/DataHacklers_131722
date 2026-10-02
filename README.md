# GenAI SIH 2026 - Content Transformation Engine

An AI-powered multi-artifact content transformation and intelligence platform developed for **SIH 2026**.

This repository integrates local generative models (via Ollama/FastAPI) with standalone module components, dataset adapters, and a web-based frontend interface.

---

## 📁 Repository Structure

```text
sih_content_transform/
├── html_frontend/                  # Web Interface (HTML, CSS, JavaScript)
├── my_code/                        # Main Integrated Engine
│   ├── apps/
│   │   └── api.py                 # FastAPI Application Server
│   └── modules/
│       ├── generators.py          # AI Content Generation Engines
│       └── analyzer.py            # Transformation & Pipeline Logic
├── ishita_code/                    # Shared Threat Intel & Datasets
│   ├── backend/data/              # Active Threat Store (threat_intel_store.json)
│   └── datasets/                   # Sample Evidence Files & Datasets (.pdf, .csv)
├── pallavi_code/                   # Shared Adapter Generators & Validators
│   ├── generator.py
│   └── validator.py
├── data/                           # Runtime Output Storage & Assets
├── requirements.txt                # Python Dependencies
└── README.md                       # Documentation & Setup Guide
