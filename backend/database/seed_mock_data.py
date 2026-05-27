import random
from datetime import date, timedelta
from sqlalchemy.orm import Session
from backend.database.database import SessionLocal, Base, engine
from backend.models.models import Transaction, CategoryRule
from backend.cleaning.cleaner import clean_merchant_name
from backend.categorization.categorizer import categorize_transaction, ml_categorizer_instance

def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Check if transactions already exist
        if db.query(Transaction).count() > 0:
            print("Database already contains transaction data. Skipping seeding.")
            return

        print("Seeding database with 3 months of realistic mock financial data...")

        # Setup standard rules
        default_rules = [
            CategoryRule(pattern="Zomato", target_category="Food", priority=1),
            CategoryRule(pattern="Swiggy", target_category="Food", priority=1),
            CategoryRule(pattern="Starbucks", target_category="Food", priority=1),
            CategoryRule(pattern="Amazon", target_category="Shopping", priority=1),
            CategoryRule(pattern="Flipkart", target_category="Shopping", priority=1),
            CategoryRule(pattern="Myntra", target_category="Shopping", priority=1),
            CategoryRule(pattern="Uber", target_category="Travel", priority=1),
            CategoryRule(pattern="Ola", target_category="Travel", priority=1),
            CategoryRule(pattern="Netflix", target_category="Subscriptions", priority=1),
            CategoryRule(pattern="Spotify", target_category="Subscriptions", priority=1),
            CategoryRule(pattern="Youtube", target_category="Subscriptions", priority=1),
            CategoryRule(pattern="ChatGPT", target_category="Subscriptions", priority=1),
            CategoryRule(pattern="Electricity", target_category="Bills", priority=1),
            CategoryRule(pattern="Rent", target_category="Bills", priority=1),
            CategoryRule(pattern="Wifi", target_category="Bills", priority=1),
        ]
        
        # Merge standard rules
        for rule in default_rules:
            existing = db.query(CategoryRule).filter(CategoryRule.pattern == rule.pattern).first()
            if not existing:
                db.add(rule)
        db.commit()

        # Seed Transactions over Mar, Apr, May 2026
        today = date.today()
        start_date = today - timedelta(days=90)
        
        merchants = [
            # (Raw Description, Base Amount, Type, Category)
            ("SWIGGY LIMITED BLR", 350.0, "debit", "Food"),
            ("ZOMATO ONLINE DELIV", 480.0, "debit", "Food"),
            ("STARBUCKS COFFEE CON", 280.0, "debit", "Food"),
            ("MCDONALDS FAMILY REST", 450.0, "debit", "Food"),
            
            ("AMAZON INDIA PAYMT", 1200.0, "debit", "Shopping"),
            ("FLIPKART INTERNAT", 850.0, "debit", "Shopping"),
            ("MYNTRA FASHION RET", 1600.0, "debit", "Shopping"),
            
            ("UBER INDIA RIDES", 180.0, "debit", "Travel"),
            ("OLA CABS TAXI FARE", 220.0, "debit", "Travel"),
            ("SHELL PETROL STATION", 1500.0, "debit", "Travel"),
            
            ("NETFLIX CARD PAYMENT", 649.0, "debit", "Subscriptions"),
            ("SPOTIFY ONLINE MUSIC", 119.0, "debit", "Subscriptions"),
            ("CHATGPT PLUS SUB", 1999.0, "debit", "Subscriptions"),
            
            ("STATE GRID ELECTRICITY", 2200.0, "debit", "Bills"),
            ("ACT FIBERNET WIFIBILL", 999.0, "debit", "Bills"),
            
            ("PHARMACY APOLO HEALTH", 450.0, "debit", "Healthcare"),
            ("DR REDDYS MEDICAL CL", 800.0, "debit", "Healthcare"),
            
            ("P2P TRANSFER FRIEND", 500.0, "debit", "Transfers"),
        ]

        current_day = start_date
        while current_day <= today:
            # 1. Salary Credit on 1st of every month
            if current_day.day == 1:
                db.add(Transaction(
                    date=current_day,
                    raw_description="MOCK CORP SALARY CREDIT",
                    clean_description="Salary",
                    amount=85000.0,
                    type="credit",
                    category="Transfers",
                    confidence=1.0,
                    is_ai_categorized=False
                ))
            
            # 2. House Rent Debit on 3rd of every month
            if current_day.day == 3:
                db.add(Transaction(
                    date=current_day,
                    raw_description="APARTMENT OWNER RENT",
                    clean_description="House Rent",
                    amount=22000.0,
                    type="debit",
                    category="Bills",
                    confidence=1.0,
                    is_ai_categorized=False
                ))

            # 3. Random interest credit on 15th
            if current_day.day == 15:
                db.add(Transaction(
                    date=current_day,
                    raw_description="INTEREST PAID BY BANK",
                    clean_description="Interest Earned",
                    amount=1200.0,
                    type="credit",
                    category="Miscellaneous",
                    confidence=1.0,
                    is_ai_categorized=False
                ))

            # 4. Daily random spending (1 to 2 transactions per day with some gap days)
            if random.random() > 0.3:  # 70% chance of a transaction day
                num_txs = random.randint(1, 2)
                for _ in range(num_txs):
                    merchant = random.choice(merchants)
                    # Add minor random noise to amounts
                    amount = round(merchant[1] * random.uniform(0.8, 1.3), 2)
                    
                    clean_desc = clean_merchant_name(merchant[0])
                    # Run it through the categorizer logic to calculate confidence
                    category, confidence, is_ai = categorize_transaction(db, merchant[0], clean_desc)
                    
                    db.add(Transaction(
                        date=current_day,
                        raw_description=merchant[0],
                        clean_description=clean_desc,
                        amount=amount,
                        type=merchant[2],
                        category=category,
                        confidence=confidence,
                        is_ai_categorized=is_ai
                    ))
            
            current_day += timedelta(days=1)
            
        db.commit()
        print("Successfully seeded 3 months of mock transactions!")

        # Train ML model on the seeded database
        ml_categorizer_instance.train_model(db)
        print("ML models successfully fitted and operational.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
