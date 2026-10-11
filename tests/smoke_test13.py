"""Smoke test: bank links — presets + editor, Statements tab buttons, one-click open
(browser stubbed), Downloads watcher → one-click import of a dropped CSV, statement-due
logic in Do-this-now and reminders, Gerald 'open my bank', Accounts tab row, round trip."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_bank_")
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


opened = []
import webbrowser
webbrowser.open = lambda url, *a, **k: opened.append(url) or True
toasts = []

today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
_orig_toast = app._show_toast
def _spy_toast(message, style="info", duration=3000, action_label="", action_cb=None):
    toasts.append({"message": message, "action": action_cb, "label": action_label})
    return _orig_toast(message, style, duration, action_label, action_cb)
app._show_toast = _spy_toast
app._celebrate = lambda *a, **k: None
st = app.state

# ── Statements tab: no links yet → add via editor preset ─────────────────────
app._show_page("transactions"); app.update()
assert btn(app._bank_links_host, "Add your bank's statement page…")
btn(app._bank_links_host, "Add your bank's statement page…")[0].invoke(); app.update()
sc = scrims(app)[-1]
w = app._bank_editor_widgets
w["preset"].set("CommBank (NetBank)"); w["preset"].event_generate("<<ComboboxSelected>>"); app.update()
assert w["url"].get().startswith("https://netbank.web.commbank.com.au") and w["name"].get() == "CommBank"
w["add"](); app.update()
assert len(st.bank_links) == 1 and st.bank_links[0]["name"] == "CommBank" and st.bank_links[0]["every_days"] == 14
# duplicate refused, bad URL refused, custom link accepted
assert not app._add_bank_link("Again", st.bank_links[0]["url"])[0]
assert not app._add_bank_link("Bad", "nope")[0]
ok, _ = app._add_bank_link("Credit union", "mycu.com.au/login", 30); assert ok and st.bank_links[1]["url"] == "https://mycu.com.au/login"
btn(sc, "Done")[0].invoke(); app.update()
assert btn(app._bank_links_host, "Open CommBank  ↗") or any(t.startswith("Open CommBank") for t in texts(app._bank_links_host)), texts(app._bank_links_host)

# ── Statement due logic ──────────────────────────────────────────────────────
st.last_import_date = today.isoformat()
assert app._statement_due() is None
st.last_import_date = (today - timedelta(days=20)).isoformat()
due = app._statement_due(); assert due and due["idx"] == 0 and due["days"] == 20
app.refresh_transactions_tab(); app.update()
assert any("statement due" in t for t in texts(app._bank_links_host)), texts(app._bank_links_host)
cands = app._do_now_candidates(app._next_actions_snapshot()["actions"])
assert any(c["title"] == "Statement time" and c["cta"] == "Open CommBank" for c in cands), [c["title"] for c in cands]
at = lambda h: datetime.combine(today, datetime.min.time()).replace(hour=h)
msgs = bg._reminder_messages(st, at(10)); assert any(k == "statement" and "20 days" in b for k, _, b in msgs), msgs
st.last_import_date = today.isoformat(); assert not any(k == "statement" for k, _, _ in bg._reminder_messages(st, at(10)))

# ── One click opens the browser and watches a (temp) Downloads folder ────────
dl = Path(tmp) / "Downloads"; dl.mkdir()
app._downloads_dir = lambda: dl
app._open_bank_link(0); app.update()
assert opened and "commbank" in opened[-1] and st.bank_links[0]["last_opened"]
assert any("watching your Downloads" in t["message"] for t in toasts)
# a statement lands in Downloads
time.sleep(0.2)
csv_path = dl / "transactions.csv"
csv_path.write_text("Date,Description,Amount\n" + f"{(today - timedelta(days=1)).strftime('%d/%m/%Y')},COLES 1234,-45.20\n" + f"{(today - timedelta(days=2)).strftime('%d/%m/%Y')},SALARY ACME,2500.00\n", encoding="utf-8")
time.sleep(3.5); app.update(); time.sleep(0.3); app.update()
offer = [t for t in toasts if "New statement in Downloads" in t["message"]]
assert offer and offer[-1]["action"] is not None, [t["message"] for t in toasts][-3:]
offer[-1]["action"](); app.update()
assert len(app.latest_import) == 2 and st.last_import_date == today.isoformat(), len(app.latest_import)
assert app._statement_due() is None
for w_ in list(app.winfo_children()):
    if isinstance(w_, tk.Frame) and str(w_.cget("bg")) == bg.UI_HERO and w_.winfo_manager() == "place": w_.destroy()
app.update()

# ── Gerald ───────────────────────────────────────────────────────────────────
ga = getattr(app, "gerald_assistant", None) or bg.GeraldAssistant(app)
n0 = len(opened)
reply = ga._route("open my credit union bank page"); app.update(); time.sleep(0.3); app.update()
assert "Credit union" in reply[0] and len(opened) == n0 + 1 and "mycu" in opened[-1], (reply, opened[-1])
app._downloads_watch_token = None

# ── Accounts tab row + round trip ────────────────────────────────────────────
app._show_page("setup"); app._show_setup_sub("accounts"); app.update()
assert btn(app.accounts_tab, "Manage bank links…") and "CommBank, Credit union" in app._bank_links_summary_var.get()
s2 = bg.AppState.from_dict(json.loads(json.dumps(st.to_dict())))
assert [l["name"] for l in s2.bank_links] == ["CommBank", "Credit union"] and s2.last_import_date == today.isoformat() and s2.ui_prefs == st.ui_prefs
app.destroy()
print("SMOKE TEST 13 PASSED")
