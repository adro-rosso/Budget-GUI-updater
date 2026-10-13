"""Smoke test: the bill interview — Gerald asks one question per card; Yes → add with an
amount / 'on my statement' (amount pending, filled by the first matching charge) / 'remind
me' (stays on Today); multi-pick streaming; Today card, Plan row 'amount?', Do-this-now,
the sort-card banner that fills a pending amount, commit filling it, Undo restoring it."""
import os, sys, tempfile, time
from datetime import date, timedelta, datetime

tmp = tempfile.mkdtemp(prefix="budget_interview_")
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


def entries(root):
    return [w for w in all_w(root) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]


def tx(d, desc, out):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
st.bills.append(bg.Bill("Electricity", 300.0, today + timedelta(days=20), "quarterly", "essential"))
app._show_page("setup"); app.update()
app._show_bill_interview(); app.update()
sc = app._bill_interview_scrim; iv = app._bill_interview
ids = [i["id"] for i in bg.BILL_INTERVIEW]
tt = texts(sc)
assert any("Do you pay rent or a mortgage?" in t for t in tt), tt[:6]
# Q1 rent: Yes → amount 480 fortnightly (typed)
btn(sc, "Yes  (Enter)")[0].invoke(); app.update()
assert btn(sc, "Add with this amount  ✓") and btn(sc, "It'll be on my statement") and btn(sc, "Not sure — remind me")
e = entries(sc); e[0].delete(0, tk.END); e[0].insert(0, "$480"); app.update()
btn(sc, "Add with this amount  ✓")[0].invoke(); app.update()
rent = next(b for b in st.bills if b.name == "Rent / Mortgage")
assert rent.amount == 480.0 and rent.frequency == "fortnightly" and rent.amount_pending == "" and "rent" in rent.keywords
# Q2 electricity is already in the plan → the card says so; No moves on
assert any("Already in your plan: Electricity" in t for t in texts(sc))
btn(sc, "No")[0].invoke(); app.update()
# walk to the gym question with No, answer 'on my statement'
while not any("gym or fitness" in t for t in texts(sc)):
    btn(sc, "No")[0].invoke(); app.update()
btn(sc, "Yes  (Enter)")[0].invoke(); app.update()
assert any(t.startswith("typical $35") for t in texts(sc)), [t for t in texts(sc) if "typical" in t]
btn(sc, "It'll be on my statement")[0].invoke(); app.update()
gym = next(b for b in st.bills if b.name == "Gym")
assert gym.amount == 0.0 and gym.amount_pending == "statement" and gym.amount_pending_since == today.isoformat() and "anytime" in gym.keywords
# streaming (multi-pick): jump straight to it through the exposed state
iv["idx"] = ids.index("streaming"); iv["open"] = False; iv["render"](); app.update()
btn(sc, "Yes  (Enter)")[0].invoke(); app.update()
iv["mode_vars"]["Netflix"].set(True); iv["mode_vars"]["Stan"].set(True); app.update()
btn(sc, "Add ticked with these amounts  ✓")[0].invoke(); app.update()
nf = next(b for b in st.bills if b.name == "Netflix"); assert nf.amount == 20.0 and nf.category == "Subscription" and nf.keywords == ["netflix"]
assert any(b.name == "Stan" for b in st.bills) and not any(b.name == "Disney+" for b in st.bills)
# a 'remind me' one: pet insurance
iv["idx"] = ids.index("pet_ins"); iv["open"] = False; iv["render"](); app.update()
btn(sc, "Yes  (Enter)")[0].invoke(); app.update()
btn(sc, "Not sure — remind me")[0].invoke(); app.update()
pet = next(b for b in st.bills if b.name == "Pet insurance"); assert pet.amount_pending == "revisit"
btn(sc, "Skip the rest  →")[0].invoke(); app.update()
assert any("bill" in t and "found" in t for t in texts(sc)), [t for t in texts(sc)][:6]
assert any(t.startswith("From your next statement: Gym") for t in texts(sc)) and any(t.startswith("To come back to: Pet insurance") for t in texts(sc))
btn(sc, "Done  ✓")[0].invoke(); app.update()
assert app._bill_interview_scrim is None
# Today card + Plan row + Setup tree
app._show_page("today"); app.refresh_today_tab(); app.update()
tt = texts(app._pending_bills_host)
assert any(t == "BILLS WITHOUT AN AMOUNT · 2" for t in tt), tt
assert any(t.startswith("Gym · fortnightly · waiting for a statement charge") for t in tt) and any("Pet insurance" in t and "come back" in t for t in tt), tt
app._show_page("setup"); app.refresh_plan_tab(); app.update()
assert sum(1 for t in texts(app._plan_host) if t == "amount?") == 2
assert any("the next statement charge fills it in" in t for t in texts(app._plan_host))
app.refresh_bills(); app.update()
assert any(app.bill_tree.item(i)["values"][0] == "amount?" for i in app.bill_tree.get_children())
# Do-this-now: a 'revisit' bill 2+ days old surfaces
pet.amount_pending_since = (today - timedelta(days=3)).isoformat()
cands = app._do_now_candidates([])
assert any(c["title"] == "Set the amount for Pet insurance" for c in cands), [c["title"] for c in cands]
# set it through the dialog
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 38.5
app._ask_bill_amount(pet); app.update()
assert pet.amount == 38.5 and pet.amount_pending == "" and app._pending_amount_bills() == [gym]
# Statement path: an ANYTIME FITNESS charge → matcher links it to Gym; the sort card offers to fill the amount
app.latest_import = [app.matcher.match(tx(today - timedelta(days=3), "ANYTIME FITNESS CHERMSIDE", 24.95)),
                     app.matcher.match(tx(today - timedelta(days=17), "ANYTIME FITNESS CHERMSIDE", 24.95)),
                     app.matcher.match(tx(today - timedelta(days=1), "MYSTERY SHOP 77", 12.0))]
