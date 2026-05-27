import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from backend.models.models import Transaction

def generate_insights(db: Session) -> list:
    """
    Scans the transactions and returns a list of dynamic insight dictionaries:
    [
      { "id": "weekend_spike", "type": "warning" | "info" | "success", "title": "...", "text": "..." },
      ...
    ]
    """
    transactions = db.query(Transaction).all()
    if len(transactions) < 5:
        return [
            {
                "id": "welcome",
                "type": "info",
                "title": "Welcome to Ledgr",
                "text": "Upload bank statements or log manual transactions to see deep, personalized insights here."
            }
        ]

    # Load into pandas for easier analytical groupings
    data = []
    for tx in transactions:
        data.append({
            "date": tx.date,
            "amount": tx.amount,
            "type": tx.type,
            "category": tx.category,
            "day_of_week": tx.date.weekday(),  # 0=Monday, 6=Sunday
            "month_str": tx.date.strftime("%Y-%m")
        })
        
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])

    insights = []

    # 1. Active Subscriptions Insight
    subs_df = df[(df["category"] == "Subscriptions") & (df["type"] == "debit")]
    if not subs_df.empty:
        # Sum spending in the most recent month for subscriptions
        latest_month = subs_df["month_str"].max()
        subs_latest = subs_df[subs_df["month_str"] == latest_month]
        total_subs = subs_latest["amount"].sum()
        
        if total_subs > 0:
            insights.append({
                "id": "subscriptions_total",
                "type": "info",
                "title": "Recurring Subscriptions",
                "text": f"You spent ₹{total_subs:,.2f} on active subscriptions in {latest_month}. Ensure you use all of them!"
            })

    # 2. MoM Food Spend Check
    food_df = df[(df["category"] == "Food") & (df["type"] == "debit")]
    if not food_df.empty:
        # Group by month
        monthly_food = food_df.groupby("month_str")["amount"].sum()
        if len(monthly_food) >= 2:
            sorted_months = sorted(monthly_food.index)
            latest_m = sorted_months[-1]
            prev_m = sorted_months[-2]
            
            latest_val = monthly_food[latest_m]
            prev_val = monthly_food[prev_m]
            
            if prev_val > 0:
                diff_pct = ((latest_val - prev_val) / prev_val) * 100
                if diff_pct > 15:
                    insights.append({
                        "id": "food_spend_increase",
                        "type": "warning",
                        "title": "Food Spend Spike",
                        "text": f"Your food spending increased by {diff_pct:.1f}% this month (₹{latest_val:,.2f}) compared to last month (₹{prev_val:,.2f})."
                    })
                elif diff_pct < -15:
                    insights.append({
                        "id": "food_spend_decrease",
                        "type": "success",
                        "title": "Food Savings",
                        "text": f"Nice! Your food spending decreased by {abs(diff_pct):.1f}% this month compared to last month."
                    })

    # 3. Weekend Spending Spikes (Saturday=5, Sunday=6)
    debits_df = df[df["type"] == "debit"]
    if len(debits_df) > 10:
        weekend_spend = debits_df[debits_df["day_of_week"].isin([5, 6])]["amount"].sum()
        total_debits = debits_df["amount"].sum()
        
        if total_debits > 0:
            weekend_pct = (weekend_spend / total_debits) * 100
            if weekend_pct > 40:
                insights.append({
                    "id": "weekend_spike",
                    "type": "warning",
                    "title": "Weekend Spending Spike",
                    "text": f"Weekend purchases account for {weekend_pct:.1f}% of your total monthly expenditures."
                })

    # 4. Cash Flow & Burn Rate Warning
    latest_month = df["month_str"].max()
    month_df = df[df["month_str"] == latest_month]
    month_debit = month_df[month_df["type"] == "debit"]["amount"].sum()
    month_credit = month_df[month_df["type"] == "credit"]["amount"].sum()
    
    if month_credit > 0:
        burn_rate = (month_debit / month_credit) * 100
        if burn_rate > 90:
            insights.append({
                "id": "high_burn_rate",
                "type": "warning",
                "title": "High Burn Rate",
                "text": f"You have spent {burn_rate:.1f}% of your earnings this month. Consider cutting discretionary spending."
            })
        elif burn_rate < 50:
            insights.append({
                "id": "healthy_savings",
                "type": "success",
                "title": "Excellent Savings Rate",
                "text": f"You saved {(100 - burn_rate):.1f}% of your income so far this month. Keep it up!"
            })

    # Default fallback if there aren't many insights yet
    if not insights:
        insights.append({
            "id": "on_track",
            "type": "success",
            "title": "All Clean!",
            "text": "Your budget allocations and monthly spend metrics are well within safe thresholds."
        })

    return insights
