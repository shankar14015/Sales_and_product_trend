"""AI-powered sales prediction for future months/days."""
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from collections import defaultdict


class SalesPredictor:
    """Predict future sales using linear regression on historical data."""

    def __init__(self, sales_data):
        """
        sales_data: list of dicts with keys: date, amount, quantity, product_id
        """
        self.sales_data = sales_data
        self.model = LinearRegression()

    def _prepare_features(self, dates):
        """Convert dates to numeric features (days since epoch)."""
        base = min(dates)
        return np.array([(d - base).days for d in dates]).reshape(-1, 1)

    def predict_daily(self, days_ahead=30):
        """Predict sales for next N days. Works even with 0 or 1 day of history."""
        daily = defaultdict(lambda: {'amount': 0, 'quantity': 0})
        def _amt(s):
            return s.get('gross_amount', s.get('amount', s.get('total', 0)))
        if self.sales_data:
            for s in self.sales_data:
                dt = s['date'] if isinstance(s['date'], datetime) else datetime.fromisoformat(s['date'])
                key = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                daily[key]['amount'] += _amt(s)
                daily[key]['quantity'] += s.get('quantity', 1)

        dates = sorted(daily.keys())
        last_day = max(dates) if dates else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        avg_amount = sum(daily[d]['amount'] for d in dates) / len(dates) if dates else 0
        avg_qty = sum(daily[d]['quantity'] for d in dates) / len(dates) if dates else 0

        if len(dates) < 2:
            # 0 or 1 day: use average (or 0) for all future days so chart is not empty
            predictions = []
            for i in range(1, days_ahead + 1):
                future_date = last_day + timedelta(days=i)
                predictions.append({
                    'date': future_date.strftime('%Y-%m-%d'),
                    'predicted_amount': round(avg_amount, 2),
                    'predicted_quantity': round(avg_qty, 1),
                })
            return predictions

        X = self._prepare_features(dates)
        amounts = np.array([daily[d]['amount'] for d in dates])
        quantities = np.array([daily[d]['quantity'] for d in dates])
        self.model.fit(X, amounts)
        predictions = []
        for i in range(1, days_ahead + 1):
            future_date = last_day + timedelta(days=i)
            x_pred = np.array([(future_date - min(dates)).days]).reshape(-1, 1)
            pred_amount = max(0, float(self.model.predict(x_pred)[0]))
            pred_qty = max(0, quantities.mean()) if len(quantities) > 0 else 0
            predictions.append({
                'date': future_date.strftime('%Y-%m-%d'),
                'predicted_amount': round(pred_amount, 2),
                'predicted_quantity': round(pred_qty, 1),
            })
        return predictions

    def predict_monthly(self, months_ahead=3):
        """Predict sales for next N months. Works even with 0 or 1 month of history."""
        monthly = defaultdict(lambda: {'amount': 0, 'quantity': 0})
        def _amt(s):
            return s.get('gross_amount', s.get('amount', s.get('total', 0)))
        if self.sales_data:
            for s in self.sales_data:
                dt = s['date'] if isinstance(s['date'], datetime) else datetime.fromisoformat(s['date'])
                key = (dt.year, dt.month)
                monthly[key]['amount'] += _amt(s)
                monthly[key]['quantity'] += s.get('quantity', 1)

        keys = sorted(monthly.keys())
        now = datetime.now()
        # Start from next month after last data (or next month from now if no data)
        if keys:
            last_key = keys[-1]
            start_year, start_month = last_key[0], last_key[1]
        else:
            start_year, start_month = now.year, now.month

        # If we have 2+ months, fit model once
        if keys and len(keys) >= 2:
            X = np.array([k[0] * 12 + k[1] for k in keys]).reshape(-1, 1)
            amounts_arr = np.array([monthly[k]['amount'] for k in keys])
            self.model.fit(X, amounts_arr)
        last_observed = monthly[keys[-1]]['amount'] if keys else 0
        avg_observed = (sum(monthly[k]['amount'] for k in keys) / len(keys)) if keys else 0

        predictions = []
        for i in range(1, months_ahead + 1):
            m = start_month + i
            y = start_year
            while m > 12:
                m -= 12
                y += 1
            if keys and len(keys) >= 2:
                x_pred = np.array([[y * 12 + m]])
                pred_amount = float(self.model.predict(x_pred)[0])
                # Linear regression can extrapolate negative values; fallback to a stable baseline.
                if pred_amount <= 0:
                    pred_amount = max(last_observed, avg_observed, 0)
                else:
                    pred_amount = max(0, pred_amount)
            elif keys:
                pred_amount = monthly[keys[-1]]['amount']
            else:
                pred_amount = 0
            predictions.append({
                'year': y,
                'month': m,
                'label': f'{y}-{m:02d}',
                'predicted_amount': round(pred_amount, 2),
            })
        return predictions

    def predict_by_product(self, product_id, days_ahead=30):
        """Predict daily sales for a specific product (by product_id)."""
        filtered = [s for s in self.sales_data if s.get('product_id') == product_id]
        return SalesPredictor(filtered).predict_daily(days_ahead)

    def predict_monthly_by_product(self, product_id, months_ahead=6):
        """Predict monthly sales for a specific product (by product_id)."""
        filtered = [s for s in self.sales_data if s.get('product_id') == product_id]
        return SalesPredictor(filtered).predict_monthly(months_ahead)

    def predict_by_product_key(self, get_key):
        """
        Group sales by a key (e.g. product_name or product_id) and return predictions per key.
        get_key: function(sale_doc) -> hashable key.
        Returns: dict key -> {'daily': [...], 'monthly': [...]}
        """
        from collections import defaultdict
        grouped = defaultdict(list)
        for s in self.sales_data:
            k = get_key(s)
            if k is not None:
                grouped[k].append(s)
        result = {}
        for key, sales_list in grouped.items():
            if not sales_list:
                continue
            sub = SalesPredictor(sales_list)
            result[key] = {
                'daily': sub.predict_daily(30),
                'monthly': sub.predict_monthly(6),
            }
        return result
