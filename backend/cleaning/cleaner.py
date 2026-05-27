import re

# Common UPI handles and payment processor noise
UPI_PATTERNS = [
    r"@[a-zA-Z0-9.-]+",                   # UPI handles e.g., @okaxis, @ybl
    r"UPI-",                              # UPI prefix
    r"UPI/",                              # UPI slash prefix
    r"GPAY-",                             # GPay prefix
    r"PAYTM-",                            # Paytm prefix
    r"IMPS-",                             # IMPS prefix
    r"NEFT-",                             # NEFT prefix
    r"RTGS-",                             # RTGS prefix
    r"/[0-9]+/.*",                        # Slash reference numbers
]

# Explicit common merchant maps for direct normalization
MERCHANT_MAP = {
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "netflix": "Netflix",
    "spotify": "Spotify",
    "amazon": "Amazon",
    "uber": "Uber",
    "ola ride": "Ola",
    "blinkit": "Blinkit",
    "zepto": "Zepto",
    "starbucks": "Starbucks",
    "apple.com": "Apple",
    "google *t": "Google Play",
    "google play": "Google Play",
    "microsoft": "Microsoft",
    "steam games": "Steam",
    "dunzo": "Dunzo",
    "cred": "Cred",
    "interest received": "Interest Earned",
    "salary": "Salary",
    "dividend": "Dividend Income",
}

def clean_merchant_name(raw_desc: str) -> str:
    """
    Cleans up noisy merchant names / transaction descriptions.
    e.g., "SWIGGY LIMITED BLR" -> "Swiggy"
          "UPI-GPAY-ZOMATO-1234@okaxis" -> "Zomato"
    """
    if not raw_desc:
        return "Unknown"

    cleaned = raw_desc.upper()

    # Apply general UPI/IMPS/NEFT removals
    for pat in UPI_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Clean numbers, references, transaction IDs, trailing punctuation, and extra spacing
    cleaned = re.sub(r"\b[0-9]{5,}\b", "", cleaned)  # long numbers
    cleaned = re.sub(r"\b[0-9]+[A-Z]+[0-9]*\b", "", cleaned) # alphanumeric ref numbers
    cleaned = re.sub(r"\s+", " ", cleaned) # extra whitespace
    cleaned = cleaned.strip(" -_/\\.*")

    # Match common merchant map
    cleaned_lower = cleaned.lower()
    for keyword, friendly_name in MERCHANT_MAP.items():
        if keyword in cleaned_lower:
            return friendly_name

    # Title-case remaining cleaned descriptions
    words = cleaned.split()
    # Filter out empty strings and words that are entirely numeric (unless short)
    filtered_words = [w for w in words if not (w.isdigit() and len(w) > 3)]
    
    if not filtered_words:
        return cleaned.title()

    # Reassemble and title case
    final_desc = " ".join(filtered_words).title()
    return final_desc or "Unknown"
