"""Smoke test: Homestead phase 3 — decor shop (Gold/Gem sink), seasonal palettes unlocked by
the top season tier, the scene drawing decor and palette, the legendary background awarded
at tier 5, and the share-as-image path with ImageGrab stubbed."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_b4_")
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


def lbl(root, text):
    return [w for w in all_w(root) if isinstance(w, tk.Label) and str(w.cget("text")) == text]


today = date.today()
# ── Engine ───────────────────────────────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
assert not eng.buy_decor("flowerbed")[0] and not eng.buy_decor("nope")[0]
g.total_score = 100; ok, msg = eng.buy_decor("flowerbed"); assert ok and g.total_score == 40 and g.homestead_decor == ["flowerbed"]
assert not eng.buy_decor("flowerbed")[0]
g.gems = 1; assert not eng.buy_decor("beehive")[0]; g.gems = 2; assert eng.buy_decor("beehive")[0] and g.gems == 0
assert not eng.set_palette("autumn")[0] and eng.set_palette("classic")[0]
season = bg.season_for_month(today.month)
assert bg.season_for_month(1) == "summer" and bg.season_for_month(4) == "autumn" and bg.season_for_month(7) == "winter" and bg.season_for_month(10) == "spring"
g.season_xp = 5000
for i in range(len(bg.SEASON_TIERS) - 1):
    eng.claim_season_tier(i)
res = eng.claim_season_tier(len(bg.SEASON_TIERS) - 1)
assert res.get("palette") == season and season in g.homestead_palettes
assert eng.set_palette(season)[0] and g.homestead_palette == season
assert eng.claim_season_tier(len(bg.SEASON_TIERS) - 1) == {}
# tier 5 awards the legendary background alongside the dragonet
awarded = eng.check_homestead_tiers(5)
assert "comp_dragonet" in awarded and "background_homestead" in awarded and "background_homestead" in g.character_items_owned
assert bg.AVATAR_ITEMS["background_homestead"]["rarity"] == "legendary"
# snapshot carries palette + decor; drawing uses them without error
snap = bg.HomesteadEngine(st).snapshot(datetime(today.year, today.month, today.day, 12, 0))
assert snap["palette"] == season and snap["decor"] == ["flowerbed", "beehive"]
root = tk.Tk(); c = tk.Canvas(root, width=760, height=360); c.pack(); root.update()
bg.draw_homestead(c, snap, 760, 360, 5)
n_pal = len(c.find_all())
bg.draw_homestead(c, dict(snap, decor=[], palette="classic"), 760, 360, 5)
assert n_pal > len(c.find_all()), "decor should add items to the scene"
for did, *_ in bg.HOMESTEAD_DECOR:
    bg.draw_homestead(c, dict(snap, decor=[did]), 760, 360, 3)
root.destroy()
# round trip
s2 = bg.AppState.from_dict(json.loads(json.dumps(st.to_dict())))
assert s2.game.homestead_decor == ["flowerbed", "beehive"] and s2.game.homestead_palette == season and s2.game.homestead_palettes == [season]
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
g = app.state.game
g.total_score = 500; g.gems = 5; g.level = app.game_engine.level_from_score(500)   # Level 4 unlocks the decor shop
app._show_page("homestead"); app.update()
app._expand_section("homestead.shop"); app.update()
host = app._homestead_shop_host
assert lbl(host, "Classic") and lbl(host, "Autumn 🔒") and btn(host, "60 Gold") and btn(host, "2 Gems")
score_before = g.total_score   # visiting the Homestead may have paid a daily challenge; measure the purchase relatively
btn(host, "60 Gold")[0].invoke(); app.update()
assert "flowerbed" in g.homestead_decor and g.total_score == score_before - 60 and lbl(app._homestead_shop_host, "placed ✓")
assert "1 of" in app._homestead_shop_summary.get()
# a Gem decor the user can't afford is disabled
expensive = [b for b in all_w(app._homestead_shop_host) if isinstance(b, bg.ttk.Button) and str(b.cget("text")) == "8 Gems"]
assert expensive and str(expensive[0].cget("state")) == "disabled"
# palette chip: locked → toast only; unlocked → switches
g.homestead_palettes.append("winter"); app.refresh_homestead_tab(); app.update()
lbl(app._homestead_shop_host, "Winter")[0].event_generate("<Button-1>"); app.update()
assert g.homestead_palette == "winter" and app._homestead_snap["palette"] == "winter"
# share: stub ImageGrab + save dialog
import types
fake = types.SimpleNamespace()
class _Img:
    def convert(self, *_a): return self
    def resize(self, *_a): return self
    def getdata(self): return [120] * 1024
    def save(self, path): Path(path).write_bytes(b"PNG")
fake.grab = lambda bbox=None: _Img()
import PIL
PIL.ImageGrab = fake
sys.modules["PIL.ImageGrab"] = fake
import tkinter.filedialog as fd
out = str(Path(tmp) / "home.png"); fd.asksaveasfilename = lambda *a, **k: out
app._share_homestead_png(); app.update()
assert Path(out).exists()
app.destroy()
print("SMOKE TEST 18 PASSED")
