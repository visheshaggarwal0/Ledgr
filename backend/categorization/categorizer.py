import re
from typing import Tuple, List
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from backend.models.models import CategoryRule, Transaction
from backend.cleaning.cleaner import clean_merchant_name

# Core categories
CATEGORIES = [
    "Food",
    "Shopping",
    "Bills",
    "Entertainment",
    "Travel",
    "Healthcare",
    "Subscriptions",
    "Transfers",
    "Miscellaneous"
]

# Seed training data to boot up the ML model immediately without empty dataset errors
SEED_TRAINING_DATA = [
    # Food
    ("swiggy", "Food"), ("zomato", "Food"), ("starbucks", "Food"), ("mcdonalds", "Food"),
    ("burger king", "Food"), ("groceries superstore", "Food"), ("fresh vegetables market", "Food"),
    ("restaurant dining", "Food"), ("pizza hut", "Food"), ("bakery", "Food"),
    # Shopping
    ("amazon prime delivery", "Shopping"), ("flipkart order", "Shopping"), ("myntra fashion", "Shopping"),
    ("decathlon sports", "Shopping"), ("clothing apparel", "Shopping"), ("shoe palace", "Shopping"),
    ("electronic store gadgets", "Shopping"), ("retail department store", "Shopping"),
    # Bills
    ("electricity bill payment", "Bills"), ("water utility supply", "Bills"), ("broadband wifi recharge", "Bills"),
    ("mobile post paid bill", "Bills"), ("house rent transfer", "Bills"), ("insurance premium", "Bills"),
    ("piped gas utility", "Bills"),
    # Entertainment
    ("netflix com monthly subscription", "Entertainment"), ("spotify premium music", "Entertainment"),
    ("movie tickets cinema", "Entertainment"), ("bookmyshow event", "Entertainment"), ("gaming arcade play", "Entertainment"),
    ("playstation network purchase", "Entertainment"), ("bowling alley", "Entertainment"),
    # Travel
    ("uber ride trip", "Travel"), ("ola cabs city taxi", "Travel"), ("irctc railway ticket", "Travel"),
    ("indigo airlines flight", "Travel"), ("fuel station petrol pump", "Travel"), ("metro smart card recharge", "Travel"),
    ("hotel stay booking", "Travel"),
    # Healthcare
    ("pharmacy medical store", "Healthcare"), ("hospital consultation doctor", "Healthcare"),
    ("diagnostic lab tests", "Healthcare"), ("health insurance copay", "Healthcare"), ("dental clinic", "Healthcare"),
    # Subscriptions
    ("youtube premium", "Subscriptions"), ("chatgpt plus subscription", "Subscriptions"), ("github co pilot subscription", "Subscriptions"),
    ("adobe creative cloud", "Subscriptions"), ("newspaper subscription monthly", "Subscriptions"),
    # Transfers
    ("transfer to friend self", "Transfers"), ("p2p transfer bank", "Transfers"), ("wallet load credit", "Transfers"),
    ("payment to self account", "Transfers")
]

class MLCategorizer:
    def __init__(self):
        self.pipeline = Pipeline([
            ('vectorizer', TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
            ('classifier', MultinomialNB(alpha=0.1))
        ])
        self.is_trained = False
        self._bootstrap_model()

    def _bootstrap_model(self):
        """Trains the initial model with the seed data."""
        X = [item[0] for item in SEED_TRAINING_DATA]
        y = [item[1] for item in SEED_TRAINING_DATA]
        self.pipeline.fit(X, y)
        self.is_trained = True

    def train_model(self, db: Session):
        """Retrains the model with seed data + database transactions."""
        # Query all transactions that have a category
        db_transactions = db.query(Transaction).all()
        
        X = [item[0] for item in SEED_TRAINING_DATA]
        y = [item[1] for item in SEED_TRAINING_DATA]

        for tx in db_transactions:
            # We train on both raw and clean descriptions to increase vocabulary coverage
            if tx.category and tx.category in CATEGORIES:
                X.append(tx.raw_description.lower())
                y.append(tx.category)
                if tx.clean_description:
                    X.append(tx.clean_description.lower())
                    y.append(tx.category)

        if X:
            self.pipeline.fit(X, y)
            self.is_trained = True

    def predict(self, text: str) -> Tuple[str, float]:
        """Predicts the category and returns (category, confidence)."""
        if not self.is_trained:
            return "Miscellaneous", 1.0
        
        # Predict probability
        probs = self.pipeline.predict_proba([text.lower()])[0]
        classes = self.pipeline.classes_
        
        max_idx = probs.argmax()
        pred_class = classes[max_idx]
        confidence = float(probs[max_idx])
        
        # If low confidence, fallback to Miscellaneous
        if confidence < 0.3:
            return "Miscellaneous", confidence
            
        return pred_class, confidence

# Global ML categorizer instance
ml_categorizer_instance = MLCategorizer()

def categorize_transaction(db: Session, raw_desc: str, clean_desc: str) -> Tuple[str, float, bool]:
    """
    Categorizes a transaction.
    Returns (category, confidence, is_ai_categorized)
    """
    # 1. Rules-based engine
    rules = db.query(CategoryRule).order_by(CategoryRule.priority.desc()).all()
    
    # Check raw and clean descriptions against regex rules
    for rule in rules:
        try:
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            if pattern.search(raw_desc) or pattern.search(clean_desc):
                return rule.target_category, 1.0, False  # Explicit rule match
        except re.error:
            continue

    # 2. ML Classifier fallback
    category, confidence = ml_categorizer_instance.predict(clean_desc)
    return category, confidence, True
