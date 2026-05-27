# Ledgr — AI-Powered Financial Insights Platform

Ledgr is a modern, lightweight, AI-powered financial insights and tracking platform. Instead of tedious manual ledger keeping, Ledgr parses your statements (PDF/CSV/Excel), normalizes description noise, automatically categorizes spending using a cascading Rules + Machine Learning engine, and projects your savings trajectory using linear regression models.

---

## ✨ Features

- **Multi-Format Ingestion**: Supports drag-and-drop parsing of PDF bank statements and CSV exports (like Google Pay, Paytm, and standard bank logs).
- **Interactive Mapping UI**: Automatically detects headers like Date, Description, and Amounts. If detection fails, a custom mapping interface allows manual matching.
- **Smart Description Cleaner**: Strips raw UPI transaction IDs, card swipe references, merchant codes, and converts noisy entries like `SWIGGY LIMITED BLR` to `Swiggy`.
- **Hybrid Categorization**:
  1. **Rules Engine**: Matches cleaned descriptors against user-defined regex/keyword rules.
  2. **ML Classifier**: Falls back to a Scikit-learn `MultinomialNB` model with confidence tags.
  3. **Overriding Feed**: Correcting a category on the UI instantly writes a database rule and triggers an online model retraining cycle.
- **Predictive Savings Engine**: Fits a scikit-learn `LinearRegression` model on historical months to project future months' cash flow, alongside daily run-rate burns.
- **AI Narrative Feed**: Analyzes metrics for warning alerts, weekend spending spikes, and recurring subscriptions.
- **Minimalist Design**: High-end light theme built with React, Vite, TS, and Tailwind CSS.
- **Single-User Lock Screen**: Secure environment-configured passcode gate.

---

## 📂 Project Architecture

```text
Ledgr/
├── backend/                # FastAPI Application Root
│   ├── api/                # Router controllers & password validation
│   │   └── routes.py
│   ├── parsing/            # CSV, Excel, and pdfplumber parsing engines
│   │   ├── parser.py
│   │   └── pdf_parser.py
│   ├── cleaning/           # Regex name normalization
│   │   └── cleaner.py
│   ├── categorization/     # Rules database & Scikit-learn pipeline
│   │   └── categorizer.py
│   ├── insights/           # Weekend spikes & recurring subscription analysis
│   │   └── insights_engine.py
│   ├── ml/                 # Linear regression predictions
│   │   └── predictor.py
│   ├── database/           # SQLite session engine and seeder script
│   │   ├── database.py
│   │   └── seed_mock_data.py
│   ├── models/             # SQLAlchemy ORM and Pydantic validation schemas
│   │   └── models.py
│   ├── main.py             # Server entrypoint
│   └── requirements.txt    # Backend dependencies
├── frontend/               # React + TypeScript + Vite Application
│   ├── src/
│   │   ├── App.tsx         # Main single-page application dashboard
│   │   ├── main.tsx        # React mounting entrypoint
│   │   └── index.css       # Tailwind CSS declarations
│   ├── tailwind.config.js  # Color tokens and design parameters
│   ├── vite.config.ts      # Proxy mapping configuration
│   └── package.json        # Frontend dependencies
└── README.md               # Documentation
```

---

## ⚡ How it Works (Categorization & Predictions)

### The Categorization Cascade
When a new transaction is processed, it flows through the following pipeline:
```
  [Raw Transaction] 
         │
         ▼
  [cleaner.py] ──► Normalizes description (e.g. "UPI-GPAY-ZOMATO..." -> "Zomato")
         │
         ▼
  [Rules Engine] ──► Checks regex keyword matches in DB (Priority 1)
         │
         ├─── (Match Found) ──► Category Assigned (100% confidence)
         │
         └─── (No Match) ──► [ML classifier] (TF-IDF + Naive Bayes)
                                     │
                                     ▼
                              Predicts category & assigns Confidence %
```

### Predictions Engine
- Fits a `LinearRegression` model using ordinal indices of monthly debit/credit aggregates as features ($X$), predicting next month's totals.
- Scales the current month's transactions by a velocity multiplier: $\text{Projected Spend} = \text{Current Spend} \times (\text{Days in Month} / \text{Current Day})$ to display a real-time progress budget warning.

---

## 🚀 Quick Start Instructions

### 1. Backend Setup
1. Navigate to the project root and install requirements:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Populate the SQLite database with 3 months of mock credit/debit data to test the charts:
   ```bash
   python -m backend.database.seed_mock_data
   ```
3. Run the FastAPI development server:
   ```bash
   uvicorn backend.main:app --reload
   ```
*The API is now running on `http://127.0.0.1:8000`.*

### 2. Frontend Setup
1. In a new terminal window, navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Launch the Vite dev server:
   ```bash
   npm run dev
   ```
*Vite will start the client on `http://localhost:5173`. Open it, and enter the default password:* **`ledgrpass`**.

---

## 🔑 Environment Variables
Configure backend auth settings in `backend/.env`:
```env
LEDGR_MASTER_PASSWORD=ledgrpass
```
If `LEDGR_MASTER_PASSWORD` is left empty, session verification is bypassed (useful for local offline environments).
