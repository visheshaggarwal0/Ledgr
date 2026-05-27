from datetime import date
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, Date
from pydantic import BaseModel
from backend.database.database import Base

# --- SQLAlchemy Models ---

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    raw_description = Column(String, nullable=False)
    clean_description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # "debit" or "credit"
    category = Column(String, nullable=False, default="Miscellaneous")
    confidence = Column(Float, nullable=False, default=1.0)
    is_ai_categorized = Column(Boolean, nullable=False, default=False)
    source_file = Column(String, nullable=True)
    manual = Column(Boolean, nullable=False, default=False)


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, unique=True, nullable=False)
    target_category = Column(String, nullable=False)
    priority = Column(Integer, default=0)


class Config(Base):
    __tablename__ = "configs"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)


# --- Pydantic Schemas ---

class TransactionBase(BaseModel):
    date: date
    raw_description: str
    amount: float
    type: str  # "debit" or "credit"
    category: str = "Miscellaneous"

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    clean_description: Optional[str] = None
    amount: Optional[float] = None
    type: Optional[str] = None

class TransactionResponse(TransactionBase):
    id: int
    clean_description: str
    confidence: float
    is_ai_categorized: bool
    source_file: Optional[str] = None
    manual: bool

    class Config:
        from_attributes = True


class CategoryRuleCreate(BaseModel):
    pattern: str
    target_category: str
    priority: int = 0

class CategoryRuleResponse(CategoryRuleCreate):
    id: int

    class Config:
        from_attributes = True


class QuickAddRequest(BaseModel):
    query: str


class LoginRequest(BaseModel):
    password: str
