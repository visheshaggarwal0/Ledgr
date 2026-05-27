import os
import re
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, Cookie
from sqlalchemy.orm import Session
import json

from backend.database.database import get_db
from backend.models.models import Transaction, CategoryRule, Config, TransactionResponse, CategoryRuleResponse, LoginRequest, QuickAddRequest, CategoryRuleCreate, TransactionCreate
from backend.parsing.parser import parse_csv_to_transactions
from backend.parsing.pdf_parser import parse_pdf_statement
from backend.cleaning.cleaner import clean_merchant_name
from backend.categorization.categorizer import categorize_transaction, ml_categorizer_instance, CATEGORIES
from backend.ml.predictor import get_predictions
from backend.insights.insights_engine import generate_insights

router = APIRouter()

# Password session token verification helper
SESSION_TOKEN = "ledgr_authenticated_session"

def verify_session(ledgr_session: Optional[str] = Cookie(None)):
    master_password = os.getenv("LEDGR_MASTER_PASSWORD", "")
    # If no password is set in .env, skip authentication
    if not master_password:
        return
    if ledgr_session != SESSION_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# --- AUTHENTICATION ---

@router.post("/auth/login")
def login(payload: LoginRequest, response: Response):
    master_password = os.getenv("LEDGR_MASTER_PASSWORD", "")
    if not master_password:
        # No password configured, allow login
        response.set_cookie(key="ledgr_session", value=SESSION_TOKEN, httponly=True, samesite="lax")
        return {"status": "success", "message": "No password required"}
        
    if payload.password == master_password:
        response.set_cookie(key="ledgr_session", value=SESSION_TOKEN, httponly=True, samesite="lax")
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Invalid password")

@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("ledgr_session")
    return {"status": "success"}

@router.get("/auth/check")
def check_auth(ledgr_session: Optional[str] = Cookie(None)):
    master_password = os.getenv("LEDGR_MASTER_PASSWORD", "")
    if not master_password:
        return {"authenticated": True, "password_required": False}
    return {"authenticated": ledgr_session == SESSION_TOKEN, "password_required": True}


# --- TRANSACTION UPLOAD & PARSING ---

def save_parsed_transactions(db: Session, parsed_txs: List[Dict], filename: str):
    new_txs = []
    for tx_data in parsed_txs:
        # Clean description
        clean_desc = clean_merchant_name(tx_data["raw_description"])
        
        # Categorize
        category, confidence, is_ai = categorize_transaction(db, tx_data["raw_description"], clean_desc)
        
        tx = Transaction(
            date=tx_data["date"],
            raw_description=tx_data["raw_description"],
            clean_description=clean_desc,
            amount=tx_data["amount"],
            type=tx_data["type"],
            category=category,
            confidence=confidence,
            is_ai_categorized=is_ai,
            source_file=filename,
            manual=False
        )
        db.add(tx)
        new_txs.append(tx)
        
    db.commit()
    # Retrain ML model since we have new data
    try:
        ml_categorizer_instance.train_model(db)
    except Exception:
        pass
    return len(new_txs)


@router.post("/upload", dependencies=[Depends(verify_session)])
async def upload_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    filename = file.filename or "statement"
    
    if filename.endswith(".csv"):
        parsed_txs, requires_map = parse_csv_to_transactions(contents)
        if requires_map:
            # We must return standard columns to let frontend map them
            import pandas as pd
            import io
            # Parse head of file to send columns to UI
            try:
                decoded = contents.decode("utf-8")
            except UnicodeDecodeError:
                decoded = contents.decode("latin-1")
            df = pd.read_csv(io.StringIO(decoded), nrows=5)
            return {
                "requires_mapping": True,
                "columns": list(df.columns),
                "sample_rows": df.head(3).to_dict(orient="records")
            }
        
        count = save_parsed_transactions(db, parsed_txs, filename)
        return {"status": "success", "imported_count": count}

    elif filename.endswith(".pdf"):
        parsed_txs = parse_pdf_statement(contents)
        count = save_parsed_transactions(db, parsed_txs, filename)
        return {"status": "success", "imported_count": count}
        
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a CSV or PDF.")


