import json
import sqlite3
from datetime import datetime, timedelta
from statistics import median
from typing import Dict, List, Optional

from rapidfuzz import fuzz

DB_PATH = "data.db"

# Simple mapping of product keys to canonical model strings used for fuzzy matching.
PRODUCT_RULES: Dict[str, List[str]] = {
    "delonghi_magnifica_s": ["delonghi magnifica s"],
}

THRESHOLD = 80


def match_product_key(title: str) -> Optional[str]:
    """Return the product key that best matches a listing title."""
    title = title.lower()
    best_key: Optional[str] = None
    best_score = 0
    for key, patterns in PRODUCT_RULES.items():
        for pattern in patterns:
            score = fuzz.partial_ratio(pattern.lower(), title)
            if score > best_score:
                best_key, best_score = key, score
    if best_score >= THRESHOLD:
        return best_key
    return None


def winsorize(values: List[float], lower_pct: float = 0.1, upper_pct: float = 0.9) -> List[float]:
    """Clamp values to the given percentile range."""
    if not values:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    lower_idx = int(n * lower_pct)
    upper_idx = int(n * upper_pct) - 1
    lower = sorted_vals[lower_idx]
    upper = sorted_vals[upper_idx]
    return [min(max(v, lower), upper) for v in values]


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return float("nan")
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_vals):
        return sorted_vals[f] + (sorted_vals[f + 1] - sorted_vals[f]) * c
    return sorted_vals[f]


def analyze(db_path: str = DB_PATH) -> Dict[str, Dict[str, float]]:
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
    try:
        cur = conn.execute(
            "SELECT title, price, final_price, start_date, last_seen, highest_bid FROM listings WHERE last_seen >= ?",
            (cutoff,),
        )
    except sqlite3.OperationalError:
        return {}

    products: Dict[str, Dict[str, List[float]]] = {}
    for title, price, final_price, start_date, last_seen, highest_bid in cur.fetchall():
        key = match_product_key(title or "")
        if key is None:
            continue
        ask = final_price if final_price is not None else price
        if ask is None:
            continue
        if highest_bid is not None:
            clearing = max(highest_bid, ask * 0.8)
        else:
            clearing = ask
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        last_dt = datetime.fromisoformat(last_seen) if last_seen else None
        duration = (last_dt - start_dt).days if start_dt and last_dt else None

        rec = products.setdefault(key, {"prices": [], "durations": []})
        rec["prices"].append(clearing)
        if duration is not None:
            rec["durations"].append(duration)

    results: Dict[str, Dict[str, float]] = {}
    for key, rec in products.items():
        prices = winsorize(rec["prices"])
        p25 = percentile(prices, 0.25)
        med = percentile(prices, 0.5)
        p75 = percentile(prices, 0.75)
        tt_disp = median(rec["durations"]) if rec["durations"] else float("nan")
        results[key] = {
            "p25": p25,
            "median": med,
            "p75": p75,
            "time_to_disappear": tt_disp,
        }
    return results


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
