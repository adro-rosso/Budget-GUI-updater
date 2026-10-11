import os, sys, tempfile, time
from datetime import date, timedelta
tmp = tempfile.mkdtemp(prefix="budget_shot2_"); os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk, budget_gui as bg
from PIL import ImageGrab
OUT = sys.argv[1]
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app._celebrate = lambda *a, **k: None; app._show_toast = lambda *a, **k: None
app.geometry("1366x768+40+60"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
t = date.today(); st = app.state
rows = [(38, "ACME PTY LTD PAY", 0.0, 2400.0, "income", "Income"), (24, "ACME PTY LTD PAY", 0.0, 2400.0, "income", "Income"), (10, "ACME PTY LTD PAY", 0.0, 2400.0, "income", "Income"),
        (37, "RENT REAL ESTATE", 800.0, 0.0, "discretionary", "Bill"), (23, "RENT REAL ESTATE", 800.0, 0.0, "discretionary", "Bill"),
        (35, "NETFLIX.COM", 22.99, 0.0, "discretionary", "Subscription"), (5, "NETFLIX.COM", 22.99, 0.0, "discretionary", "Subscription"),
        (36, "TELSTRA", 65.0, 0.0, "discretionary", "Bill"), (6, "TELSTRA", 65.0, 0.0, "discretionary", "Bill"),
        (33, "COLES 1234", 120.0, 0.0, "discretionary", "Groceries"), (31, "SHELL", 70.0, 0.0, "discretionary", "Fuel"), (34, "GUZMAN Y GOMEZ", 18.5, 0.0, "discretionary", "Food"), (30, "COLES 1234", 95.0, 0.0, "discretionary", "Groceries")]
for n, desc, out, inn, mt, cat in rows:
    st.transactions.append(bg.TransactionRecord(tx_date=t - timedelta(days=n), description=desc, money_out=out, money_in=inn, fingerprint=f"{n}{desc}", matched_type=mt, category=cat, user_verified=True, needs_review=False))
for n in (38, 24, 10):
    st.incomes.append(bg.IncomeEntry(2400.0, t - timedelta(days=n), "Acme"))
app.refresh_all_views(); app.update()
app._show_statement_setup(); app.update(); time.sleep(0.4); app.update()
x, y = app.winfo_rootx(), app.winfo_rooty(); w, h = app.winfo_width(), app.winfo_height()
ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, "overlay_statement_setup.png"))
[w_.destroy() for w_ in app.winfo_children() if isinstance(w_, tk.Frame) and str(w_.cget("bg")) == bg.UI_HERO and w_.winfo_manager() == "place"]
app._show_page("review"); app.update(); time.sleep(0.4); app.update()
ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, "review_partial.png"))
app.destroy(); print("done")
