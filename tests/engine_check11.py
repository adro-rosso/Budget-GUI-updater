import os
import sys, os, tempfile; os.chdir(tempfile.mkdtemp()); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import budget_gui as bg
from datetime import date, timedelta, datetime
assert [bg.level_threshold(l) for l in (1, 2, 3, 4, 5, 10)] == [0, 100, 250, 450, 700, 1950]
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
assert eng.level_from_score(0) == 1 and eng.level_from_score(99) == 1 and eng.level_from_score(100) == 2 and eng.level_from_score(266) == 3 and eng.level_from_score(1950) == 10
eng.generate_daily_challenges(); assert len(g.daily_challenges) == 3 and all(c["trigger"] not in ("pay", "pay_40", "pay_35", "streak") for c in g.daily_challenges)
st.incomes.append(bg.IncomeEntry(2000.0, date.today() - timedelta(days=14), "x")); g.daily_challenges_date = ""
eng.generate_daily_challenges(); assert g.daily_challenges[0]["trigger"] in ("pay", "pay_40", "pay_35", "streak"), g.daily_challenges
assert len(g.weekly_challenges) == 3
for _ in range(5): eng.complete_challenge("pulse")
assert g.weekly_challenges[0]["completed"] and g.weekly_challenges[0]["progress"] == 5
eng.complete_challenge("no_spend"); eng.complete_challenge("no_spend"); eng.complete_challenge("contribute"); eng.complete_challenge("contribute")
assert eng.weekly_all_done(); res = eng.claim_weekly_reward(); assert res and res["success"] and len(res["cards"]) == 3
assert eng.claim_weekly_reward() is None
g.total_score = 100000
for _ in range(60): eng.open_pack("standard")
assert "x_founder" not in g.cards_owned
out = eng.day_one_head_start(); assert out["founder"] and "x_founder" in g.cards_owned and out["pack"]["success"] and g.vault_force_tier == "gold" and eng.vault_status()["ready"]
assert eng.day_one_head_start() == {}
r = eng.open_vault(); assert r["tier"] == "gold" and g.vault_force_tier == ""
st2 = bg.AppState(); st2.incomes.append(bg.IncomeEntry(2000.0, date.today() - timedelta(days=13), "x"))
st2.bills.append(bg.Bill("Rent", 800.0, date.today() + timedelta(days=1), "monthly", "essential", "bill", 300.0))
st2.game.pulse_streak = 4; st2.game.pulse_last_date = (date.today() - timedelta(days=1)).isoformat()
at = lambda h: datetime.combine(date.today(), datetime.min.time()).replace(hour=h)
msgs = bg._reminder_messages(st2, at(19))
keys = [m[0] for m in msgs]; assert keys == ["pulse", "payday", "bill:Rent"], msgs
assert "4-day run" in msgs[0][2] and "tomorrow" in msgs[1][1] and "$500" in msgs[2][2], msgs
assert bg._reminder_messages(st2, at(9))[0][0] == "payday"
cmd = bg.reminder_task_command(bg.Path("C:/x/budget_data.json")); assert "--remind" in cmd and "budget_data.json" in cmd, cmd
print("engine OK:", cmd)
