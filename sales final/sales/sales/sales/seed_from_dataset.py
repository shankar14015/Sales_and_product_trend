#!/usr/bin/env python3
"""
Import dataset.csv into the database.
CSV columns: Date, Product, Category, Quantity, Unit Price, Gross Amount, Payment Mode.
Creates categories and products from the CSV and adds sales with dates and gross_amount.
Run with --replace to clear existing data and load only from dataset.csv.
Otherwise merges: adds new categories/products and appends sales from CSV.
"""
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.db import get_tables


def parse_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        if '-' in raw:
            parts = raw.split('-')
            if len(parts[0]) == 4:  # YYYY-MM-DD
                from dateutil.parser import parse as dateutil_parse
                return dateutil_parse(raw.split('+')[0].strip())
            return datetime.strptime(raw[:10], '%d-%m-%Y')
        from dateutil.parser import parse as dateutil_parse
        return dateutil_parse(raw.split('+')[0].strip())
    except Exception:
        return None


def run(replace=False):
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, 'dataset.csv')
    if not os.path.isfile(csv_path):
        print(f"File not found: {csv_path}")
        return

    t = get_tables()
    cats_t = t['categories']
    prods_t = t['products']
    sales_t = t['sales']

    if replace:
        # Clear all (TinyDB: we need to drop and recreate or remove all docs)
        for doc in sales_t.all():
            sales_t.remove(doc_ids=[doc.doc_id])
        for doc in prods_t.all():
            prods_t.remove(doc_ids=[doc.doc_id])
        for doc in cats_t.all():
            cats_t.remove(doc_ids=[doc.doc_id])
        print("Cleared existing categories, products, and sales.")

    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if any(r.get(k, '').strip() for k in r)]

    if not rows:
        print("No rows in CSV.")
        return

    # Normalize column names
    first = rows[0]
    col = {}
    for k in first.keys():
        k2 = k.strip()
        col[k2.lower()] = k2
    date_col = col.get('date') or next((col[k] for k in col if 'date' in k), None)
    product_col = col.get('product') or next((col[k] for k in col if 'product' in k), None)
    category_col = col.get('category') or next((col[k] for k in col if 'category' in k), None)
    qty_col = col.get('quantity') or next((col[k] for k in col if 'quantity' in k), None)
    unit_price_col = col.get('unit price') or col.get('unit_price') or next((col[k] for k in col if 'unit' in k and 'price' in k), None)
    gross_col = col.get('gross amount') or col.get('gross_amount') or next((col[k] for k in col if 'gross' in k), None)

    if not all([date_col, product_col, category_col, gross_col]):
        print("CSV must have Date, Product, Category, and Gross Amount columns.")
        return

    # Build unique categories and products (name -> id)
    category_name_to_id = {c.get('name', ''): c.doc_id for c in cats_t.all()}
    category_id_to_name = {c.doc_id: c.get('name', '') for c in cats_t.all()}
    product_key_to_id = {}  # (product_name, category_name) -> doc_id
    for p in prods_t.all():
        cid = p.get('category_id')
        cname = category_id_to_name.get(cid, '')
        product_key_to_id[(p.get('name', ''), cname)] = p.doc_id

    # First pass: ensure all categories and products exist
    for row in rows:
        cat_name = (row.get(category_col) or '').strip()
        prod_name = (row.get(product_col) or '').strip()
        if not cat_name or not prod_name:
            continue
        if cat_name not in category_name_to_id:
            cid = cats_t.insert({'name': cat_name})
            category_name_to_id[cat_name] = cid
            category_id_to_name[cid] = cat_name
        if (prod_name, cat_name) not in product_key_to_id:
            try:
                price = float((row.get(unit_price_col) or 0))
            except (TypeError, ValueError):
                price = 0
            cid = category_name_to_id[cat_name]
            pid = prods_t.insert({'name': prod_name, 'price': price, 'category_id': cid})
            product_key_to_id[(prod_name, cat_name)] = pid

    # Second pass: insert sales (with dates from CSV)
    inserted = 0
    for row in rows:
        dt = parse_date(row.get(date_col))
        prod_name = (row.get(product_col) or '').strip()
        cat_name = (row.get(category_col) or '').strip()
        if not dt or not prod_name or not cat_name:
            continue
        pid = product_key_to_id.get((prod_name, cat_name))
        if not pid:
            continue
        try:
            qty = float((row.get(qty_col) or 1).strip() or 1)
        except (TypeError, ValueError):
            qty = 1
        if qty <= 0:
            qty = 1
        try:
            price = float((row.get(unit_price_col) or 0))
        except (TypeError, ValueError):
            price = 0
        try:
            gross = float((row.get(gross_col) or 0).strip())
        except (TypeError, ValueError):
            continue
        sales_t.insert({
            'product_id': pid,
            'quantity': qty,
            'price': price,
            'amount': gross,
            'total': gross,
            'gross_amount': gross,
            'date': dt.isoformat(),
            'created_at': dt.isoformat(),
        })
        inserted += 1

    print(f"Imported {inserted} sales from dataset.csv.")
    print(f"Categories: {len(category_name_to_id)}, Products: {len(product_key_to_id)}.")


if __name__ == '__main__':
    replace = '--replace' in sys.argv
    run(replace=replace)
