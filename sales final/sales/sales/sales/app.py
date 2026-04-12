"""Main Flask Sales Management Application."""
import os
import json
import time
import secrets
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta
from config import (
    SECRET_KEY,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    AI_PREDICTION_API_URL,
    AI_PREDICTION_API_KEY,
    AI_PREDICTION_API_TIMEOUT_SECONDS,
)
from database.db import get_tables
from services.ai_predictor import SalesPredictor
from services.ai_analyzer import SaleAnalyzer

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Persistent cache for POST→Redirect→GET predictions (survives dev reloads).
_AI_PRED_CACHE_TTL_SECONDS = 10 * 60


def _ai_pred_cache_put(payload):
    key = secrets.token_urlsafe(16)
    try:
        t = tables()['ai_pred_cache']
        t.insert({'key': key, 'expires': time.time() + _AI_PRED_CACHE_TTL_SECONDS, 'payload': payload})
    except Exception:
        # last-resort: still return key; GET will fall back to default if missing
        pass
    return key


def _ai_pred_cache_get(key):
    if not key:
        return None
    try:
        t = tables()['ai_pred_cache']
        now = time.time()
        # cleanup expired
        try:
            from tinydb import Query
            Q = Query()
            t.remove(Q.expires < now)
        except Exception:
            pass
        from tinydb import Query
        Q = Query()
        row = t.get(Q.key == key)
        if not row:
            return None
        if row.get('expires', 0) < now:
            t.remove(Q.key == key)
            return None
        return row.get('payload')
    except Exception:
        return None


