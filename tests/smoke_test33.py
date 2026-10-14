"""Smoke test: committed incoming rows are never 'to verify' (the Verify-N count only counts
outgoing rows, and older profiles are migrated at startup); the Coin Catcher starts on the first
arrow press and takes arrows from anywhere on the Score page."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_verify_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def tx(d, desc, out=0.0, inn=0.0):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}")


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
app._celebrate = lambda *a, **k: None; app._show_tier_up_card = lambda *a, **k: None
st = app.state
st.starting_position_date = (today - timedelta(days=10)).isoformat()
rows = [app.matcher.match(tx(today - timedelta(days=30 + 14 * i), "ACME PAYROLL", inn=2400.0)) for i in range(3)]   # history
rows.append(app.matcher.match(tx(today - timedelta(days=2), "ACME PAYROLL", inn=2400.0)))                              # to confirm
shop = app.matcher.match(tx(today - timedelta(days=1), "KMART 1234", 85.0)); shop.user_verified = True; shop.needs_review = False; shop.matched_type = "discretionary"; shop.category = "General"
rows.append(shop)
app.latest_import = rows
app.commit_imported_transactions(); app.update()
assert len(st.pending_income_confirmations) == 1 and len(st.incomes) == 3
assert all(t.user_verified and not t.needs_review for t in st.transactions if t.direction() == "in")
snap = app._next_actions_snapshot()
assert snap["pending_review"] == 0, snap["pending_review"]
assert not any(a["title"].startswith("Verify") for a in snap["actions"]), [a["title"] for a in snap["actions"]]
# an older profile with incoming rows left 'to verify' is migrated at startup
st.transactions[0].user_verified = False; st.transactions[0].needs_review = True
app._startup_progression_migration()
assert st.transactions[0].user_verified
# Coin Catcher: first arrow press starts the round; keys route from the Score page
app._show_page("score"); app.update()
app._select_arcade_game("coin"); app.update()
assert not app._cc_running
app._cc_global_key("right", True); app.update()
assert app._cc_running and app._cc_pressed["right"]
app._cc_global_key("right", False); app.update()
assert not app._cc_pressed["right"]
app._cc_end_round("manual"); app.update()
# on another page the keys are ignored
app._show_page("today"); app.update()
app._cc_global_key("left", True); app.update()
assert not app._cc_running
app.destroy()
print("SMOKE TEST 33 PASSED")
