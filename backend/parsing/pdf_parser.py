import re
import io
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import pypdf
import pdfplumber
import pandas as pd

class PasswordRequiredException(Exception):
    pass

class IncorrectPasswordException(Exception):
    pass

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
        return pd.to_datetime(cleaned).date()
    except Exception:
        raise ValueError(f"Unable to parse date: {date_str}")

def parse_pdf_statement(file_bytes: bytes, password: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Reads a PDF statement and extracts transaction entries using tables and line heuristics.
    Detects GPAY or SBI structures automatically and applies specific parsers.
    """
    # 1. Check if the PDF is encrypted
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        is_encrypted = reader.is_encrypted
    except Exception:
        is_encrypted = False

    if is_encrypted:
        if not password:
            raise PasswordRequiredException("Password required for encrypted PDF.")
        try:
            success = reader.decrypt(password)
            if not success:
                raise IncorrectPasswordException("Incorrect password for PDF.")
        except Exception:
            raise IncorrectPasswordException("Incorrect password for PDF.")

    # 2. Extract first page text to auto-differentiate formats
    first_page_text = ""
    try:
        # Re-initialize reader to ensure fresh state after decryption
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        if is_encrypted:
            reader.decrypt(password)
        first_page_text = reader.pages[0].extract_text() or ""
    except Exception:
        pass

    # Unique keywords
    is_gpay = "Transaction statement" in first_page_text or "Google Pay" in first_page_text or "UPI Transaction ID" in first_page_text
    is_sbi = "State Bank of India" in first_page_text or "STATEMENT OF ACCOUNT" in first_page_text or "Savings Account" in first_page_text

    if is_gpay:
        return _parse_gpay_pdf(reader)
    elif is_sbi:
        return _parse_sbi_pdf(file_bytes, password)
    else:
        return _parse_generic_pdf(file_bytes, password)

def _parse_gpay_pdf(reader: pypdf.PdfReader) -> List[Dict[str, Any]]:
    transactions = []
    DATE_RE = re.compile(r"^\d{1,2} [A-Za-z]{3}, \d{4}$")
    TIME_RE = re.compile(r"^\d{1,2}:\d{2} [AP]M$")
    
    all_lines = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            page_lines = [l.strip() for l in text.split("\n") if l.strip()]
            all_lines.extend(page_lines)
            
    i = 0
    while i < len(all_lines) - 5:
        # Check for Date and Time pattern starting a block
        if DATE_RE.match(all_lines[i]) and TIME_RE.match(all_lines[i+1]):
            date_str = all_lines[i]
            time_str = all_lines[i+1]
            desc = all_lines[i+2]
            upi_id = all_lines[i+3]
            payment_info = all_lines[i+4]
            amount_str = all_lines[i+5]
            
            # Verify amount line
            if "₹" in amount_str:
                try:
                    dt = datetime.strptime(date_str, "%d %b, %Y").date()
                except Exception:
                    try:
                        dt = pd.to_datetime(date_str).date()
                    except Exception:
                        dt = date.today()
                        
                amount_cleaned = amount_str.replace("₹", "").replace(",", "").strip()
                try:
                    amount = float(amount_cleaned)
                except ValueError:
                    amount = 0.0
                    
                tx_type = "debit"
                desc_lower = desc.lower()
                if "received from" in desc_lower:
                    tx_type = "credit"
                elif "top-up to" in desc_lower:
                    tx_type = "debit"
                elif "paid to" in desc_lower:
                    tx_type = "debit"
                else:
                    pay_lower = payment_info.lower()
                    if "paid to" in pay_lower:
                        tx_type = "credit"
                    elif "paid by" in pay_lower:
                        tx_type = "debit"
                
                if amount > 0:
                    transactions.append({
                        "date": dt,
                        "raw_description": f"{desc} ({upi_id})",
                        "amount": amount,
                        "type": tx_type
                    })
                i += 6
                continue
        i += 1
    return transactions

def _parse_sbi_pdf(file_bytes: bytes, password: Optional[str] = None) -> List[Dict[str, Any]]:
    transactions = []
    DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    
    with pdfplumber.open(io.BytesIO(file_bytes), password=password) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if len(row) < 7:
                        continue
                    
                    post_date = (row[0] or "").strip()
                    narration = (row[2] or "").strip()
                    debit = (row[4] or "").strip()
                    credit = (row[5] or "").strip()
                    
                    if not DATE_RE.match(post_date):
                        continue
                        
                    debit_val = 0.0
                    credit_val = 0.0
                    is_debit = False
                    is_credit = False
                    
                    if debit and debit != "-":
                        try:
                            debit_val = float(debit.replace(",", "").strip())
                            if debit_val > 0:
                                is_debit = True
                        except ValueError:
                            pass
                            
                    if credit and credit != "-":
                        try:
                            credit_val = float(credit.replace(",", "").strip())
                            if credit_val > 0:
                                is_credit = True
                        except ValueError:
                            pass
                            
                    if not is_debit and not is_credit:
                        continue
                        
                    try:
                        dt = datetime.strptime(post_date, "%d/%m/%Y").date()
                    except Exception:
                        continue
                        
                    amount = debit_val if is_debit else credit_val
                    tx_type = "debit" if is_debit else "credit"
                    clean_narration = re.sub(r"\s+", " ", narration).strip()
                    
                    transactions.append({
                        "date": dt,
                        "raw_description": clean_narration,
                        "amount": amount,
                        "type": tx_type
                    })
    return transactions

def _parse_generic_pdf(file_bytes: bytes, password: Optional[str] = None) -> List[Dict[str, Any]]:
    transactions = []
    with pdfplumber.open(io.BytesIO(file_bytes), password=password) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    row_str = " ".join([str(cell) for cell in row if cell is not None])
                    dates = DATE_PATTERN.findall(row_str)
                    amounts = AMOUNT_PATTERN.findall(row_str)
                    
                    if len(dates) >= 1 and len(amounts) >= 1:
                        non_empty_cells = [str(c).strip() for c in row if c is not None and str(c).strip() != ""]
                        if len(non_empty_cells) >= 3:
                            try:
                                date_val = parse_date(dates[0])
                                desc_parts = []
                                numeric_vals = []
                                for cell in non_empty_cells:
                                    if DATE_PATTERN.search(cell):
                                        continue
                                    clean_cell = re.sub(r"[^\d.]", "", cell).strip()
                                    if re.match(r"^\d+(?:\.\d{1,2})?$", clean_cell) and clean_cell:
                                        numeric_vals.append(float(clean_cell))
                                    else:
                                        desc_parts.append(cell)
                                
                                desc = " ".join(desc_parts).strip()
                                if not desc:
                                    desc = "Bank Transaction"

                                if numeric_vals:
                                    amount = numeric_vals[0]
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
            
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split("\n"):
                dates = DATE_PATTERN.findall(line)
                amounts = AMOUNT_PATTERN.findall(line)
                
                if len(dates) >= 1 and len(amounts) >= 1:
                    try:
                        date_val = parse_date(dates[0])
                        desc = line
                        for d in dates:
                            desc = desc.replace(d, "")
                        for a in amounts:
                            desc = desc.replace(a, "")
                        
                        desc = re.sub(r"\s+", " ", desc).strip()
                        desc = desc.strip(" -_/\\.*")
                        amount = float(amounts[0].replace(",", ""))
                        
                        tx_type = "debit"
                        line_lower = line.lower()
                        if "credit" in line_lower or "cr" in line_lower or "salary" in line_lower or "deposit" in line_lower or "interest" in line_lower:
                            tx_type = "credit"
                            
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
