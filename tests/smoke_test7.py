"""Smoke test: cost guide, investing helper, quarterly bills, persisted investing rules, Gerald answers."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_guide_")
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


def find_btn(root, text, cls=None):
    cls = cls or bg.ttk.Button
    out = []
    def walk(w):
        if isinstance(w, cls) and str(w.cget("text")) == text: out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


# ── Data + pure helpers ──────────────────────────────────────────────────────
assert bg.COST_GUIDE_BY_ID["rego"]["typical"] == 871 and bg.REGO_ESTIMATES_QLD["5–6 cyl"] == 1096
assert bg.monthly_equivalent(518, "quarterly") == 518 / 3 and bg.monthly_equivalent(871, "yearly") == 871 / 12
assert [e["id"] for e in bg._guide_lookup("how much is rego in qld")] == ["rego"]
assert bg._guide_lookup("how much is car insurance")[0]["id"] == "car_insurance"    # longest keyword wins
assert bg._guide_lookup("how much do i have left") == []
eng = bg.BudgetEngine(bg.AppState())
assert eng.next_due_date(date(2026, 1, 31), "quarterly") == date(2026, 4, 30)
assert eng.next_due_date(date(2026, 11, 15), "quarterly") == date(2027, 2, 15)
print("data OK")

# ── Live app ────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
today = date.today()
app.state.bills = [bg.Bill("Rent", 1800.0, today + timedelta(days=10), "monthly", "essential", "bill", 0.0),
                   bg.Bill("Electricity", 518.0, today + timedelta(days=20), "quarterly", "essential", "bill", 0.0),
                   bg.Bill("Gym", 35.0, today + timedelta(days=3), "fortnightly", "optional", "bill", 0.0)]
# essential monthly = 1800 + 172.67 = 1972.67 → emergency 3× ≈ 5900
assert abs(app._essential_monthly_bills() - (1800 + 518 / 3)) < 0.01
target, why = app._emergency_fund_suggestion(); assert target == 5900.0 and "three months" in why.lower(), (target, why)
assert app._guide_amount_for(bg.COST_GUIDE_BY_ID["rego"], "7–8 cyl") == 1300.0
assert app._guide_amount_for(bg.COST_GUIDE_BY_ID["emergency"]) == 5900.0

# Cost guide overlay → rego with cylinder picker → fills the bills form
app._show_page("bills"); app.update()
find_btn(app.bills_tab, "Cost guide")[0].invoke(); app.update()
sc = scrims(app)[-1]
assert any("COST GUIDE" in t for t in texts(sc))
# select rego via its row (click handler bound to the row label)
rows = [w for w in sc.winfo_children()]
# search filter: type "rego" and pick
entries = [w for w in sc.winfo_children()]
def all_widgets(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out
q = [w for w in all_widgets(sc) if isinstance(w, bg.ttk.Entry)][0]
q.insert(0, "rego"); app.update()
row_lbl = [w for w in all_widgets(sc) if isinstance(w, tk.Label) and str(w.cget("text")) == "Car registration (QLD)"]
assert row_lbl, texts(sc)
row_lbl[0].event_generate("<Button-1>"); app.update()
assert find_btn(sc, "5–6 cyl ≈ $1096", tk.Button), [t for t in texts(sc) if "cyl" in t]
find_btn(sc, "5–6 cyl ≈ $1096", tk.Button)[0].invoke(); app.update()
amt_entries = [w for w in all_widgets(sc) if isinstance(w, bg.ttk.Entry)]
assert amt_entries[-1].get() == "1096", [e.get() for e in amt_entries]
find_btn(sc, "Use this  →")[0].invoke(); app.update()
assert app.current_page_key == "setup"
assert app.bill_name.get() == "Car registration" and app.bill_amount.get() == "1096.00" and app.bill_frequency.get() == "yearly" and app.bill_priority.get() == "essential"
assert "quarterly" in app.bill_frequency["values"]

# Guide → goal (emergency) fills goal form with computed target
app._show_cost_guide("goal"); app.update(); sc = scrims(app)[-1]
lbl = [w for w in all_widgets(sc) if isinstance(w, tk.Label) and str(w.cget("text")) == "Emergency fund"][0]
lbl.event_generate("<Button-1>"); app.update()
assert any("$5,900" in t for t in texts(sc)), [t for t in texts(sc) if "5,9" in t]
find_btn(sc, "Use this  →")[0].invoke(); app.update()
assert app.goal_name.get() == "Emergency fund" and app.goal_target.get() == "5900" and app.goal_priority.get() == "essential"

# Guide → fund (Christmas) sets auto mode + 20 Dec date
app._show_cost_guide("fund"); app.update(); sc = scrims(app)[-1]
lbl = [w for w in all_widgets(sc) if isinstance(w, tk.Label) and str(w.cget("text")) == "Christmas & gifts"][0]
lbl.event_generate("<Button-1>"); app.update()
find_btn(sc, "Use this  →")[0].invoke(); app.update()
assert app.fund_name.get() == "Christmas & gifts" and app.fund_target.get() == "800.00" and app.fund_date.get().endswith("-12-20")

# Wizard pick path: on_pick callback fills prefill
got = {}
app._show_cost_guide("bill", on_pick=lambda e, amt, ex: got.update({"e": e["id"], "amt": amt, "freq": ex["frequency"]})); app.update()
sc = scrims(app)[-1]
lbl = [w for w in all_widgets(sc) if isinstance(w, tk.Label) and str(w.cget("text")) == "Electricity"][0]
lbl.event_generate("<Button-1>"); app.update()
find_btn(sc, "Use this  →")[0].invoke(); app.update()
assert got == {"e": "electricity", "amt": 518.0, "freq": "quarterly"}, got

# Investment recommendation matrix
r = app._invest_recommendation
assert r("3plus", "no", "long", "high")[0] == 20
assert r("3plus", "yes", "long", "high")[0] == 0
assert r("1to3", "no", "short", "high")[0] == 5
assert r("3plus", "no", "mid", "medium")[0] == 10        # cap 15 × 0.8 = 12 → rounds to 10
assert r("none", "no", "long", "high")[0] == 0
assert r("3plus", "no", "long", "low")[0] == 10
pct, buf, lines = r("under1", "no", "long", "medium"); assert pct == 5 and buf == 500.0 and any("week" in l for l in lines), (pct, buf)

# Helper overlay applies and persists
app._show_invest_helper(); app.update(); sc = scrims(app)[-1]
find_btn(sc, "3+ months", tk.Button)[0].invoke(); app.update()
find_btn(sc, "Buy more", tk.Button)[0].invoke(); app.update()
assert any("Suggested: 20% of surplus" in t for t in texts(sc)), [t for t in texts(sc) if "Suggested" in t]
find_btn(sc, "Apply this  ✓")[0].invoke(); app.update()
assert app.rule_settings["investment_mode"] == "percent" and app.rule_settings["investment_value"] == 20.0
assert app.state.investment_rules["investment_value"] == 20.0
s2 = bg.AppState.from_dict(app.state.to_dict()); assert s2.investment_rules["investment_mode"] == "percent"
# a fresh app in this folder loads the persisted rules
app.destroy()
app2 = bg.BudgetApp(); app2.focus_force(); app2.update()
assert app2.rule_settings["investment_value"] == 20.0 and app2.invest_value_entry.get() == "20.0", app2.rule_settings
# Gerald
app2.gerald_assistant.handle("how much is rego?")
reply = app2.gerald_assistant.transcript[-1]["text"]
assert "$871" in reply and "Car registration" in reply, reply
app2.gerald_assistant.handle("how much should i invest each pay?"); app2.update()
assert scrims(app2) and any("INVESTING" in t for t in texts(scrims(app2)[-1]))
app2.destroy()
print("SMOKE TEST 7 PASSED")
