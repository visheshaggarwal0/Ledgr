import io
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DATE_KEYWORDS = ["date", "tx date", "value date", "transaction date", "booking date", "post date"]
DESC_KEYWORDS = ["description", "particulars", "narration", "remarks", "details", "payee", "merchant", "transaction details"]
DEBIT_KEYWORDS = ["debit", "withdrawal", "withdrawals", "payment", "out", "spent"]
CREDIT_KEYWORDS = ["credit", "deposit", "deposits", "in", "received"]
AMOUNT_KEYWORDS = ["amount", "value", "transaction amount", "dr/cr amount", "net amount"]

def detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Scans the dataframe columns to auto-detect mappings for Date, Description, Amount/Debit/Credit.
    """
    mapping = {
        "date_col": None,
        "desc_col": None,
        "amount_col": None,
        "debit_col": None,
        "credit_col": None
    }
    
    cols = [str(c).strip().lower() for c in df.columns]
    col_map = {str(c).strip().lower(): c for c in df.columns}

    # 1. Date column detection
    for dk in DATE_KEYWORDS:
        matched = [c for c in cols if dk in c]
        if matched:
            mapping["date_col"] = col_map[matched[0]]
            break

    # 2. Description column detection
    for dk in DESC_KEYWORDS:
        matched = [c for c in cols if dk in c]
        if matched:
            mapping["desc_col"] = col_map[matched[0]]
            break

    # Check for Debit and Credit separate columns
    debit_col = None
    for dk in DEBIT_KEYWORDS:
        matched = [c for c in cols if dk == c or (dk in c and "amount" in c)]
        if matched:
            debit_col = col_map[matched[0]]
            break

    credit_col = None
    for ck in CREDIT_KEYWORDS:
        matched = [c for c in cols if ck == c or (ck in c and "amount" in c)]
        if matched:
            credit_col = col_map[matched[0]]
            break

    if debit_col and credit_col:
        mapping["debit_col"] = debit_col
        mapping["credit_col"] = credit_col
    else:
        # Check unified Amount column
        for ak in AMOUNT_KEYWORDS:
            matched = [c for c in cols if ak in c and not any(k in c for k in DEBIT_KEYWORDS + CREDIT_KEYWORDS)]
            if matched:
                mapping["amount_col"] = col_map[matched[0]]
                break
        
        # Fallback if amount_col not found, check if there's any col named "amount"
        if not mapping["amount_col"]:
            matched = [c for c in cols if "amount" in c]
            if matched:
                mapping["amount_col"] = col_map[matched[0]]

    return mapping

def parse_date(date_str: Any) -> datetime.date:
    """Attempts to parse dates in various formats."""
    if pd.isna(date_str):
        raise ValueError("Empty date cell")
        
    val = str(date_str).strip()
    # Common formats
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y",
        "%b %d, %Y", "%d %b %Y", "%d-%b-%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
            
    # Try parsing using pandas if simple formats fail
    try:
        return pd.to_datetime(val).date()
    except Exception:
        raise ValueError(f"Could not parse date string: {val}")

def parse_csv_to_transactions(
    file_bytes: bytes,
    custom_mapping: Optional[Dict[str, str]] = None
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Parses a CSV transaction file.
    Returns (list_of_parsed_tx_dicts, requires_custom_mapping)
    """
    # Try reading as UTF-8 or Latin-1
    try:
        decoded = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decoded = file_bytes.decode("latin-1")

    # Read CSV
    # Skip potential bank header rows (e.g. if the first few rows are bank branding)
    # We can inspect the first few lines to find where the main table starts
    lines = decoded.splitlines()
    header_idx = 0
    for idx, line in enumerate(lines[:15]):
        # Look for headers containing typical date/description/amount fields
        line_lower = line.lower()
        if any(dk in line_lower for dk in DATE_KEYWORDS) and any(ak in line_lower for ak in AMOUNT_KEYWORDS + DEBIT_KEYWORDS + CREDIT_KEYWORDS):
            header_idx = idx
            break

    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))

    # Get column configuration
    mapping = detect_columns(df) if not custom_mapping else {
        "date_col": custom_mapping.get("date"),
        "desc_col": custom_mapping.get("description"),
        "amount_col": custom_mapping.get("amount"),
        "debit_col": custom_mapping.get("debit"),
        "credit_col": custom_mapping.get("credit"),
    }

    # Validate mapping - if we can't detect Date and Description, we must ask the user
    if not mapping["date_col"] or not mapping["desc_col"]:
        # Check if they are configured in custom mapping
        return [], True

    has_amount = mapping["amount_col"] is not None
    has_split = mapping["debit_col"] is not None and mapping["credit_col"] is not None

    if not has_amount and not has_split:
        return [], True

    transactions = []
    
    for _, row in df.iterrows():
        try:
            date_val = parse_date(row[mapping["date_col"]])
            desc_val = str(row[mapping["desc_col"]]).strip()
            
            # Skip empty description rows or summary rows
            if not desc_val or pd.isna(row[mapping["desc_col"]]):
                continue

            amount = 0.0
            tx_type = "debit"

            if has_split:
                debit_val = row[mapping["debit_col"]]
                credit_val = row[mapping["credit_col"]]
                
                # Check which one has a value
                is_debit = not pd.isna(debit_val) and str(debit_val).strip() != "" and float(str(debit_val).replace(",", "").strip() or 0) > 0
                is_credit = not pd.isna(credit_val) and str(credit_val).strip() != "" and float(str(credit_val).replace(",", "").strip() or 0) > 0

                if is_debit:
                    amount = float(str(debit_val).replace(",", "").strip())
                    tx_type = "debit"
                elif is_credit:
                    amount = float(str(credit_val).replace(",", "").strip())
                    tx_type = "credit"
                else:
                    continue  # skip zero or blank lines
            else:
                amount_raw = str(row[mapping["amount_col"]]).replace(",", "").strip()
                # Determine sign
                if amount_raw.startswith("-") or amount_raw.endswith("DR") or "debit" in amount_raw.lower():
                    tx_type = "debit"
                elif amount_raw.startswith("+") or amount_raw.endswith("CR") or "credit" in amount_raw.lower():
                    tx_type = "credit"
                else:
                    # Let's inspect column value. If amount is just a float, default to debit (expenses are more common)
                    # unless it's explicitly classified. If there's another column indicating Dr/Cr, we can check.
                    tx_type = "debit"
                
                # Strip out formatting/letters
                amount_cleaned = "".join([c for c in amount_raw if c.isdigit() or c == "."])
                amount = float(amount_cleaned) if amount_cleaned else 0.0

            if amount == 0:
                continue

            transactions.append({
                "date": date_val,
                "raw_description": desc_val,
                "amount": amount,
                "type": tx_type,
            })
        except Exception:
            # Skip bad rows
            continue

    return transactions, False
