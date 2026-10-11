"""Smoke test: Analysis periods (month / calendar quarter / financial year / YTD / custom),
text-size scaling of FONT_* constants, sample data load + clear with backup/restore, and
the Settings/nav hooks for both."""
import os, sys, tempfile, time, json
from datetime import date, timedelta
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_b2_")
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


def btn(root, text, cls=None):
    cls = cls or (bg.ttk.Button, tk.Button)
    return [w for w in all_w(root) if isinstance(w, cls) and str(w.cget("text")) == text]


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


# ── Text scale (module level, before any window) ─────────────────────────────
base_body = bg.FONT_BODY
bg.apply_text_scale(1.2); assert bg.FONT_BODY[1] == 12 and bg.TREE_ROWHEIGHT == 41, (bg.FONT_BODY, bg.TREE_ROWHEIGHT)
bg.apply_text_scale(0.5); assert bg.FONT_BODY[1] == 8   # clamped to 0.8
bg.apply_text_scale(1.0); assert bg.FONT_BODY == base_body and bg.TREE_ROWHEIGHT == 34

today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state

# ── Analysis periods ─────────────────────────────────────────────────────────
app._show_page("review"); app.update()
assert set(app._review_period_buttons) == {"month", "qtr", "fy", "ytd", "custom"}
app._review_set_period("qtr"); app.update()
s, e, label, word = app._resolve_review_period()
q = (today.month - 1) // 3
assert s == date(today.year, q * 3 + 1, 1) and e == today and label.startswith(f"Q{q + 1} {today.year}") and "to date" in label, (s, e, label)
app._review_step(-1); app.update()
s2, e2, label2, _ = app._resolve_review_period()
assert e2 == s - timedelta(days=1) and (e2 - s2).days in (89, 90, 91) and "to date" not in label2, (s2, e2, label2)
app._review_step(1); app._review_step(1); app.update()   # can't go past now
assert app._review_month_offset == 0
app._review_set_period("fy"); app.update()
s, e, label, _ = app._resolve_review_period()
fy = today.year if today.month >= 7 else today.year - 1
assert s == date(fy, 7, 1) and e == today and label.startswith(f"FY{fy}"), (s, e, label)
app._review_step(-1); s3, e3, _, _ = app._resolve_review_period()
assert s3 == date(fy - 1, 7, 1) and e3 == date(fy, 6, 30)
app._review_set_period("ytd"); s, e, label, _ = app._resolve_review_period(); assert s == date(today.year, 1, 1) and "YTD" in label
# custom via the overlay
app._review_set_period("custom"); app.update()
sc = scrims(app)[-1]
w = app._review_custom_widgets
w["from"].delete(0, tk.END); w["from"].insert(0, "2026-07-01"); w["to"].delete(0, tk.END); w["to"].insert(0, "2026-06-01")
w["apply"](); app.update()
assert app._review_period_scope == "custom" and app._review_custom == (date(2026, 6, 1), date(2026, 7, 1)) and not scrims(app)
s, e, label, _ = app._resolve_review_period(); assert (s, e) == (date(2026, 6, 1), date(2026, 7, 1)) and "01 Jun 2026" in label
app._review_this_month(); assert app._review_period_scope == "month" and app._review_month_offset == 0
# label shows the active period
app._review_set_period("fy"); app.update()
assert "FY" in app._review_month_label.cget("text")

# ── Text size setting ────────────────────────────────────────────────────────
app._show_page("settings"); app.update()
assert btn(app.settings_tab, "Larger") and btn(app.settings_tab, "Load sample data")
app._restart_app = lambda: None
btn(app.settings_tab, "Larger")[0].invoke(); app.update()
assert st.ui_prefs["text_scale"] == 1.1 and str(app._settings_text_btns[1.1].cget("style")) == "Accent.TButton"
# relaunch reads the pref before building: simulate the startup path
bg.apply_text_scale(st.ui_prefs["text_scale"]); assert bg.FONT_BODY[1] == 11; bg.apply_text_scale(1.0)

# ── Sample data: backup, load, banner, clear/restore ─────────────────────────
st.bills.append(bg.Bill("My real bill", 50.0, today + timedelta(days=5), "monthly", "essential", "bill", 0.0))
app.save_state()
import tkinter.messagebox as mb
mb.askyesno = lambda *a, **k: True
app._settings_load_sample(); app.update()
assert app.state is not st and app.state.ui_prefs.get("sample_mode") and len(app.state.transactions) > 100 and len(app.state.incomes) == 6
assert app.state.bills[0].name == "Rent" and app.engine.state is app.state and app.homestead.state is app.state
assert Path(bg.BudgetApp.SAMPLE_BACKUP_NAME).exists()
assert app._sample_banner.winfo_manager() == "grid" and "SAMPLE" in app._sample_banner.cget("text")
assert app.current_page_key == "today"
# analysis works on the sample
app._show_page("review"); app.update(); app._review_set_period("qtr"); app.update()
data = app._current_month_review_data(bounds=app._resolve_review_period()[:2])
assert data["outgoing_total"] > 0
# clear restores the real data
app._settings_clear_sample(); app.update()
assert not app.state.ui_prefs.get("sample_mode") and app.state.bills and app.state.bills[0].name == "My real bill"
assert not Path(bg.BudgetApp.SAMPLE_BACKUP_NAME).exists() and app._sample_banner.winfo_manager() == ""
# clearing with no backup gives a fresh profile
app.state.ui_prefs["sample_mode"] = True
app._settings_clear_sample(); app.update()
assert not app.state.bills and not app.state.ui_prefs.get("sample_mode")
app.destroy()
print("SMOKE TEST 16 PASSED")
