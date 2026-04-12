"""Seed sample categories and products for testing."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.db import get_tables
from datetime import datetime, timedelta
import random

def seed():
    t = get_tables()
    cats = t['categories']
    prods = t['products']
    sales = t['sales']

    if cats.all():
        print("Data already exists. Skipping seed.")
        return

    # Categories
    c1 = cats.insert({'name': 'Electronics'})
    c2 = cats.insert({'name': 'Clothing'})
    c3 = cats.insert({'name': 'Food & Beverages'})

    # Products
    prods.insert({'name': 'Laptop', 'price': 999.99, 'category_id': c1})
    prods.insert({'name': 'Phone', 'price': 699.99, 'category_id': c1})
    prods.insert({'name': 'Headphones', 'price': 149.99, 'category_id': c1})
    prods.insert({'name': 'T-Shirt', 'price': 29.99, 'category_id': c2})
    prods.insert({'name': 'Jeans', 'price': 59.99, 'category_id': c2})
    prods.insert({'name': 'Coffee', 'price': 4.99, 'category_id': c3})
    prods.insert({'name': 'Sandwich', 'price': 8.99, 'category_id': c3})

    # Sample sales for charts and AI
    all_prods = prods.all()
    for i in range(30):
        dt = datetime.now() - timedelta(days=i)
        for _ in range(random.randint(1, 5)):
            p = random.choice(all_prods)
            qty = random.randint(1, 3)
            amt = qty * (p.get('price', 10))
            sales.insert({
                'product_id': p.doc_id,
                'quantity': qty,
                'price': p.get('price', 10),
                'amount': amt,
                'total': amt,
                'date': dt.isoformat(),
                'created_at': dt.isoformat(),
            })

    print("Seeded categories, products, and sample sales.")

if __name__ == '__main__':
    seed()
