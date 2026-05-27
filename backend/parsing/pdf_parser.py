import re
import io
from datetime import datetime
from typing import List, Dict, Any
import pdfplumber

# Date pattern regex: matches e.g. 12/03/2026, 25-05-2026, 01 Jan 2026, 01-Jan-2026
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}|\d{1,2}[/\-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[/\-]\d{2,4})\b",
    re.IGNORECASE
)

# Number pattern: matches values with or without decimals, supporting Indian commas (e.g., 1,00,000.00, 2,500.00, 2500, 150)
AMOUNT_PATTERN = re.compile(r"(?<![\w\.])\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?(?![\w\.])")

def parse_date(date_str: str) -> datetime.date:
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
        "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%Y-%m-%d"
    ]
    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    try:
        # Fallback to dateutil/pandas if needed
        import pandas as pd
        return pd.to_datetime(cleaned).date()
    except Exception:
        raise ValueError(f"Unable to parse date: {date_str}")

def parse_pdf_statement(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Reads a PDF statement and extracts transaction entries using tables and line heuristics.
    """
    transactions = []
    
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # Method 1: Table Extraction (Sleeker and handles structured PDF grids)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Look for rows containing a date and an amount
                    row_str = " ".join([str(cell) for cell in row if cell is not None])
                    dates = DATE_PATTERN.findall(row_str)
                    amounts = AMOUNT_PATTERN.findall(row_str)
                    
                    if len(dates) >= 1 and len(amounts) >= 1:
                        # Clean and identify row cells
                        non_empty_cells = [str(c).strip() for c in row if c is not None and str(c).strip() != ""]
                        if len(non_empty_cells) >= 3:
                            # Let's map cells
                            # First cell is usually date
                            # Middle cell(s) is usually description
                            # Last one or two cells are debit/credit/balance
                            try:
                                date_val = parse_date(dates[0])
                                # Extract description: join cells that don't match dates or floats
                                desc_parts = []
                                numeric_vals = []
                                for cell in non_empty_cells:
                                    if DATE_PATTERN.search(cell):
                                        continue
                                    # If cell looks like float amount, clean currency symbols
                                    clean_cell = re.sub(r"[^\d.]", "", cell).strip()
                                    if re.match(r"^\d+(?:\.\d{1,2})?$", clean_cell) and clean_cell:
                                        numeric_vals.append(float(clean_cell))
                                    else:
                                        desc_parts.append(cell)
                                
                                desc = " ".join(desc_parts).strip()
                                if not desc:
                                    desc = "Bank Transaction"

                                # Determine amount and credit/debit
                                # Usually if there are multiple numbers: 
                                # Withdrawal, Deposit, Balance.
                                # Let's assume the first numeric is the transaction amount.
                                if numeric_vals:
                                    amount = numeric_vals[0]
                                    # Simple rule to identify debit vs credit:
                                    # If the description has "salary", "interest", "refund", "credit", "received", it's credit
                                    # Else debit. Or if there are two amounts and deposit is non-zero.
                                    tx_type = "debit"
                                    desc_lower = desc.lower()
                                    if any(k in desc_lower for k in ["salary", "interest", "refund", "credit", "received", "dep", "cr "]):
                                        tx_type = "credit"
                                    
                                    transactions.append({
                                        "date": date_val,
                                        "raw_description": desc,
                                        "amount": amount,
                                        "type": tx_type
                                    })
                            except Exception:
                                continue
            
            # Method 2: Fallback to Raw Text Extraction line-by-line
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split("\n"):
                dates = DATE_PATTERN.findall(line)
                amounts = AMOUNT_PATTERN.findall(line)
                
                # A valid row must contain a date and at least one decimal currency amount
                if len(dates) >= 1 and len(amounts) >= 1:
                    try:
                        date_val = parse_date(dates[0])
                        # Remove date and amounts from the line to extract the description
                        desc = line
                        for d in dates:
                            desc = desc.replace(d, "")
                        for a in amounts:
                            desc = desc.replace(a, "")
                        
                        # Clean description
                        desc = re.sub(r"\s+", " ", desc).strip()
                        desc = desc.strip(" -_/\\.*")
                        
                        # Extract amount (the first matching amount is typically the transaction value)
                        amount = float(amounts[0].replace(",", ""))
                        
                        # Detect credit/debit keywords in the line
                        tx_type = "debit"
                        line_lower = line.lower()
                        if "credit" in line_lower or "cr" in line_lower or "salary" in line_lower or "deposit" in line_lower or "interest" in line_lower:
                            tx_type = "credit"
                            
                        # Avoid duplicates from Method 1
                        is_duplicate = False
                        for t in transactions:
                            if t["date"] == date_val and abs(t["amount"] - amount) < 0.01 and t["raw_description"][:10] == desc[:10]:
                                is_duplicate = True
                                break
                                
                        if not is_duplicate and amount > 0:
                            transactions.append({
                                "date": date_val,
                                "raw_description": desc,
                                "amount": amount,
                                "type": tx_type
                            })
                    except Exception:
                        continue
                        
    return transactions
