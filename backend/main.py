import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database.database import Base, engine, SessionLocal
from backend.api.routes import router
from backend.models.models import CategoryRule
from backend.categorization.categorizer import ml_categorizer_instance

# Make sure tables are created
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ledgr API",
    description="Modern AI-Powered Financial Insights Engine",
    version="1.0.0"
)

# CORS Middleware (React + Vite dev server defaults to port 5173 or 5174)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed database with initial default rules if none exist
def seed_default_rules():
    db = SessionLocal()
    try:
        if db.query(CategoryRule).count() == 0:
            default_rules = [
                # Food
                CategoryRule(pattern="Zomato", target_category="Food", priority=1),
                CategoryRule(pattern="Swiggy", target_category="Food", priority=1),
                CategoryRule(pattern="Starbucks", target_category="Food", priority=1),
                CategoryRule(pattern="McDonalds", target_category="Food", priority=1),
                CategoryRule(pattern="Burger King", target_category="Food", priority=1),
                CategoryRule(pattern="Groceries", target_category="Food", priority=1),
                # Shopping
                CategoryRule(pattern="Amazon", target_category="Shopping", priority=1),
                CategoryRule(pattern="Flipkart", target_category="Shopping", priority=1),
                CategoryRule(pattern="Myntra", target_category="Shopping", priority=1),
                CategoryRule(pattern="Decathlon", target_category="Shopping", priority=1),
                # Travel
                CategoryRule(pattern="Uber", target_category="Travel", priority=1),
                CategoryRule(pattern="Ola", target_category="Travel", priority=1),
                CategoryRule(pattern="Irctc", target_category="Travel", priority=1),
                CategoryRule(pattern="Petrol", target_category="Travel", priority=1),
                CategoryRule(pattern="Fuel", target_category="Travel", priority=1),
                # Subscriptions
                CategoryRule(pattern="Netflix", target_category="Subscriptions", priority=1),
                CategoryRule(pattern="Spotify", target_category="Subscriptions", priority=1),
                CategoryRule(pattern="Youtube", target_category="Subscriptions", priority=1),
                CategoryRule(pattern="ChatGPT", target_category="Subscriptions", priority=1),
                # Bills
                CategoryRule(pattern="Electricity", target_category="Bills", priority=1),
                CategoryRule(pattern="Rent", target_category="Bills", priority=1),
                CategoryRule(pattern="Wifi", target_category="Bills", priority=1),
                CategoryRule(pattern="Broadband", target_category="Bills", priority=1),
            ]
            db.bulk_save_objects(default_rules)
            db.commit()
            print("Successfully seeded default categorization rules.")
            
        # Bootstrap ML Model training from current database
        ml_categorizer_instance.train_model(db)
    except Exception as e:
        print(f"Error during bootstrap: {e}")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    seed_default_rules()

app.include_router(router, prefix="/api")

@app.get("/")
def read_root():
    return {"app": "Ledgr", "status": "operational"}
