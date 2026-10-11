"""Smoke test: end-of-month report prompt, card, overlay, mark-seen, analysis jump."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_report_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def texts(root):
    out = []
    def walk(w):
        try: out.append(str(w.cget("text")))
        except tk.TclError: pass
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


def find_btn(root, text):
    out = []
    def walk(w):
        if isinstance(w, bg.ttk.Button) and str(w.cget("text")) == text: out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


today = date.today()
first_this = today.replace(day=1)
last_prev = first_this - timedelta(days=1)
prev_mid = last_prev.replace(day=15)
ym_prev = last_prev.strftime("%Y-%m")

app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None

# No activity last month → no prompt
assert app._pending_report_month() is None
app._show_page("today"); app.update()
assert app._month_report_host.winfo_manager() == ""

# Add last-month activity: income + categorised spend
app.state.incomes.append(bg.IncomeEntry(3000.0, prev_mid, "Pay"))
for i, (desc, amt, cat) in enumerate([("WOOLWORTHS", 420.0, "Groceries"), ("NETFLIX", 20.0, "Subscription"),
                                      ("BP FUEL", 160.0, "Fuel"), ("UBER EATS", 95.0, "Food"), ("KMART", 140.0, "General")]):
    t = bg.TransactionRecord(prev_mid + timedelta(days=i), desc, money_out=amt, source_file="s.pdf", fingerprint=f"r{i}",
                             matched_type="discretionary", category=cat, user_verified=True, needs_review=False)
    app.state.transactions.append(t)
assert app._pending_report_month() == (last_prev.year, last_prev.month)
app.refresh_today_tab(); app.update()
assert app._month_report_host.winfo_manager() == "pack"
assert any(f"Your {last_prev:%B} report is ready" in t for t in texts(app._month_report_host))

# Data
d = app._monthly_report_data(last_prev.year, last_prev.month)
assert d["income"] == 3000.0 and abs(d["spent"] - 835.0) < 0.01 and d["net"] > 0 and d["top"][0][0] == "Groceries", d
assert d["tx_count"] == 5

# Startup-style prompt → toast with action
app._maybe_prompt_monthly_report(); app.update()
assert app._toast_stack, "expected a toast"

# Open the report from the card
find_btn(app._month_report_host, "View report")[0].invoke(); app.update()
scrims = [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]
assert scrims, "report overlay should be open"
rt = texts(scrims[-1])
assert any(last_prev.strftime("%B %Y") == t for t in rt), rt[:10]
assert any("$3,000" in t for t in rt) and any("Groceries" in t for t in rt) and any("WHAT STOOD OUT" in t for t in rt)
# Done marks the month as seen and the card goes away
find_btn(scrims[-1], "Done  ✓")[0].invoke(); app.update()
assert app.state.last_month_report_seen == ym_prev
assert app._pending_report_month() is None
assert app._month_report_host.winfo_manager() == ""
assert not any(w.winfo_exists() for w in scrims)

# Open full analysis path jumps to that month on the Analysis tab
app.state.last_month_report_seen = ""
app._show_monthly_report(last_prev.year, last_prev.month); app.update()
scrims = [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]
find_btn(scrims[-1], "Open full analysis  →")[0].invoke(); app.update()
assert app.current_page_key == "review" and app._review_month_offset == -1, (app.current_page_key, app._review_month_offset)
assert app.state.last_month_report_seen == ym_prev

# Skip this month path
app.state.last_month_report_seen = ""; app.refresh_today_tab(); app.update()
find_btn(app._month_report_host, "Skip this month")[0].invoke(); app.update()
assert app.state.last_month_report_seen == ym_prev and app._month_report_host.winfo_manager() == ""

# Round trip
s2 = bg.AppState.from_dict(app.state.to_dict()); assert s2.last_month_report_seen == ym_prev and s2.ui_prefs == app.state.ui_prefs
app.destroy(); print("SMOKE TEST 6 PASSED")
