# Sales Management System

A Flask-based sales management application with category/product selection, sales tracking, reports, and AI-powered prediction & analysis.

## Features

- **Dashboard** – Overall sales, bar charts (monthly & today by hour)
- **New Sale** – Category → Product selection, quantity & price, add to sale
- **Manage Categories** – Add, edit, delete categories
- **Manage Products** – Add, edit, delete products with category & price
- **Reports**
  - Today's Sales
  - Monthly Sales Growth & Graph
  - Product Reports (all products with sales)
  - Custom Date Report
- **AI Prediction** – Upload **CSV** (2 months) or Excel; predict **next 6 months Gross**. Uses columns: Date, Product, Category, Quantity, Unit Price, Gross Amount, Payment Mode.
- **AI Analyzer** – Custom date range report generation with insights

All sales and predictions show **Gross** (gross amount) everywhere.

## Tech Stack

- Python 3.8+
- Flask
- TinyDB (file-based JSON database)
- Chart.js (charts)
- scikit-learn (AI prediction)

## Setup & Execution

### 1. Create virtual environment (optional but recommended)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# or: source venv/bin/activate   # Linux/Mac
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
python run.py
```

Or:

```bash
python app.py
```

### 4. Open in browser

Visit: **http://localhost:5000**

## Project Structure

```
Sales/
├── app.py              # Main Flask app & routes
├── config.py           # Configuration
├── run.py              # Entry point
├── requirements.txt
├── README.md
├── data/               # TinyDB JSON (auto-created)
├── database/
│   └── db.py           # TinyDB setup
├── services/
│   ├── ai_predictor.py # Sales prediction (future days/months)
│   └── ai_analyzer.py  # Report generator
├── templates/          # HTML templates
└── static/
    ├── css/style.css
    └── js/main.js
```

## Usage

1. **Load dataset.csv (optional)** – Run `python seed_from_dataset.py` to merge CSV data, or `python seed_from_dataset.py --replace` to replace DB with CSV (Date, Product, Category, Quantity, Unit Price, Gross Amount, Payment Mode).
2. **Add categories** – Go to Manage Categories, add e.g. "Electronics", "Clothing"
3. **Add products** – Manage Products, add products with category and price
4. **Make sales** – New Sale: select category → product, set quantity, Add to Sale, then Complete Sale (stored as Gross).
5. **View reports** – Dashboard, Today, Monthly, Product reports, or Custom Date (all show Gross).
6. **AI Prediction** – Upload a **CSV** (2 months) or Excel file; get **next 6 months Gross** prediction. Or use DB data (last 6 months).
7. **AI Analyzer** – Pick date range and generate AI report (Gross).

## License

MIT
