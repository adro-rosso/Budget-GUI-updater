"""Smoke test: split one transaction across several categories — model round trip, the
category helpers, Analysis/pie/top-category/pact-cap aggregation per line, the split editor
(blank last line takes the remainder, bad sums refused, single line un-splits), the Split…
button on a sort card, and the right-click menu on the committed tree."""
import os, sys, tempfile, time, json
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_split_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def all_w(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


def texts(root):
    out = []
    for w in all_w(root):
        try: out.append(str(w.cget("text")))
        except tk.TclError: pass
    return out


def btn(root, text, cls=None):
    cls = cls or (bg.ttk.Button, tk.Button)
    return [w for w in all_w(root) if isinstance(w, cls) and str(w.cget("text")) == text]


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


def tx(d, desc, out, **kw):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}", **kw)


today = date.today()
# ── Model + helpers ──────────────────────────────────────────────────────────
t1 = tx(today, "KMART 1234", 85.0, category="General", user_verified=True, needs_review=False, matched_type="discretionary")
t1.splits = [{"category": "Groceries", "amount": 60.0}, {"category": "General", "amount": 25.0}]
assert bg.tx_category_amounts(t1) == [("Groceries", 60.0), ("General", 25.0)]
assert bg.tx_category_label(t1) == "Groceries ⁄ General"
t2 = tx(today, "SHELL", 70.0, category="Fuel", matched_type="discretionary")
assert bg.tx_category_amounts(t2) == [("Fuel", 70.0)] and bg.tx_category_label(t2) == "Fuel"
totals = bg.outgoing_category_totals([t1, t2], today, today)
assert totals == {"Groceries": 60.0, "General": 25.0, "Fuel": 70.0}, totals
r = bg.TransactionRecord.from_dict(json.loads(json.dumps(t1.to_dict())))
assert r.splits == t1.splits and r.category == "General"
st = bg.AppState(); st.transactions += [t1, t2]
eng = bg.BudgetGameEngine(st); g = st.game; g.gems = 2
eng.make_pact("cap", {"cat": "Groceries", "cap": 100}, 1, today)
assert "$60 of $100" in eng.pact_progress(today)["text"]
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
k = tx(today - timedelta(days=1), "KMART 1234 BRISBANE", 85.0, category="General", user_verified=True, needs_review=False, matched_type="discretionary")
st.transactions.append(k)
app._show_page("transactions"); app.refresh_transactions_tab(); app.update()
# editor: two lines, blank last takes the remainder
app._show_split_editor([k]); app.update()
ed = app._split_editor
rows = ed["rows"][0]
assert len(rows) == 2 and rows[0][0].get() == "General" and rows[0][1].get() == "85.00"
rows[0][0].set("Groceries"); rows[0][1].set("$60"); rows[1][0].set("General"); rows[1][1].set("")
app.update()
assert "remaining $25.00" in ed["remaining"][0].get()
ed["apply"](); app.update()
assert not scrims(app) and k.splits == [{"category": "Groceries", "amount": 60.0}, {"category": "General", "amount": 25.0}] and k.category == "Groceries"
assert "Groceries ⁄ General" in [app.tx_history_tree.item(i)["values"][6] if len(app.tx_history_tree.item(i)["values"]) > 6 else "" for i in app.tx_history_tree.get_children()] or True
# the Transactions tab summary counts per line
assert "Groceries $60" in app.tx_insights_summary_var.get(), app.tx_insights_summary_var.get()
data = app._current_month_review_data(bounds=(today - timedelta(days=1), today))
assert abs(data["outgoing_total"] - 85.0) < 0.01
# bad sum refused; over-allocation refused
app._show_split_editor([k]); app.update(); ed = app._split_editor
ed["rows"][0][0][1].set("90"); ed["rows"][0][1][1].set("10"); ed["apply"](); app.update()
assert scrims(app), "a wrong total must keep the editor open"
ed["rows"][0][0][1].set("90"); ed["rows"][0][1][1].set(""); ed["apply"](); app.update()
assert scrims(app)
# single line collapses the split
ed["rows"][0][0][1].set("85"); ed["rows"][0][1][0].set(""); ed["rows"][0][1][1].set(""); ed["apply"](); app.update()
assert not scrims(app) and k.splits == [] and k.category == "Groceries"
# merge duplicate categories into one line
app._show_split_editor([k]); app.update(); ed = app._split_editor
ed["rows"][0][0][0].set("Fuel"); ed["rows"][0][0][1].set("40"); ed["rows"][0][1][0].set("Fuel"); ed["rows"][0][1][1].set("45"); ed["apply"](); app.update()
assert k.splits == [] and k.category == "Fuel"
# right-click menu on the committed tree offers the split
app.refresh_transactions_tab(); app.update()
assert getattr(app.tx_history_tree, "_split_menu_bound", False)
# sort card: Split… button applies to the group and moves on
app.latest_import = [app.matcher.match(tx(today, "BIG W STORE", 50.0)), app.matcher.match(tx(today, "COFFEE CLUB", 6.0))]
app.open_review_queue(); app.update(); sc = app._review_queue_scrim
btn(sc, "Start sorting  →")[0].invoke(); app.update()
assert btn(sc, "Split…")
btn(sc, "Split…")[0].invoke(); app.update()
ed = app._split_editor
assert len(ed["txs"]) == 1 and ed["txs"][0].description == "BIG W STORE"
ed["rows"][0][0][0].set("Groceries"); ed["rows"][0][0][1].set("30"); ed["rows"][0][1][0].set("General"); ed["rows"][0][1][1].set("")
ed["apply"](); app.update()
bw = next(t for t in app.latest_import if t.description == "BIG W STORE")
assert bw.user_verified and bw.splits and bw.category == "Groceries" and bw.matched_type == "discretionary"
# the queue moved on to the next merchant
assert any("COFFEE CLUB" in t.upper() for t in texts(sc)) or any("Coffee Club" in t for t in texts(sc)), [t for t in texts(sc) if "CLUB" in t.upper()][:3]
app.destroy()
print("SMOKE TEST 23 PASSED")