assert app.latest_import[0].matched_type == "linked_bill" and app.latest_import[0].matched_target == "Gym"
app._show_page("transactions"); app.update()
app.open_review_queue(); app.update(); rq = app._review_queue_scrim
btn(rq, "Start sorting  →")[0].invoke(); app.update()
for _ in range(3):
    if any("Looks like your Gym bill" in t for t in texts(rq)):
        break
    nxt = [b for b in all_w(rq) if isinstance(b, bg.ttk.Button) and "Skip" in str(b.cget("text"))]
    nxt[0].invoke(); app.update()
assert any("Looks like your Gym bill" in t for t in texts(rq)), [t for t in texts(rq)][:12]
fill = btn(rq, "Use $24.95 and link  ✓"); assert fill, [str(b.cget("text")) for b in all_w(rq) if isinstance(b, bg.ttk.Button)]
fill[0].invoke(); app.update()
assert gym.amount == 24.95 and gym.amount_pending == "" and all(t.matched_type == "linked_bill" and t.user_verified for t in app.latest_import[:2])
rq.destroy(); app._review_queue_scrim = None; app.update()
# Commit path fills a pending amount too (and Undo restores it)
gym.amount = 0.0; gym.amount_pending = "statement"; gym.amount_pending_since = today.isoformat()
for t in app.latest_import[:2]:
    t.user_verified = True; t.needs_review = False
app.latest_import[2].user_verified = True; app.latest_import[2].needs_review = False; app.latest_import[2].matched_type = "discretionary"; app.latest_import[2].category = "General"
app._toast_stack.clear()
app.commit_imported_transactions(); app.update()
assert gym.amount == 24.95 and gym.amount_pending == "", (gym.amount, gym.amount_pending)
labels = [str(w.cget("text")) for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label)]
assert any("Amount set from the statement: Gym $24.95" in l for l in labels), labels
app._undo_last_commit(); app.update()
assert gym.amount == 0.0 and gym.amount_pending == "statement"
# Reminder + Gerald intent
gym.amount_pending_since = (today - timedelta(days=5)).isoformat()
msgs = bg._reminder_messages(st, datetime.combine(today, datetime.min.time()).replace(hour=10))
assert any(k == "bill_amount" and "Gym" in body for k, _, body in msgs), msgs
assert app.gerald_assistant._classify_intent("find my bills") == "bill_interview"
assert app.gerald_assistant._classify_intent("ask me what i pay for") == "bill_interview"
assert app.gerald_assistant._classify_intent("list my bills") != "bill_interview"
# wizard bills step has the button; plan tab has it
app._show_setup_wizard(); app.update(); wz = app._setup_wizard_scrim
btn(wz, "Next  →")[0].invoke(); app.update()
assert btn(wz, "Ask me what I pay for")
btn(wz, "Finish later")[0].invoke(); app.update()
assert btn(app.plan_tab, "Find my bills")
app.destroy()
print("SMOKE TEST 27 PASSED")
