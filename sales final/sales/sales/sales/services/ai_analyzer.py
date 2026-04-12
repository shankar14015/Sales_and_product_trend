"""AI Sale Analyzer & Report Generator."""
from datetime import datetime, timedelta
from collections import defaultdict


class SaleAnalyzer:
    """Analyze sales data and generate natural language reports."""

    def __init__(self, sales_data, products_map=None, categories_map=None):
        self.sales_data = sales_data
        self.products_map = products_map or {}
        self.categories_map = categories_map or {}

    def _parse_date(self, d):
        if isinstance(d, datetime):
            return d
        return datetime.fromisoformat(str(d).replace('Z', '+00:00').split('+')[0])

    def analyze_period(self, start_date=None, end_date=None):
        """Analyze sales for a date range."""
        filtered = []
        for s in self.sales_data:
            dt = self._parse_date(s.get('date', s.get('created_at', '')))
            if start_date and dt.date() < start_date:
                continue
            if end_date and dt.date() > end_date:
                continue
            filtered.append(s)

        def _gross(s):
            return s.get('gross_amount', s.get('amount', s.get('total', 0)))

        total_amount = sum(_gross(s) for s in filtered)
        total_quantity = sum(s.get('quantity', 1) for s in filtered)
        transaction_count = len(filtered)

        # Daily breakdown
        daily = defaultdict(lambda: {'amount': 0, 'count': 0})
        for s in filtered:
            dt = self._parse_date(s.get('date', s.get('created_at', '')))
            key = dt.strftime('%Y-%m-%d')
            daily[key]['amount'] += _gross(s)
            daily[key]['count'] += 1

        # Product breakdown
        product_sales = defaultdict(lambda: {'amount': 0, 'quantity': 0})
        for s in filtered:
            pid = s.get('product_id', s.get('product', 'Unknown'))
            name = self.products_map.get(pid, str(pid))
            product_sales[name]['amount'] += _gross(s)
            product_sales[name]['quantity'] += s.get('quantity', 1)

        top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:5]
        avg_per_transaction = total_amount / transaction_count if transaction_count else 0

        return {
            'total_amount': total_amount,
            'total_quantity': total_quantity,
            'transaction_count': transaction_count,
            'avg_per_transaction': avg_per_transaction,
            'daily': dict(daily),
            'top_products': top_products,
            'filtered_count': len(filtered),
        }

    def generate_report(self, start_date=None, end_date=None, report_type='full'):
        """Generate natural language report."""
        analysis = self.analyze_period(start_date, end_date)
        lines = []

        period = "custom period"
        if start_date and end_date:
            period = f"{start_date} to {end_date}"
        elif start_date:
            period = f"from {start_date}"
        elif end_date:
            period = f"until {end_date}"

        lines.append(f"# Sales Report — {period}")
        lines.append("")
        lines.append(f"**Summary**")
        lines.append(f"- Total Gross: ₹{analysis['total_amount']:,.2f}")
        lines.append(f"- Total Quantity Sold: {analysis['total_quantity']:,.0f}")
        lines.append(f"- Number of Transactions: {analysis['transaction_count']}")
        lines.append(f"- Average Gross per Transaction: ₹{analysis['avg_per_transaction']:,.2f}")
        lines.append("")

        if analysis['top_products']:
            lines.append("**Top Selling Products**")
            for i, (name, data) in enumerate(analysis['top_products'], 1):
                lines.append(f"  {i}. {name}: ₹{data['amount']:,.2f} ({data['quantity']} units)")
            lines.append("")

        # Insights
        lines.append("**Insights**")
        if analysis['transaction_count'] > 0:
            lines.append(f"- Gross is driven by {len(analysis['top_products'])} key products.")
            if analysis['avg_per_transaction'] > 0:
                lines.append(f"- Strong average gross per transaction: ₹{analysis['avg_per_transaction']:,.2f}.")
        else:
            lines.append("- No sales data in the selected period.")

        return "\n".join(lines)