@router.post("/upload/map", dependencies=[Depends(verify_session)])
async def upload_with_mapping(
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    try:
        custom_mapping = json.loads(mapping_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid mapping JSON")
        
    parsed_txs, requires_map = parse_csv_to_transactions(contents, custom_mapping)
    if requires_map:
        raise HTTPException(status_code=400, detail="Mapping failed, unable to parse CSV rows.")
        
    count = save_parsed_transactions(db, parsed_txs, file.filename or "mapped_statement.csv")
    return {"status": "success", "imported_count": count}


# --- MANUAL TRANSACTION & QUICK-ADD ---

@router.post("/transactions", response_model=TransactionResponse, dependencies=[Depends(verify_session)])
def create_transaction(tx_in: TransactionCreate, db: Session = Depends(get_db)):
    # Create clean description
    clean_desc = clean_merchant_name(tx_in.raw_description)
    
    # Categorize
    category, confidence, is_ai = categorize_transaction(db, tx_in.raw_description, clean_desc)
    
    # If the user explicitly provided a category, use it instead of our prediction
    if tx_in.category and tx_in.category in CATEGORIES:
        category = tx_in.category
        confidence = 1.0
        is_ai = False

    tx = Transaction(
        date=tx_in.date,
        raw_description=tx_in.raw_description,
        clean_description=clean_desc,
        amount=tx_in.amount,
        type=tx_in.type,
        category=category,
        confidence=confidence,
        is_ai_categorized=is_ai,
        manual=True
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/transactions/quick-add", response_model=TransactionResponse, dependencies=[Depends(verify_session)])
def quick_add_transaction(payload: QuickAddRequest, db: Session = Depends(get_db)):
    """
    Parses a string command such as "₹250 groceries" or "1500 electricity bill debit"
    and adds the transaction.
    """
    query = payload.query.strip()
    
    # Heuristic Regex Parser:
    # 1. Match amount: looks for integers/floats, optionally preceded by ₹, Rs, INR and followed by suffixes like k, l, cr, m, b
    amount_match = re.search(r"(?:(?:₹|Rs\.?|INR)\s*)?(\d+(?:\.\d+)?)\s*(k|l|cr|m|b)?\b", query, re.IGNORECASE)
    if not amount_match:
        raise HTTPException(status_code=400, detail="Could not parse amount from input. Example: '₹250 groceries' or '1k food'")
        
    base_amount = float(amount_match.group(1))
    suffix = (amount_match.group(2) or "").lower()
    
    multiplier = 1
    if suffix == "k":
        multiplier = 1000
    elif suffix == "l":
        multiplier = 100000
    elif suffix == "cr":
        multiplier = 10000000
    elif suffix == "m":
        multiplier = 1000000
    elif suffix == "b":
        multiplier = 1000000000
        
    amount = base_amount * multiplier
    
    # 2. Extract description (everything except the amount and currency markers)
    desc = query.replace(amount_match.group(0), "").strip()
    
    # 3. Detect type
    tx_type = "debit"
    if "credit" in query.lower() or "received" in query.lower() or "income" in query.lower():
        tx_type = "credit"
        
    clean_desc = clean_merchant_name(desc or "Manual Expense")
    category, confidence, is_ai = categorize_transaction(db, desc, clean_desc)
    
    tx = Transaction(
        date=date.today(),
        raw_description=desc or "Quick Add",
        clean_description=clean_desc,
        amount=amount,
        type=tx_type,
        category=category,
        confidence=confidence,
        is_ai_categorized=is_ai,
        manual=True
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# --- GET TRANSACTIONS ---

@router.get("/transactions", response_model=List[TransactionResponse], dependencies=[Depends(verify_session)])
def get_transactions(
    category: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Transaction)
    if category:
        query = query.filter(Transaction.category == category)
    if type:
        query = query.filter(Transaction.type == type)
    if search:
        query = query.filter(
            (Transaction.raw_description.ilike(f"%{search}%")) | 
            (Transaction.clean_description.ilike(f"%{search}%"))
        )
        
    return query.order_by(Transaction.date.desc()).limit(limit).offset(offset).all()


@router.patch("/transactions/{tx_id}", response_model=TransactionResponse, dependencies=[Depends(verify_session)])
def update_transaction(
    tx_id: int,
    payload: dict,
    db: Session = Depends(get_db)
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if "category" in payload:
        new_category = payload["category"]
        if new_category not in CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        tx.category = new_category
        tx.is_ai_categorized = False
        tx.confidence = 1.0
        
        # Add a custom matching rule for this merchant automatically if one doesn't exist
        # to ensure future items automatically get this corrected category
        rule_exists = db.query(CategoryRule).filter(CategoryRule.pattern == tx.clean_description).first()
        if not rule_exists:
            new_rule = CategoryRule(pattern=tx.clean_description, target_category=new_category, priority=1)
            db.add(new_rule)

    if "clean_description" in payload:
        tx.clean_description = payload["clean_description"]
        
    db.commit()
    db.refresh(tx)
    
    # Retrain ML model since user edited category
    try:
        ml_categorizer_instance.train_model(db)
    except Exception:
        pass
        
    return tx


# --- DASHBOARD INSIGHTS & STATS ---

@router.get("/dashboard", dependencies=[Depends(verify_session)])
def get_dashboard_summary(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    
    total_income = sum(t.amount for t in transactions if t.type == "credit")
    total_expense = sum(t.amount for t in transactions if t.type == "debit")
    net_savings = total_income - total_expense
    
    # Category Breakdowns (debits only)
    category_summary = {}
    for cat in CATEGORIES:
        category_summary[cat] = 0.0
        
    for t in transactions:
        if t.type == "debit":
            category_summary[t.category] = category_summary.get(t.category, 0.0) + t.amount

    # Convert breakdown to a list of dicts for charting
    category_chart = [
        {"name": cat, "value": round(val, 2)}
        for cat, val in category_summary.items() if val > 0
    ]

    # Daily Cash Flow Chart (last 30 days)
    today = date.today()
    start_date = today - timedelta(days=30)
    recent_txs = db.query(Transaction).filter(Transaction.date >= start_date).all()
    
    daily_data = {}
    for i in range(31):
        d = start_date + timedelta(days=i)
        daily_data[d.strftime("%b %d")] = {"income": 0.0, "expense": 0.0}
        
    for t in recent_txs:
        date_str = t.date.strftime("%b %d")
        if date_str in daily_data:
            if t.type == "credit":
                daily_data[date_str]["income"] += t.amount
            else:
                daily_data[date_str]["expense"] += t.amount
                
    cashflow_chart = [
        {"name": d_str, "income": round(vals["income"], 2), "expense": round(vals["expense"], 2)}
        for d_str, vals in daily_data.items()
    ]

    # Dynamic Insights Feed
    insights = generate_insights(db)

    # ML Predictions
    predictions = get_predictions(db)

    return {
        "totals": {
            "income": round(total_income, 2),
            "expense": round(total_expense, 2),
            "net_savings": round(net_savings, 2)
        },
        "category_chart": category_chart,
        "cashflow_chart": cashflow_chart,
        "predictions": predictions,
        "insights": insights
    }


# --- CATEGORY RULES ENGINE ---

@router.get("/rules", response_model=List[CategoryRuleResponse], dependencies=[Depends(verify_session)])
def get_rules(db: Session = Depends(get_db)):
    return db.query(CategoryRule).order_by(CategoryRule.priority.desc()).all()

@router.post("/rules", response_model=CategoryRuleResponse, dependencies=[Depends(verify_session)])
def create_rule(payload: CategoryRuleCreate, db: Session = Depends(get_db)):
    # Check if duplicate rule pattern exists
    existing = db.query(CategoryRule).filter(CategoryRule.pattern == payload.pattern).first()
    if existing:
        existing.target_category = payload.target_category
        existing.priority = payload.priority
        db.commit()
        db.refresh(existing)
        return existing
        
    rule = CategoryRule(
        pattern=payload.pattern,
        target_category=payload.target_category,
        priority=payload.priority
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}", dependencies=[Depends(verify_session)])
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(CategoryRule).filter(CategoryRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"status": "success"}
