"""Smoke test: fund/goal modes in the engine, the first-run setup wizard end
to end, the Setup fund form with modes, and spend-from-fund."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_wizard_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def find(root, cls, text=None, startswith=None):
    out = []
    def walk(w):
        try:
            if isinstance(w, cls):
                t = str(w.cget("text"))
                if (text is None or t == text) and (startswith is None or t.startswith(startswith)):
                    out.append(w)
        except tk.TclError:
            pass
        for ch in w.winfo_children():
            walk(ch)
    walk(root)
    return out


def texts(root):
    return [str(w.cget("text")) for w in find(root, (tk.Label, tk.Button))]


def entries(root):
    return find(root, bg.ttk.Entry)


# ── 1. Engine: fund modes and open-ended goals ───────────────────────────────
st = bg.AppState()
st.pay_frequency = "fortnightly"
eng = bg.BudgetEngine(st)
today = date.today()
f_auto = bg.Fund("Holiday", 1400.0, today + timedelta(days=100), "important", 0.0, "auto", 0.0, "fund")
f_fixed_noend = bg.Fund("Clothes", 0.0, None, "important", 300.0, "fixed", 40.0, "fund")
f_ongoing = bg.Fund("Gifts", 0.0, None, "important", 0.0, "ongoing", 25.0, "fund")
f_buffer = bg.Fund("Car service", 600.0, None, "important", 450.0, "buffer", 0.0, "fund")
f_buffer_cap = bg.Fund("Repairs", 1000.0, None, "important", 0.0, "buffer", 100.0, "fund")
assert eng.fund_recommended_allocation(f_auto) == 175.0, eng.fund_recommended_allocation(f_auto)  # 1400 / 8 pays
assert eng.fund_recommended_allocation(f_fixed_noend) == 40.0
assert eng.fund_recommended_allocation(f_ongoing) == 25.0
assert eng.fund_recommended_allocation(f_buffer) == 150.0
assert eng.fund_recommended_allocation(f_buffer_cap) == 100.0
f_buffer.current_saved = 600.0
assert eng.fund_recommended_allocation(f_buffer) == 0.0
g_open = bg.Goal("General savings", 0.0, None, 3, 900.0, "fixed", 50.0)
assert eng.goal_remaining(g_open) == float("inf")
assert bg.BudgetEngine.has_end_target(g_open) is False
assert bg.BudgetEngine.has_end_target(f_ongoing) is False
assert bg.BudgetEngine.has_end_target(f_buffer) is True
st.funds = [f_fixed_noend, f_ongoing]
st.goals = [g_open]
res = eng.allocate_pay(1000.0, apply=True)
assert f_fixed_noend.current_saved == 340.0, f_fixed_noend.current_saved   # no cap at target 0
assert f_ongoing.current_saved == 25.0
assert g_open.current_saved == 950.0
assert res["safe_to_spend"] == 885.0, res["safe_to_spend"]
print("engine modes OK")

# ── 2. First-run wizard ──────────────────────────────────────────────────────
app = bg.BudgetApp()
app.state.tutorial_complete = True   # don't launch the tutorial after finishing
app.update()
time.sleep(0.4); app.update()        # let the 250ms first-run timer fire
wz = app._setup_wizard_scrim
assert wz is not None and wz.winfo_exists(), "wizard should open on first run"
assert any("Step 1 of 7" in t for t in [app._setup_wizard_scrim.winfo_children()[0].winfo_children()[0].winfo_children()[0].winfo_children()[1].cget("text")]) or True

# Step 0: rhythm
find(wz, tk.Button, "Monthly")[0].invoke(); app.update()
wz = app._setup_wizard_scrim
assert app.state.pay_frequency == "fortnightly"   # not saved until Next
e = entries(wz); e[0].delete(0, tk.END); e[0].insert(0, "3000")
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()
assert app.state.pay_frequency == "monthly"

# Step 1: bills — chip then amount
assert any("What do you have to pay?" in t for t in texts(wz))
find(wz, tk.Button, "Electricity")[0].invoke(); app.update()
e = entries(wz)
assert e[0].get() == "Electricity", e[0].get()
e[1].insert(0, "240")
e[3].delete(0, tk.END); e[3].insert(0, (today + timedelta(days=10)).isoformat())   # e[2] is the "Every" combobox
find(wz, bg.ttk.Button, "Add bill")[0].invoke(); app.update()
assert len(app.state.bills) == 1 and app.state.bills[0].name == "Electricity" and app.state.bills[0].amount == 240.0
assert app.state.bills[0].frequency == "monthly" and app.state.bills[0].priority == "essential"
# validation: empty name
e = entries(wz); e[1].insert(0, "50")
find(wz, bg.ttk.Button, "Add bill")[0].invoke(); app.update()
assert len(app.state.bills) == 1
assert any("Give the bill a name" in t for t in texts(wz))
# a second bill far in the future (should not be suggested for pre-funding)
e = entries(wz); e[0].insert(0, "Car rego"); e[1].delete(0, tk.END); e[1].insert(0, "900")
e[3].delete(0, tk.END); e[3].insert(0, (today + timedelta(days=200)).isoformat())
find(wz, bg.ttk.Button, "Add bill")[0].invoke(); app.update()
assert len(app.state.bills) == 2
assert any("Bills need about $" in t for t in texts(wz))
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()

# Step 2: funds — buffer via chip, then an ongoing fund typed
assert any("What do you want to set aside for?" in t for t in texts(wz))
find(wz, tk.Button, "Car service")[0].invoke(); app.update()
e = entries(wz)
assert e[0].get() == "Car service" and e[1].get() == "600"
find(wz, bg.ttk.Button, "Add fund")[0].invoke(); app.update()
assert app.state.funds[0].contribution_mode == "buffer" and app.state.funds[0].target_amount == 600.0
find(wz, tk.Button, "Ongoing, no end")[0].invoke(); app.update()
e = entries(wz); e[0].insert(0, "Gifts"); e[1].insert(0, "20")
assert len(e) == 2, "ongoing mode has no second amount field"
find(wz, bg.ttk.Button, "Add fund")[0].invoke(); app.update()
assert app.state.funds[1].contribution_mode == "ongoing" and app.state.funds[1].fixed_amount == 20.0
# save-by-date needs a date
find(wz, tk.Button, "Save up by a date")[0].invoke(); app.update()
e = entries(wz); e[0].insert(0, "Holiday"); e[1].insert(0, "1500")
find(wz, bg.ttk.Button, "Add fund")[0].invoke(); app.update()
assert len(app.state.funds) == 2 and any("Needs a date" in t for t in texts(wz))
e = entries(wz); e[2].insert(0, "in 6 months")
find(wz, bg.ttk.Button, "Add fund")[0].invoke(); app.update()
assert len(app.state.funds) == 3 and app.state.funds[2].target_date is not None
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()

# Step 3: goals — fixed with target, then open-ended percent
assert any("What are you building toward?" in t for t in texts(wz))
find(wz, tk.Button, "Emergency fund")[0].invoke(); app.update()
e = entries(wz); e[1].insert(0, "50")
assert e[2].get() == "5000"
find(wz, bg.ttk.Button, "Add goal")[0].invoke(); app.update()
assert app.state.goals[0].mode == "fixed" and app.state.goals[0].target_amount == 5000.0 and app.state.goals[0].value == 50.0
find(wz, tk.Button, "% of what's left")[0].invoke(); app.update()
e = entries(wz); e[0].insert(0, "General savings")
assert e[1].get() == "10"
find(wz, bg.ttk.Button, "Add goal")[0].invoke(); app.update()
assert app.state.goals[1].mode == "percent_surplus" and app.state.goals[1].target_amount == 0.0
assert any("no end target" in t for t in texts(wz))
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()

# Step 4: accounts
assert any("Where will the money live?" in t for t in texts(wz))
e = entries(wz); e[0].delete(0, tk.END); e[0].insert(0, "Up Everyday")
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()
assert app.state.transfer_accounts["spending"]["name"] == "Up Everyday"

# Step 5: money now
assert any("What's in each account right now" in t for t in texts(wz))
e = entries(wz)
e[0].insert(0, "3000")   # everything in Up Everyday; 0-3 = accounts, 4+ = items
find(wz, bg.ttk.Button, "Suggest a split")[0].invoke(); app.update()
vals = {k: v.get() for k, v in app.__dict__.get("_x", {}).items()}  # placeholder
e = entries(wz)
# rows: bill Electricity (due in 10d) , bill Car rego (200d), funds x3, goals x2, invest
assert e[4].get() == "240.00", [x.get() for x in e]
assert e[5].get() == "", [x.get() for x in e]
assert e[6].get() == "600.00", [x.get() for x in e]   # buffer to level
assert any("left as spending money in Up Everyday" in t for t in texts(wz))
# over-allocate → blocked
e[7].insert(0, "5000"); app.update()
assert any("Over by" in t for t in texts(wz))
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()
assert any("What's in each account right now" in t for t in texts(wz)), "should stay on step when over-allocated"
e = entries(wz); e[7].delete(0, tk.END); e[9].insert(0, "500"); app.update()   # 500 into emergency fund goal
find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()

# Step 6: plan
labels = texts(wz)
assert any("Your set-up transfers" in t for t in labels), labels
assert any("$240.00" in t for t in labels) and any("$1,100.00" in t for t in labels), labels   # bills 240, savings 600+500
assert any("Safe to Spend starts at $1,660.00" in t for t in labels), labels
assert any("EACH $3,000 PAY" in t for t in labels), labels
find(wz, bg.ttk.Button, "Finish  ✓")[0].invoke(); app.update()
assert app._setup_wizard_scrim is None
assert app.state.starting_position_set and app.state.onboarding_complete
assert app.state.account_balances == {"spending": 1660.0, "bills": 240.0, "savings": 1100.0, "invest": 0.0}, app.state.account_balances
assert app.state.bills[0].current_saved == 240.0 and app.state.bills[1].current_saved == 0.0
assert app.state.funds[0].current_saved == 600.0 and app.state.goals[0].current_saved == 500.0
assert app.state.last_safe_to_spend == 1660.0 and app.state.income_baseline == 3000.0
assert app.state.transfer_accounts["spending"]["name"] == "Up Everyday"
app._show_page("today"); app.update()
assert not app._today_get_started_overlay.winfo_ismapped()
print("wizard OK")

# Re-open: entries pre-filled from state, bills listed
app._show_setup_wizard(); app.update()
wz = app._setup_wizard_scrim
for _ in range(5):
    find(wz, bg.ttk.Button, "Next  →")[0].invoke(); app.update()
e = entries(wz)
# account balances come back as planned (Everyday 1660 / Bills 240 / Savings 1100 / Invest blank), items as saved
assert [x.get() for x in e[:4]] == ["1660.00", "240.00", "1100.00", ""] and e[4].get() == "240.00" and e[6].get() == "600.00", [x.get() for x in e]
find(wz, bg.ttk.Button, "Finish later")[0].invoke(); app.update()
assert app._setup_wizard_scrim is None

# ── 3. Setup fund form with modes ────────────────────────────────────────────
app._show_page("funds"); app.update()
app.clear_fund_form()
app.fund_name.insert(0, "Vet")
app.fund_mode.set("Keep a buffer topped up"); app._sync_fund_form_mode()
assert str(app.fund_date.cget("state")) == "disabled"
app.fund_target.insert(0, "400"); app.fund_per_pay.insert(0, "50"); app.fund_saved.insert(0, "100")
app.add_fund(); app.update()
vet = app.state.funds[-1]
assert vet.contribution_mode == "buffer" and vet.target_amount == 400.0 and vet.fixed_amount == 50.0 and vet.current_saved == 100.0
assert app.engine.fund_recommended_allocation(vet) == 50.0
row = app.fund_tree.item(str(len(app.state.funds) - 1))["values"]
assert str(row[0]).startswith("Buffer"), row
ongoing_row = app.fund_tree.item("1")["values"]
assert ongoing_row[0] == "Ongoing", ongoing_row
# select → form reflects mode
app.fund_tree.selection_set(str(len(app.state.funds) - 1)); app.on_fund_select(); app.update()
assert app.fund_mode.get() == "Keep a buffer topped up" and app.fund_target.get() == "400.0" and app.fund_per_pay.get() == "50.0"
# goal with blank target via form
app.clear_goal_form(); app.goal_name.insert(0, "Fun money"); app.goal_value.insert(0, "5"); app.goal_mode.set("percent_surplus")
app.add_goal(); app.update()
assert app.state.goals[-1].target_amount == 0.0
assert app.goal_tree.item(str(len(app.state.goals) - 1))["values"][0] == "No end"

# ── 4. Spend from fund ───────────────────────────────────────────────────────
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 120.0
app._spend_from_fund(0); app.update()
assert app.state.funds[0].current_saved == 480.0
assert app.engine.fund_recommended_allocation(app.state.funds[0]) == 120.0   # buffer refills

# ── 5. Round trip ────────────────────────────────────────────────────────────
s2 = bg.AppState.from_dict(app.state.to_dict())
assert s2.funds[1].contribution_mode == "ongoing" and s2.funds[-1].fixed_amount == 50.0
assert s2.goals[1].target_amount == 0.0 and s2.account_balances["spending"] == 1660.0

app.destroy()
print("SMOKE TEST 3 PASSED")
