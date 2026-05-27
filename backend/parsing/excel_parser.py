import io
import re
import pandas as pd
import msoffcrypto
from datetime import datetime, date
from typing import List, Dict, Any, Optional

class PasswordRequiredException(Exception):
    pass

class IncorrectPasswordException(Exception):
    pass

# Date pattern: DD/MM/YYYY or DD-MM-YYYY
DATE_RE = re.compile(r"^\d{2}[/\-]\d{2}[/\-]\d{4}$")

def parse_excel_statement(file_bytes: bytes, password: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses an Excel bank statement, decrypting it first if it is password-protected.
    """
    file_bytes_io = io.BytesIO(file_bytes)
    
    # 1. Detect encryption and decrypt if necessary
    try:
        office_file = msoffcrypto.OfficeFile(file_bytes_io)
        is_encrypted = office_file.is_encrypted()
    except Exception:
        # If msoffcrypto fails to inspect, it's typically an unencrypted zip/xlsx file
        is_encrypted = False
        
    if is_encrypted:
        if not password:
            raise PasswordRequiredException("Password required for encrypted Excel file.")
            
        decrypted = io.BytesIO()
        try:
            file_bytes_io.seek(0)
            office_file = msoffcrypto.OfficeFile(file_bytes_io)
            office_file.load_key(password=password)
            office_file.decrypt(decrypted)
        except Exception:
            raise IncorrectPasswordException("Incorrect password for Excel file.")
            
        decrypted.seek(0)
        df = pd.read_excel(decrypted, header=None)
    else:
        file_bytes_io.seek(0)
        try:
            df = pd.read_excel(file_bytes_io, header=None)
        except Exception as e:
            raise ValueError(f"Failed to load Excel file: {e}")

    # 2. Identify the structure of the Excel statement
    # We will search for headers (Date, Description/Details, Debit, Credit, Balance)
    header_idx = -1
    is_sbi = False
    
    for idx, row in df.iterrows():
        row_str = " ".join([str(c).strip().lower() for c in row if pd.notna(c)])
        if "state bank of india" in row_str or "sbi" in row_str:
            is_sbi = True
        if "date" in row_str and ("details" in row_str or "description" in row_str) and "balance" in row_str:
            header_idx = idx
            break
            
    if header_idx == -1:
        # If we can't find header row, search for any row containing Date & Balance
        for idx, row in df.iterrows():
            row_str = " ".join([str(c).strip().lower() for c in row if pd.notna(c)])
            if "date" in row_str and "balance" in row_str:
                header_idx = idx
                break

    if header_idx == -1:
        # Fallback to index 17 if we still can't find it
        header_idx = 17 if len(df) > 17 else 0

    transactions = []
    
    # 3. Parse rows starting after the header
    for idx, row in df.iloc[header_idx + 1:].iterrows():
        # Clean first column value
        first_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        
        # Stop parsing when hitting SBI footer summary or general empty footer sections
        if "statement summary" in first_val.lower() or "brought forward" in first_val.lower() or "please do not share" in first_val.lower():
            break
            
        # Parse date from first column
        date_str = first_val
        if not date_str or not DATE_RE.match(date_str):
            # Check if it has date but in different format or is nan
            continue
            
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%d-%m-%Y").date()
            except ValueError:
                # Skip invalid date rows
                continue

        # Extract details (narration / description)
        narration = ""
        # Look for details column: usually index 1
        if len(row) > 1 and pd.notna(row.iloc[1]):
            narration = str(row.iloc[1]).strip()
            
        # Clean narration
        clean_narration = re.sub(r"\s+", " ", narration).strip()
        if not clean_narration:
            clean_narration = "Excel Transaction"
            
        # Extract Debit and Credit
        # For SBI: column index 3 is Debit, index 4 is Credit
        # Let's inspect columns dynamically or use index heuristics:
        # Usually Debit is in 3rd/4th col, Credit is in 4th/5th col.
        debit_val = 0.0
        credit_val = 0.0
        is_debit = False
        is_credit = False
        
        # Heuristics:
        # Look at cols 2, 3, 4, 5
        cols_to_check = list(range(2, min(6, len(row))))
        
        # Let's assume indices 3 and 4 are Debit and Credit for SBI
        # For generic Excel, we look for numerical values that are not the balance (which is usually the last col)
        # Let's check index 3 and 4 first
        debit_raw = row.iloc[3] if len(row) > 3 else None
        credit_raw = row.iloc[4] if len(row) > 4 else None
        
        if pd.notna(debit_raw) and str(debit_raw).strip() not in ("", "-"):
            try:
                val = float(str(debit_raw).replace(",", "").strip())
                if val > 0:
                    debit_val = val
                    is_debit = True
            except ValueError:
                pass
                
        if pd.notna(credit_raw) and str(credit_raw).strip() not in ("", "-"):
            try:
                val = float(str(credit_raw).replace(",", "").strip())
                if val > 0:
                    credit_val = val
                    is_credit = True
            except ValueError:
                pass
                
        if not is_debit and not is_credit:
            # Fallback check other columns if indices 3/4 didn't work
            # e.g., if there's only one Amount column (index 2 or 3) and a type column
            continue
            
        amount = debit_val if is_debit else credit_val
        tx_type = "debit" if is_debit else "credit"
        
        transactions.append({
            "date": dt,
            "raw_description": clean_narration,
            "amount": amount,
            "type": tx_type
        })
        
    return transactions
