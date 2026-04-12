"""Add 6 months of past sales so AI Prediction shows a real trend (not flat).
Run once: python seed_6months_sales.py
Keeps existing categories and products; replaces sales with 6 months of data.
"""
import sys
sys.path.insert(0, sys.path[0] or '.')
from database.db import get_tables
from datetime import datetime, timedelta
import random

def seed_6months():
    t = get_tables()
    prods = t['products'].all()
    sales_t = t['sales']
    if not prods:
        print("No products found. Run seed_data.py first.")
        return
    # Clear existing sales so we have exactly 6 months of history
    sales_t.truncate()
    # Generate sales for each of the last ~180 days (6 months)
    days_back = 180
    for i in range(days_back):
        dt = datetime.now() - timedelta(days=i)
        for _ in range(random.randint(1, 5)):
            p = random.choice(prods)
            qty = random.randint(1, 3)
            amt = qty * (p.get('price', 10))
            sales_t.insert({
                'product_id': p.doc_id,
                'quantity': qty,
                'price': p.get('price', 10),
                'amount': amt,
                'total': amt,
                'date': dt.isoformat(),
                'created_at': dt.isoformat(),
            })
    print("Seeded 6 months of sales. Refresh AI Prediction to see a trend (different values per month).")

if __name__ == '__main__':
    seed_6months()
