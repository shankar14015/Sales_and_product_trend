# How to Test the Sales App

## 1. Install and run

```bash
cd sales
pip install -r requirements.txt
python run.py
```

## 2. Add sample data (if database is empty)

In a **new terminal** (keep the app running in the first):

```bash
cd sales
python seed_data.py
```

This adds categories, products, and about 30 days of sample sales.

## 3. Test in the browser

1. Open **http://localhost:5000**
2. You should see the **login** page.
3. Log in: **username** `admin`, **password** `admin123`
4. You should be redirected to the **Dashboard** (today’s sales, charts).
5. In the sidebar, go to **Reports → AI Prediction**.
6. Check:
   - Page says: “Trained on **past 6 months** … Predicting **next 6 months**”
   - **Next 6 Months Prediction** chart shows 6 bars (6 future months).
   - Table **Monthly Predictions (Next 6 Months)** has 6 rows.

If you see that, the 6‑month prediction is working.

## 4. Quick checklist

| Test | What to do | Expected |
|------|------------|----------|
| Login | Go to http://localhost:5000, enter admin / admin123 | Redirect to dashboard |
| Logout | Click **Logout** at bottom of sidebar | Back to login page |
| Dashboard | Open Dashboard | Today’s sales, 2 charts |
| AI Prediction | Reports → AI Prediction | 6 months chart + table, “past 6 months” text |

## 5. If AI Prediction shows no data

- Run `python seed_data.py` once to add sample sales.
- If you already ran it before, the DB might have data; refresh the AI Prediction page.
