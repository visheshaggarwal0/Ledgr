import numpy as np
import pandas as pd
from datetime import datetime, date
from sklearn.linear_model import LinearRegression
from sqlalchemy.orm import Session
from backend.models.models import Transaction

def get_predictions(db: Session) -> dict:
    """
    Computes spending and savings forecasts.
    Returns a dictionary of current-month forecast and next-month ML projections.
    """
    # 1. Fetch all transactions
    transactions = db.query(Transaction).all()
    if not transactions:
        return {
            "has_data": False,
            "projected_spend": 0.0,
            "projected_savings": 0.0,
            "savings_change_pct": 0.0,
            "forecast_chart": []
        }

    # Convert to pandas DataFrame for quick aggregation
    data = []
    for tx in transactions:
        data.append({
            "date": tx.date,
            "amount": tx.amount,
            "type": tx.type,  # "debit" or "credit"
            "month_str": tx.date.strftime("%Y-%m")
        })
    
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])

    # Monthly aggregation
    monthly_data = []
    grouped = df.groupby("month_str")
    
    for month, group in grouped:
        income = group[group["type"] == "credit"]["amount"].sum()
        spending = group[group["type"] == "debit"]["amount"].sum()
        savings = income - spending
        monthly_data.append({
            "month": month,
            "income": float(income),
            "spending": float(spending),
            "savings": float(savings)
        })

    # Sort months chronologically
    monthly_data = sorted(monthly_data, key=lambda x: x["month"])
    
    # Calculate current month's velocity projection
    today = date.today()
    current_month_str = today.strftime("%Y-%m")
    
    current_month_tx = df[df["month_str"] == current_month_str]
    current_spend = current_month_tx[current_month_tx["type"] == "debit"]["amount"].sum()
    current_income = current_month_tx[current_month_tx["type"] == "credit"]["amount"].sum()
    
    # Simple linear extrapolation for the current month
    day_of_month = today.day
    # Get total days in current month
    import calendar
    total_days = calendar.monthrange(today.year, today.month)[1]
    
    scale_factor = total_days / max(day_of_month, 1)
    projected_spend = float(current_spend * scale_factor)
    projected_income = float(current_income * scale_factor)
    projected_savings = projected_income - projected_spend

    # ML Linear Regression for next month (requires at least 2 historical months)
    next_month_spend_pred = projected_spend
    next_month_savings_pred = projected_savings
    
    has_ml = len(monthly_data) >= 2
    
    if has_ml:
        # Prepare regression X (index of months) and y (spending, savings)
        X = np.arange(len(monthly_data)).reshape(-1, 1)
        y_spend = np.array([m["spending"] for m in monthly_data])
        y_save = np.array([m["savings"] for m in monthly_data])
        
        # Fit spending model
        model_spend = LinearRegression()
        model_spend.fit(X, y_spend)
        
        # Fit savings model
        model_save = LinearRegression()
        model_save.fit(X, y_save)
        
        # Predict for next index
        next_idx = np.array([[len(monthly_data)]])
        next_month_spend_pred = float(max(model_spend.predict(next_idx)[0], 0))
        next_month_savings_pred = float(model_save.predict(next_idx)[0])

    # Construct the chart data including historical, current, and predicted
    forecast_chart = []
    for m in monthly_data:
        forecast_chart.append({
            "name": m["month"],
            "spending": m["spending"],
            "savings": m["savings"],
            "type": "Historical"
        })
        
    # Append prediction
    next_month_date = today + pd.DateOffset(months=1)
    next_month_str = next_month_date.strftime("%Y-%m")
    
    forecast_chart.append({
        "name": next_month_str + " (Est)",
        "spending": round(next_month_spend_pred, 2),
        "savings": round(next_month_savings_pred, 2),
        "type": "Forecast"
    })

    # Compare projected savings with last month's actual savings (if available)
    savings_change_pct = 0.0
    if len(monthly_data) >= 1:
        # find last month
        last_month_actual = monthly_data[-1]["savings"]
        if last_month_actual != 0:
            savings_change_pct = ((projected_savings - last_month_actual) / abs(last_month_actual)) * 100

    return {
        "has_data": True,
        "projected_spend": round(projected_spend, 2),
        "projected_savings": round(projected_savings, 2),
        "savings_change_pct": round(savings_change_pct, 1),
        "next_month_predicted_spend": round(next_month_spend_pred, 2),
        "next_month_predicted_savings": round(next_month_savings_pred, 2),
        "forecast_chart": forecast_chart
    }