@app.before_request
def require_admin_login():
    """Redirect to login if not authenticated (except landing, login, static)."""
    if request.endpoint and request.endpoint not in ('index', 'login', 'static'):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login. Only successful login redirects to dashboard."""
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Clear session and redirect to landing."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


def tables():
    return get_tables()


def serialize_doc(doc):
    """Convert TinyDB doc_id to id for JSON."""
    d = dict(doc)
    d['id'] = getattr(doc, 'doc_id', d.get('id', 0))
    return d


# --- Landing (public) ---
@app.route('/')
def index():
    """Landing page. If logged in, redirect to dashboard."""
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


# --- Dashboard ---
@app.route('/dashboard')
def dashboard():
    """Dashboard with overall sales and bar charts."""
    cats = tables()['categories'].all()
    prods = tables()['products'].all()
    sales = tables()['sales'].all()

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    today_sales = [s for s in sales if _get_date(s) == today]
    yesterday_sales = [s for s in sales if _get_date(s) == yesterday]
    total_today = sum(_get_gross(s) for s in today_sales)
    total_yesterday = sum(_get_gross(s) for s in yesterday_sales)
    growth_pct = None
    if total_yesterday and total_yesterday > 0:
        growth_pct = round((total_today - total_yesterday) / total_yesterday * 100, 2)

    # Monthly aggregation for chart (Gross)
    monthly = {}
    for s in sales:
        dt = _get_date(s)
        key = dt.strftime('%Y-%m')
        monthly[key] = monthly.get(key, 0) + _get_gross(s)

    chart_labels = sorted(monthly.keys())[-12:]
    chart_data = [monthly[k] for k in chart_labels]

    # Today hourly
    hourly = {}
    for s in today_sales:
        dt = _get_datetime(s)
        h = dt.hour
        hourly[h] = hourly.get(h, 0) + _get_gross(s)
    hour_labels = [f"{h}:00" for h in range(24) if h in hourly]
    hour_data = [hourly[h] for h in range(24) if h in hourly]
    if not hour_labels:
        hour_labels = ['0:00']
        hour_data = [0]

    return render_template('dashboard.html',
        categories=cats,
        products=prods,
        total_today=total_today,
        today_count=len(today_sales),
        growth_pct=growth_pct,
        chart_labels=chart_labels,
        chart_data=chart_data,
        hour_labels=hour_labels,
        hour_data=hour_data,
    )


# --- Sales Section ---
@app.route('/sales')
def sales_page():
    cats = tables()['categories'].all()
    prods = tables()['products'].all()
    # Include doc_id so JS dropdowns get valid option values (TinyDB doc_id is not in dict)
    categories_data = [{'doc_id': c.doc_id, 'name': c.get('name', '')} for c in cats]
    products_data = [{'doc_id': p.doc_id, 'name': p.get('name', ''), 'price': p.get('price', 0), 'category_id': p.get('category_id')} for p in prods]
    return render_template('sales.html', categories=categories_data, products=products_data)


@app.route('/api/products/by_category/<int:cat_id>')
def products_by_category(cat_id):
    prods = [p for p in tables()['products'].all() if p.get('category_id') == cat_id]
    return jsonify([serialize_doc(p) for p in prods])


@app.route('/api/sales/summary')
def api_sales_summary():
    """Return quantity and total for sales filtered by category_ids and/or product_ids."""
    cat_ids = request.args.getlist('category_ids', type=int)
    prod_ids = request.args.getlist('product_ids', type=int)
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}

    filtered = sales
    if prod_ids:
        filtered = [s for s in filtered if s.get('product_id') in prod_ids]
    elif cat_ids:
        prod_in_cats = {p.doc_id for p in prods.values() if p.get('category_id') in cat_ids}
        filtered = [s for s in filtered if s.get('product_id') in prod_in_cats]

    qty = sum(s.get('quantity', 1) for s in filtered)
    total = sum(_get_gross(s) for s in filtered)
    return jsonify({'quantity': qty, 'total': total, 'transactions': len(filtered)})


@app.route('/api/sales/add', methods=['POST'])
def add_sale():
    data = request.get_json() or request.form
    # Support both JSON dict and form data
    if isinstance(data, dict):
        product_id = int(data.get('product_id') or 0)
        quantity = float(data.get('quantity') or 1)
        price = float(data.get('price') or 0)
    else:
        product_id = data.get('product_id', type=int)
        quantity = data.get('quantity', 1, type=float)
        price = data.get('price', 0, type=float)
    amount = quantity * price

    prods = {p.doc_id: p for p in tables()['products'].all()}
    if product_id not in prods:
        return jsonify({'error': 'Product not found'}), 400

    sale = {
        'product_id': product_id,
        'quantity': quantity,
        'price': price,
        'amount': amount,
        'total': amount,
        'gross_amount': amount,
        'date': datetime.now().isoformat(),
        'created_at': datetime.now().isoformat(),
    }
    tables()['sales'].insert(sale)
    return jsonify({'success': True, 'sale': sale})


# --- Categories ---
@app.route('/categories')
def categories_page():
    cats = tables()['categories'].all()
    cat_ids = request.args.getlist('category_ids', type=int)
    if cat_ids:
        cats = [c for c in cats if c.doc_id in cat_ids]
    return render_template('categories.html', categories=cats)


@app.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    t = tables()['categories']
    if request.method == 'POST':
        data = request.get_json() or request.form
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Name required'}), 400
        tid = t.insert({'name': name})
        return jsonify({'success': True, 'id': tid})
    return jsonify([serialize_doc(c) for c in t.all()])


@app.route('/api/categories/<int:cid>', methods=['PUT', 'DELETE'])
def api_category(cid):
    t = tables()['categories']
    if request.method == 'DELETE':
        t.remove(doc_ids=[cid])
        return jsonify({'success': True})
    data = request.get_json()
    t.update({'name': data.get('name')}, doc_ids=[cid])
    return jsonify({'success': True})


# --- Products ---
@app.route('/products')
def products_page():
    cats = tables()['categories'].all()
    prods = tables()['products'].all()
    cat_ids = request.args.getlist('category_ids', type=int)
    prod_ids = request.args.getlist('product_ids', type=int)

    if prod_ids:
        prods = [p for p in prods if p.doc_id in prod_ids]
    elif cat_ids:
        prods = [p for p in prods if p.get('category_id') in cat_ids]

    cats_map = {c.doc_id: c.get('name', '') for c in cats}
    products_with_cat = []
    for p in prods:
        d = dict(p)
        d['doc_id'] = p.doc_id
        d['category_name'] = cats_map.get(p.get('category_id'), '-')
        products_with_cat.append(d)
    return render_template('products.html', categories=cats, products=products_with_cat)


@app.route('/api/products', methods=['GET', 'POST'])
def api_products():
    t = tables()['products']
    if request.method == 'POST':
        data = request.get_json() or request.form
        # Support both JSON dict and form data
        if isinstance(data, dict):
            name = str(data.get('name', '')).strip()
            price = float(data.get('price') or 0)
            category_id = int(data.get('category_id') or 0)
        else:
            name = data.get('name', '').strip()
            price = data.get('price', 0, type=float)
            category_id = data.get('category_id', type=int)
        if not name:
            return jsonify({'error': 'Name required'}), 400
        tid = t.insert({'name': name, 'price': price, 'category_id': category_id})
        return jsonify({'success': True, 'id': tid})
    return jsonify([serialize_doc(p) for p in t.all()])


@app.route('/api/products/<int:pid>', methods=['PUT', 'DELETE'])
def api_product(pid):
    t = tables()['products']
    if request.method == 'DELETE':
        t.remove(doc_ids=[pid])
        return jsonify({'success': True})
    data = request.get_json()
    updates = {}
    if 'name' in data: updates['name'] = data['name']
    if 'price' in data: updates['price'] = float(data['price'])
    if 'category_id' in data: updates['category_id'] = data['category_id']
    t.update(updates, doc_ids=[pid])
    return jsonify({'success': True})


# --- Reports ---
@app.route('/reports')
def reports_page():
    return render_template('reports.html')


def _apply_sales_filter(sales, prods_map):
    """Filter sales by category_ids or product_ids from request."""
    cat_ids = request.args.getlist('category_ids', type=int)
    prod_ids = request.args.getlist('product_ids', type=int)
    if prod_ids:
        return [s for s in sales if s.get('product_id') in prod_ids]
    if cat_ids:
        prod_in_cats = {p.doc_id for p in prods_map.values() if p.get('category_id') in cat_ids}
        return [s for s in sales if s.get('product_id') in prod_in_cats]
    return sales


@app.route('/reports/today')
def report_today():
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}
    today = datetime.now().date()
    filtered = [s for s in sales if _get_date(s) == today]
    filtered = _apply_sales_filter(filtered, prods)
    return _report_response(filtered, 'Today')


@app.route('/reports/monthly')
def report_monthly():
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}
    now = datetime.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    filtered = [s for s in sales if _get_datetime(s) >= start]
    filtered = _apply_sales_filter(filtered, prods)
    return _report_response(filtered, 'This Month')


@app.route('/reports/custom')
def report_custom():
    start_s = request.args.get('start')
    end_s = request.args.get('end')
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}
    filtered = sales
    if start_s:
        start_d = parse_date(start_s).date()
        filtered = [s for s in filtered if _get_date(s) >= start_d]
    if end_s:
        end_d = parse_date(end_s).date()
        filtered = [s for s in filtered if _get_date(s) <= end_d]
    filtered = _apply_sales_filter(filtered, prods)
    label = f"Custom: {start_s or '...'} to {end_s or '...'}"
    return _report_response(filtered, label)


@app.route('/reports/products')
def report_products():
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}
    sales = _apply_sales_filter(sales, prods)
    by_product = {}
    for s in sales:
        pid = s.get('product_id')
        name = prods.get(pid, {}).get('name', f'Product #{pid}')
        if pid not in by_product:
            by_product[pid] = {'name': name, 'amount': 0, 'quantity': 0}
        by_product[pid]['amount'] += _get_gross(s)
        by_product[pid]['quantity'] += s.get('quantity', 1)
    return render_template('report_products.html', products=list(by_product.values()))


@app.route('/reports/ai-prediction', methods=['GET', 'POST'])
def report_ai_prediction():
    def _render(daily, monthly, daily_by_product, monthly_by_product, from_upload=False, prediction_source='local'):
        total_30 = sum(d.get('predicted_amount', 0) for d in daily) if daily else 0
        total_6m = sum(m.get('predicted_amount', 0) for m in monthly) if monthly else 0
        return render_template(
            'report_ai_prediction.html',
            daily=daily, monthly=monthly,
            daily_by_product=daily_by_product or [],
            monthly_by_product=monthly_by_product or [],
            from_upload=from_upload,
            prediction_source=prediction_source,
            total_30_days_gross=round(total_30, 2),
            total_6_months_gross=round(total_6m, 2),
        )

    def _redirect_with_payload(payload):
        cache_key = _ai_pred_cache_put(payload)
        return redirect(url_for('report_ai_prediction', cache_key=cache_key))

    def _predict_via_api(sales_list, from_upload):
        """
        Call external prediction API if configured.

        Expected response JSON (missing keys default to empty):
          { "daily": [...], "monthly": [...], "daily_by_product": [...], "monthly_by_product": [...] }
        """
        if not AI_PREDICTION_API_URL:
            return None

        def _to_jsonable_sale(s):
            dt = s.get('date')
            if isinstance(dt, datetime):
                dt = dt.isoformat()
            elif dt is None:
                dt = ''
            return {
                'date': dt,
                'amount': float(s.get('amount', s.get('gross_amount', s.get('total', 0))) or 0),
                'quantity': float(s.get('quantity', 1) or 0),
                'product_id': s.get('product_id'),
                'product_name': s.get('product_name'),
                'category': s.get('category'),
                'payment_mode': s.get('payment_mode'),
            }

        payload = {
            'source': 'upload' if from_upload else 'db',
            'horizons': {'days_ahead': 30, 'months_ahead': 6},
            'sales': [_to_jsonable_sale(s) for s in (sales_list or [])],
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if AI_PREDICTION_API_KEY:
            headers['Authorization'] = f'Bearer {AI_PREDICTION_API_KEY}'

        req = urllib.request.Request(
            AI_PREDICTION_API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=AI_PREDICTION_API_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw or '{}')
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            flash(f'AI API prediction failed; showing local predictions instead. ({e})', 'error')
            return None

        daily = data.get('daily') or []
        monthly = data.get('monthly') or []
        daily_by_product = data.get('daily_by_product') or []
        monthly_by_product = data.get('monthly_by_product') or []
        return daily, monthly, daily_by_product, monthly_by_product

    # If redirected after POST, render cached results.
    cache_key = request.args.get('cache_key')
    cached = _ai_pred_cache_get(cache_key)
    if request.method == 'GET' and cache_key and not cached:
        flash('Prediction link expired. Please upload again.', 'error')
    if request.method == 'GET' and cached:
        return _render(
            cached.get('daily') or [],
            cached.get('monthly') or [],
            cached.get('daily_by_product') or [],
            cached.get('monthly_by_product') or [],
            from_upload=bool(cached.get('from_upload')),
            prediction_source=cached.get('prediction_source') or 'local',
        )
    if request.method == 'GET' and cache_key and not cached:
        # This happens if the server restarted or the cache expired.
        flash('That prediction link has expired. Showing fresh predictions instead.', 'error')
        return redirect(url_for('report_ai_prediction'))

    upload_file = request.files.get('excel_file') or request.files.get('csv_file') or request.files.get('upload_file')
    if request.method == 'POST' and upload_file and upload_file.filename:
        fn = upload_file.filename.lower()
        if fn.endswith('.csv'):
            sales, error = _parse_csv_sales(upload_file)
            if error:
                flash(error, 'error')
                sales = _sales_last_n_months(6)
                api_result = _predict_via_api(sales, from_upload=False)
                if api_result:
                    daily, monthly, daily_by_product, monthly_by_product = api_result
                    return _redirect_with_payload({
                        'daily': daily, 'monthly': monthly,
                        'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                        'from_upload': False,
                        'prediction_source': 'api',
                    })
                predictor = SalesPredictor(sales)
                daily = predictor.predict_daily(30)
                monthly = predictor.predict_monthly(6)
                prods = {p.doc_id: p.get('name', f'#{p.doc_id}') for p in tables()['products'].all()}
                daily_by_product, monthly_by_product = _predictions_by_product(sales, products_map=prods)
                return _redirect_with_payload({
                    'daily': daily, 'monthly': monthly,
                    'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                    'from_upload': False,
                    'prediction_source': 'local',
                })
            # Persist uploaded rows into DB so that AI Analyzer and other reports
            # work on the same dataset as AI Prediction (CSV behaves like Excel).
            try:
                _rebuild_db_from_uploaded_sales(sales)
            except Exception as e:
                flash(f'Warning: could not update database from CSV upload ({e}). Analyzer will still use old data.', 'error')

            sales_6m = _last_n_months_from_list(sales, 6)
            api_result = _predict_via_api(sales_6m, from_upload=True)
            if api_result:
                daily, monthly, daily_by_product, monthly_by_product = api_result
                return _redirect_with_payload({
                    'daily': daily, 'monthly': monthly,
                    'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                    'from_upload': True,
                    'prediction_source': 'api',
                })
            predictor = SalesPredictor(sales_6m)
            daily = predictor.predict_daily(30)
            monthly = predictor.predict_monthly(6)
            daily_by_product, monthly_by_product = _predictions_by_product(sales_6m, products_map=None)
            return _redirect_with_payload({
                'daily': daily, 'monthly': monthly,
                'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                'from_upload': True,
                'prediction_source': 'local',
            })
        elif fn.endswith('.xlsx'):
            sales, error = _parse_excel_sales(upload_file)
            if error:
                flash(error, 'error')
                sales = _sales_last_n_months(6)
                api_result = _predict_via_api(sales, from_upload=False)
                if api_result:
                    daily, monthly, daily_by_product, monthly_by_product = api_result
                    return _redirect_with_payload({
                        'daily': daily, 'monthly': monthly,
                        'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                        'from_upload': False,
                        'prediction_source': 'api',
                    })
                predictor = SalesPredictor(sales)
                daily = predictor.predict_daily(30)
                monthly = predictor.predict_monthly(6)
                daily_by_product, monthly_by_product = _predictions_by_product(sales, products_map=None)
                return _redirect_with_payload({
                    'daily': daily, 'monthly': monthly,
                    'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                    'from_upload': False,
                    'prediction_source': 'local',
                })
            try:
                if sales:
                    ds = min(s.get('date') for s in sales if s.get('date'))
                    de = max(s.get('date') for s in sales if s.get('date'))
                    flash(f'Excel loaded: {len(sales)} rows ({ds:%Y-%m-%d} → {de:%Y-%m-%d}).', 'success')
            except Exception:
                flash(f'Excel loaded: {len(sales)} rows.', 'success')
            # Persist uploaded rows into DB as normalized categories/products/sales.
            try:
                _rebuild_db_from_uploaded_sales(sales)
            except Exception as e:
                flash(f'Warning: could not update database from upload ({e}). Predictions will still use uploaded file.', 'error')

            sales_6m = _last_n_months_from_list(sales, 6)
            api_result = _predict_via_api(sales_6m, from_upload=True)
            if api_result:
                daily, monthly, daily_by_product, monthly_by_product = api_result
                return _redirect_with_payload({
                    'daily': daily, 'monthly': monthly,
                    'daily_by_product': daily_by_product or [], 'monthly_by_product': monthly_by_product or [],
                    'from_upload': True,
                    'prediction_source': 'api',
                })
            predictor = SalesPredictor(sales_6m)
            daily = predictor.predict_daily(30)
            monthly = predictor.predict_monthly(6)
            # Build product breakdown for Excel too (we now have product_name/category columns).
            daily_by_product, monthly_by_product = _predictions_by_product(sales_6m, products_map=None)
            return _redirect_with_payload({
                'daily': daily, 'monthly': monthly,
                'daily_by_product': daily_by_product, 'monthly_by_product': monthly_by_product,
                'from_upload': True,
                'prediction_source': 'local',
            })
        else:
            flash('Please upload a CSV (.csv) or Excel (.xlsx) file.', 'error')
    sales = _sales_last_n_months(6)
    api_result = _predict_via_api(sales, from_upload=False)
    if api_result:
        daily, monthly, daily_by_product, monthly_by_product = api_result
        return _render(daily, monthly, daily_by_product, monthly_by_product, from_upload=False, prediction_source='api')
    predictor = SalesPredictor(sales)
    daily = predictor.predict_daily(30)
    monthly = predictor.predict_monthly(6)
    prods = {p.doc_id: p.get('name', f'#{p.doc_id}') for p in tables()['products'].all()}
    daily_by_product, monthly_by_product = _predictions_by_product(sales, products_map=prods)
    return _render(daily, monthly, daily_by_product, monthly_by_product, from_upload=False, prediction_source='local')


@app.route('/reports/ai-analyzer')
def report_ai_analyzer():
    return render_template('report_ai_analyzer.html')


@app.route('/api/reports/ai-analyzer', methods=['POST'])
def api_ai_analyzer():
    data = request.get_json() or {}
    start_s = data.get('start')
    end_s = data.get('end')
    sales = tables()['sales'].all()
    prods = {p.doc_id: p for p in tables()['products'].all()}
    cats = {c.doc_id: c for c in tables()['categories'].all()}
    products_map = {k: v.get('name', str(k)) for k, v in prods.items()}

    start_d = parse_date(start_s).date() if start_s else None
    end_d = parse_date(end_s).date() if end_s else None

    analyzer = SaleAnalyzer(sales, products_map=products_map, categories_map=cats)
    report = analyzer.generate_report(start_d, end_d)
    return jsonify({'report': report})


# --- Helpers ---
def _get_date(s):
    d = s.get('date') or s.get('created_at', '')
    if isinstance(d, datetime):
        return d.date()
    return parse_date(str(d).split('+')[0]).date()


def _get_datetime(s):
    d = s.get('date') or s.get('created_at', '')
    if isinstance(d, datetime):
        return d
    return parse_date(str(d).split('+')[0])


def _get_gross(s):
    """Get gross amount from a sale (gross_amount, amount, or total)."""
    return s.get('gross_amount', s.get('amount', s.get('total', 0)))


def _sales_for_prediction():
    sales = tables()['sales'].all()
    result = []
    for s in sales:
        result.append({
            'date': _get_datetime(s),
            'amount': _get_gross(s),
            'quantity': s.get('quantity', 1),
            'product_id': s.get('product_id'),
        })
    return result


def _sales_last_n_months(n_months):
    """Return sales from the last n months only (for training prediction). No user input."""
    sales = tables()['sales'].all()
    cutoff = datetime.now() - relativedelta(months=n_months)
    result = []
    for s in sales:
        dt = _get_datetime(s)
        if dt >= cutoff:
            result.append({
                'date': dt,
                'amount': _get_gross(s),
                'quantity': s.get('quantity', 1),
                'product_id': s.get('product_id'),
            })
    return result


def _last_n_months_from_list(sales_list, n_months):
    """From a list of sales dicts (with 'date'), keep only those in the last n months."""
    if not sales_list:
        return []
    cutoff = datetime.now() - relativedelta(months=n_months)
    return [s for s in sales_list if (s.get('date') or datetime.min) >= cutoff]


def _predictions_by_product(sales_list, products_map=None):
    """
    Build per-product daily (30 days) and monthly (6 months) predictions.
    sales_list: list of {date, amount, product_id?, product_name?}.
    products_map: optional dict product_id -> name (for DB); if None, use product_name from each sale (CSV).
    Returns (daily_by_product, monthly_by_product).
    daily_by_product: list of {product_name, total_30, daily: [{}]}
    monthly_by_product: list of {product_name, monthly: [{}]}
    """
    predictor = SalesPredictor(sales_list)
    daily_by_product = []
    monthly_by_product = []
    if products_map is not None:
        # DB: group by product_id
        product_ids = set(s.get('product_id') for s in sales_list if s.get('product_id') is not None)
        for pid in sorted(product_ids, key=lambda x: products_map.get(x, str(x))):
            name = products_map.get(pid, f'Product #{pid}')
            daily_list = predictor.predict_by_product(pid, 30)
            monthly_list = predictor.predict_monthly_by_product(pid, 6)
            total_30 = sum(d.get('predicted_amount', 0) for d in daily_list)
            daily_by_product.append({'product_name': name, 'total_30': round(total_30, 2), 'daily': daily_list})
            monthly_by_product.append({'product_name': name, 'monthly': monthly_list})
    else:
        # CSV: group by product_name
        by_key = predictor.predict_by_product_key(lambda s: s.get('product_name') or 'Unknown')
        for name in sorted(by_key.keys()):
            data = by_key[name]
            daily_list = data['daily']
            monthly_list = data['monthly']
            total_30 = sum(d.get('predicted_amount', 0) for d in daily_list)
            daily_by_product.append({'product_name': name, 'total_30': round(total_30, 2), 'daily': daily_list})
            monthly_by_product.append({'product_name': name, 'monthly': monthly_list})
    return daily_by_product, monthly_by_product


def _parse_csv_sales(file):
    """
    Parse CSV with columns (required): Date, Product, Category, Quantity, Unit Price, Gross Amount, Payment Mode.
    Returns (list of {date, amount, quantity, unit_price, product_name, category, payment_mode}, error_message).
    """
    import csv
    import io
    try:
        stream = io.TextIOWrapper(file, encoding='utf-8', errors='replace')
        reader = csv.DictReader(stream)
        rows = list(reader)
    except Exception as e:
        return [], f'Could not read CSV: {str(e)}'
    if not rows:
        return [], 'CSV file is empty.'
    # Strict required columns (case-insensitive).
    first_keys = [k for k in (rows[0].keys() or [])]
    normalized = {str(k).strip().lower(): k for k in first_keys}
    required = {
        'date': 'Date',
        'product': 'Product',
        'category': 'Category',
        'quantity': 'Quantity',
        'unit price': 'Unit Price',
        'gross amount': 'Gross Amount',
        'payment mode': 'Payment Mode',
    }
    missing = [pretty for key, pretty in required.items() if key not in normalized]
    if missing:
        return [], f"CSV is missing required column(s): {', '.join(missing)}"
    date_col = normalized['date']
    product_col = normalized['product']
    category_col = normalized['category']
    qty_col = normalized['quantity']
    unit_price_col = normalized['unit price']
    gross_col = normalized['gross amount']
    payment_col = normalized['payment mode']

    def _to_float(val, default=0.0):
        if val is None:
            return default
        try:
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if not s:
                return default
            s = s.replace('₹', '').replace(',', '')
            s = ''.join(ch for ch in s if (ch.isdigit() or ch in '.-'))
            return float(s) if s else default
        except Exception:
            return default

    def _parse_dt(raw_date):
        raw_date = (raw_date or '').strip()
        if not raw_date:
            return None
        # Common formats: DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD
        try:
            if '/' in raw_date and len(raw_date.split('/')[0]) <= 2:
                return datetime.strptime(raw_date[:10], '%d/%m/%Y')
            if '-' in raw_date:
                parts = raw_date.split('-')
                if len(parts[0]) == 4:
                    return parse_date(raw_date.split('+')[0].strip())
                return datetime.strptime(raw_date[:10], '%d-%m-%Y')
            return parse_date(raw_date.split('+')[0].strip())
        except Exception:
            try:
                return parse_date(raw_date.split('+')[0].strip())
            except Exception:
                return None

    result = []
    for row in rows:
        try:
            dt = _parse_dt(row.get(date_col, ''))
            if not dt:
                continue
            if hasattr(dt, 'to_pydatetime'):
                dt = dt.to_pydatetime()
            product_name = str(row.get(product_col, '') or '').strip()
            category = str(row.get(category_col, '') or '').strip()
            payment_mode = str(row.get(payment_col, '') or '').strip()
            quantity = _to_float(row.get(qty_col, 1), default=1.0) or 1.0
            if quantity <= 0:
                quantity = 1.0
            unit_price = _to_float(row.get(unit_price_col, 0), default=0.0)
            amount = _to_float(row.get(gross_col, 0), default=0.0)
            if amount <= 0 and unit_price > 0:
                amount = float(unit_price) * float(quantity)
            result.append({
                'date': dt,
                'amount': amount,
                'quantity': quantity,
                'product_id': None,
                'product_name': product_name or 'Unknown',
                'category': category or None,
                'payment_mode': payment_mode or None,
                'unit_price': unit_price,
            })
        except (ValueError, TypeError):
            continue
    if not result:
        return [], 'No valid rows found. Ensure Date and Gross Amount are filled.'
    return result, None


def _parse_excel_sales(file):
    """
    Parse Excel (.xlsx) with required columns:
      Date, Product, Category, Quantity, Unit Price, Gross Amount, Payment Mode
    Returns (list of {date, amount, quantity, unit_price, product_name, category, payment_mode}, error_message).
    """
    try:
        import pandas as pd
    except ImportError:
        return [], 'Excel support requires pandas and openpyxl. Install with: pip install pandas openpyxl'
    try:
        df = pd.read_excel(file, engine='openpyxl')
        if df.empty:
            return [], 'Excel file is empty.'
        # Drop empty/unnamed columns commonly present in exported sheets.
        df = df.loc[:, ~df.columns.astype(str).str.match(r'^\s*Unnamed:\s*\d+\s*$', na=False)]
        cols = [c for c in df.columns if isinstance(c, str)]
        col_lower = {c.strip().lower(): c for c in cols}
        required = {
            'date': 'Date',
            'product': 'Product',
            'category': 'Category',
            'quantity': 'Quantity',
            'unit price': 'Unit Price',
            'gross amount': 'Gross Amount',
            'payment mode': 'Payment Mode',
        }
        missing = [pretty for key, pretty in required.items() if key not in col_lower]
        if missing:
            return [], f"Excel is missing required column(s): {', '.join(missing)}"
        date_col = col_lower['date']
        product_col = col_lower['product']
        category_col = col_lower['category']
        qty_col = col_lower['quantity']
        unit_price_col = col_lower['unit price']
        amount_col = col_lower['gross amount']
        payment_col = col_lower['payment mode']

        def _to_float(val, default=0.0):
            if val is None:
                return default
            try:
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                if not s:
                    return default
                # Remove currency symbols, commas, and other noise.
                s = s.replace('₹', '').replace(',', '')
                # Keep digits, minus and dot only.
                s = ''.join(ch for ch in s if (ch.isdigit() or ch in '.-'))
                return float(s) if s else default
            except Exception:
                return default
        result = []
        for _, row in df.iterrows():
            try:
                raw_date = row.get(date_col)
                if pd.isna(raw_date):
                    continue
                if isinstance(raw_date, datetime):
                    dt = raw_date
                elif isinstance(raw_date, str):
                    # Accept DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD
                    s = raw_date.split('+')[0].strip()
                    if '/' in s and len(s.split('/')[0]) <= 2:
                        dt = datetime.strptime(s[:10], '%d/%m/%Y')
                    elif '-' in s:
                        parts = s.split('-')
                        if len(parts[0]) == 4:
                            dt = parse_date(s)
                        else:
                            dt = datetime.strptime(s[:10], '%d-%m-%Y')
                    else:
                        dt = parse_date(s)
                else:
                    dt = pd.to_datetime(raw_date)
                if hasattr(dt, 'to_pydatetime'):
                    dt = dt.to_pydatetime()
                amount = _to_float(row.get(amount_col), default=0.0)
                quantity = _to_float(row.get(qty_col), default=1.0) or 1.0
                if quantity <= 0:
                    quantity = 1
                product_name = str(row.get(product_col) if product_col else '').strip()
                category = str(row.get(category_col) if category_col else '').strip()
                payment_mode = str(row.get(payment_col) if payment_col else '').strip()
                unit_price = _to_float(row.get(unit_price_col), default=0.0)
                if amount <= 0 and unit_price > 0:
                    amount = float(unit_price) * float(quantity)
                result.append({
                    'date': dt,
                    'amount': amount,
                    'quantity': quantity,
                    'product_id': None,
                    'product_name': product_name or None,
                    'category': category or None,
                    'payment_mode': payment_mode or None,
                    'unit_price': unit_price,
                })
            except (ValueError, TypeError):
                continue
        if not result:
            return [], 'No valid rows found. Ensure required columns are present and Date/Gross Amount have values.'
        return result, None
    except Exception as e:
        return [], f'Could not read Excel file: {str(e)}'


def _rebuild_db_from_uploaded_sales(uploaded_sales):
    """
    Overwrite TinyDB tables from uploaded rows.
    uploaded_sales: list of dicts from _parse_csv_sales/_parse_excel_sales.
    Creates categories/products and writes sales rows with product_id/category_id links.
    """
    if not uploaded_sales:
        return
    t = tables()
    cats_t = t['categories']
    prods_t = t['products']
    sales_t = t['sales']

    # Full replace to match user's upload as the source of truth.
    sales_t.truncate()
    prods_t.truncate()
    cats_t.truncate()

    # Build category ids
    category_to_id = {}
    product_to_id = {}

    def _norm(s):
        return (str(s or '').strip())

    for row in uploaded_sales:
        cat_name = _norm(row.get('category') or 'Uncategorized')
        if cat_name not in category_to_id:
            cid = cats_t.insert({'name': cat_name})
            category_to_id[cat_name] = cid

    # Build products and sales rows
    for row in uploaded_sales:
        product_name = _norm(row.get('product_name') or 'Unknown')
        cat_name = _norm(row.get('category') or 'Uncategorized')
        category_id = category_to_id.get(cat_name)
        unit_price = float(row.get('unit_price') or 0)
        key = (product_name, category_id)
        if key not in product_to_id:
            pid = prods_t.insert({'name': product_name, 'price': unit_price, 'category_id': category_id})
            product_to_id[key] = pid

        product_id = product_to_id[key]
        dt = row.get('date')
        if isinstance(dt, str):
            dt = parse_date(dt.split('+')[0].strip())
        if hasattr(dt, 'to_pydatetime'):
            dt = dt.to_pydatetime()
        quantity = float(row.get('quantity') or 1)
        if quantity <= 0:
            quantity = 1
        gross_amount = float(row.get('amount') or 0)
        if gross_amount <= 0 and unit_price > 0:
            gross_amount = unit_price * quantity
        payment_mode = _norm(row.get('payment_mode') or '')

        sales_t.insert({
            'date': dt.isoformat() if isinstance(dt, datetime) else str(dt),
            'created_at': dt.isoformat() if isinstance(dt, datetime) else str(dt),
            'product_id': product_id,
            'quantity': quantity,
            'price': unit_price,
            'unit_price': unit_price,
            'amount': gross_amount,
            'total': gross_amount,
            'gross_amount': gross_amount,
            'payment_mode': payment_mode or None,
        })

def _report_response(sales, label):
    total = sum(_get_gross(s) for s in sales)
    return render_template('report_basic.html', sales=sales, total=total, label=label)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
