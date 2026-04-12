# Execution Instructions

## 1. Install Dependencies

Open a terminal (Command Prompt or PowerShell) and run:

```bash
cd c:\Users\HP\OneDrive\Desktop\Sales
pip install -r requirements.txt
```

If you get permission errors, try:
```bash
pip install --user flask tinydb python-dateutil numpy scikit-learn
```

## 2. (Optional) Seed Sample Data

To add sample categories, products, and sales data:

```bash
python seed_data.py
```

## 3. Run the Application

```bash
python run.py
```

Or:
```bash
python app.py
```

## 4. Open in Browser

Visit: **http://localhost:5000**

The dashboard will load. Use the sidebar to navigate:
- **Dashboard** – Overall sales & bar charts
- **New Sale** – Category → Product → Quantity → Add
- **Manage Categories** – Add/edit/delete categories
- **Manage Products** – Add/edit/delete products
- **Reports** – Today, Monthly, Custom date, Product reports
- **AI Prediction** – Future 30 days & 3 months forecast
- **AI Analyzer** – Custom date report generation

## Troubleshooting

- **ModuleNotFoundError**: Run `pip install -r requirements.txt` again
- **Port in use**: Change port in `run.py` (e.g., `port=5001`)
- **Empty charts**: Run `python seed_data.py` to add sample sales
