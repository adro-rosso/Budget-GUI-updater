import os
import sys, os, tempfile; os.chdir(tempfile.mkdtemp()); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import budget_gui as bg
from datetime import date, timedelta, datetime
today = date.today()
T0 = datetime(2026, 10, 9, 9, 0)

# ── Windmill accrual ─────────────────────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
m = eng.mill_status(T0); assert m["gold"] == 0 and m["rate"] == 2.0 and g.mill_last_collected
m = eng.mill_status(T0 + timedelta(hours=3)); assert m["gold"] == 6 and not m["capped"] and m["ready"], m
m = eng.mill_status(T0 + timedelta(hours=20)); assert m["gold"] == 16 and m["capped"], m
g.homestead_tier = 3; assert eng.mill_rate() == 8.0
st.bills.append(bg.Bill("Rent", 800.0, today - timedelta(days=2), "monthly", "essential", "bill", 0.0)); assert eng.mill_rate() == 2.0
st.bills.clear()
gold = eng.collect_mill(T0 + timedelta(hours=20)); assert gold == 64 and g.total_score == 64 and g.mill_gold_total == 64 and g.records["mill_haul"]["value"] == 64
assert eng.collect_mill(T0 + timedelta(hours=20)) == 0
# ── Plots ───────────────────────────────────────────────────────────────────
st.funds.append(bg.Fund("Holiday", 2000.0, None, "important", 100.0, "auto", 0.0, "fund"))
assert eng.plant("fund", "Holiday", T0) and not eng.plant("fund", "Holiday", T0)
ps = eng.plot_status(T0 + timedelta(hours=5)); assert len(ps) == 1 and not ps[0]["ripe"] and 6.9 < ps[0]["hours_left"] < 7.1
assert eng.harvest("fund:Holiday", T0 + timedelta(hours=5)) is None
r = eng.harvest("fund:Holiday", T0 + timedelta(hours=13)); assert r and r["fragments"] == 1 and r["pack"] is None and not g.plot_timers
g.pack_fragments = 4; eng.plant("goal", "Ghost", T0)   # goal that doesn't exist gets pruned
assert eng.plot_status(T0) == []
eng.plant("fund", "Holiday", T0); res = eng.harvest_all(T0 + timedelta(hours=13))
assert res["names"] == ["Holiday"] and res["fragments"] == 0 and len(res["packs"]) == 1 and res["packs"][0]["success"] and len(g.cards_owned) == 3
# ── Records + milestones ─────────────────────────────────────────────────────
assert eng.update_record("biggest_contribution", 50) == "first" and eng.update_record("biggest_contribution", 40) is None and eng.update_record("biggest_contribution", 120) == "new"
assert eng.record_text("biggest_contribution") == "$120" and eng.record_text("savings_rate") == "—"
eng.update_record("savings_rate", 0.42); assert eng.record_text("savings_rate") == "42%"
st.funds[0].current_saved = 600.0
st.goals.append(bg.Goal("Emergency", 1000.0, None, 5, 1000.0, "fixed", 50.0))
seeded = eng.check_money_milestones(award=False); assert seeded == [] and "fund:Holiday:$500" in g.money_milestones and "goal:Emergency:pct100" in g.money_milestones and "total:1000" in g.money_milestones
score = g.total_score
st.funds[0].current_saved = 1000.0
new = eng.check_money_milestones(); assert {n["key"] for n in new} == {"fund:Holiday:$1000", "fund:Holiday:pct50", "total:2000"} and new[0]["gold"] == 50, new
assert g.total_score == score + 50 + 25 + 30
# final stretch
pre = eng.pre_pay_ratios(); assert pre["fund:Holiday"][0] == 0.5 and pre["goal:Emergency"][0] == 1.0
st.goals[0].current_saved = 1000.0; st.funds[0].current_saved = 1650.0
assert eng.final_stretch_bonus(pre) == 0   # Holiday was at 50%, Emergency got nothing
st.funds[0].current_saved = 1700.0; pre = eng.pre_pay_ratios(); st.funds[0].current_saved = 1800.0
assert eng.final_stretch_bonus(pre) == 15
# ── Pacts ────────────────────────────────────────────────────────────────────
g.gems = 5
ok, msg = eng.make_pact("reserve", {"pct": 30}, 7, today); assert not ok
ok, msg = eng.make_pact("reserve", {"pct": 30}, 2, today); assert ok and g.gems == 3 and g.active_pact["kind"] == "reserve"
assert not eng.make_pact("nospend", {"n": 3}, 1, today)[0]
pr = eng.pact_progress(today); assert pr and not pr["done"] and "Waiting" in pr["text"] and pr["title"] == "Reserve 30% of my next pay"
eng.pact_note_pay(2000.0, 500.0); pr = eng.pact_progress(today); assert pr["failed"] and not pr["done"]
res = eng.settle_pacts(today); assert res and not res["won"] and g.pacts_lost == 1 and not g.active_pact and g.gems == 3
eng.make_pact("reserve", {"pct": 20}, 1, today); eng.pact_note_pay(2000.0, 500.0)
res = eng.settle_pacts(today); assert res["won"] and g.gems == 2 + 2 and g.pacts_won == 1 and res["card"] == "p_oath_reserve" and "p_oath_reserve" in g.cards_owned
# cap pact fails on spend, wins at deadline
g.gems = 6; ok, _ = eng.make_pact("cap", {"cat": "Food", "cap": 50}, 1, today); assert ok
st.transactions.append(bg.TransactionRecord(today, "CAFE", money_out=30.0, category="Food", fingerprint="a"))
pr = eng.pact_progress(today); assert not pr["failed"] and pr["pct"] == 0.6 and "$30 of $50" in pr["text"]
assert eng.settle_pacts(today) is None
assert eng.settle_pacts(today + timedelta(days=8))["won"]
eng.make_pact("cap", {"cat": "Food", "cap": 50}, 1, today)
st.transactions.append(bg.TransactionRecord(today + timedelta(days=1), "CAFE 2", money_out=30.0, category="Food", fingerprint="b"))
assert eng.settle_pacts(today)["won"] is False
# fund pact: early win
eng.make_pact("fund", {"name": "Holiday", "target": 1850.0, "deadline": (today + timedelta(days=10)).isoformat()}, 2, today)
assert eng.settle_pacts(today) is None; st.funds[0].current_saved = 1850.0; assert eng.settle_pacts(today)["won"]
# nospend pact
eng.make_pact("nospend", {"n": 2}, 1, today)
g.no_spend_dates = [today.isoformat(), (today + timedelta(days=2)).isoformat()]
assert eng.settle_pacts(today + timedelta(days=3))["won"] and "p_oath_nospend" in g.cards_owned
assert eng.cancel_pact() is False
# ── Challenges ───────────────────────────────────────────────────────────────
st.pay_frequency = "fortnightly"
ok, _ = eng.start_challenge("52week", today); assert ok and eng.challenge_active("52week")
f = eng.challenge_fund("52week"); assert f.challenge == "52week" and f.contribution_mode == "fixed" and f.fixed_amount == 3.0 and f.target_amount == 1378.0
assert not eng.start_challenge("52week", today)[0]
f.current_saved = 10.0; assert eng.challenge_filled("52week") == 4   # 1+2+3+4 = 10
eng.sync_challenge_funds(today); assert f.fixed_amount == 11.0   # weeks 5 + 6
f.current_saved = 1378.0; assert eng.challenge_filled("52week") == 52
rw = eng.check_challenge_rewards(); assert [r["step"] for r in rw] == [25, 50, 100] and bg.CHAMPION_CARD_ID in g.cards_owned and f.challenge_claimed == [25, 50, 100]
assert eng.check_challenge_rewards() == []
eng.start_challenge("roundup", today); ru = eng.roundup_for_spend(12.5); assert ru and ru[1] == 2.5 and ru[0].current_saved == 2.5 and ru[0].challenge_ticks == 1
assert eng.roundup_for_spend(15.0) is None and eng.challenge_filled("roundup") == 1
eng.start_challenge("fiver", today); eng.challenge_fund("fiver").current_saved = 27.0; assert eng.challenge_filled("fiver") == 5
ok, _ = eng.start_challenge("nospend30", today); assert ok and eng.challenge_active("nospend30") and eng.challenge_filled("nospend30") == 2   # today and today+2 from the pact test
g.no_spend_dates += [(today + timedelta(days=i)).isoformat() for i in range(3, 11)]
assert eng.challenge_filled("nospend30") == 10 and [r["step"] for r in eng.check_challenge_rewards() if r["challenge"] == "No-spend month"] == [25]
eng.start_challenge("payfirst", today); assert st.goals[-1].mode == "percent_surplus" and st.goals[-1].value == 10.0 and eng.challenge_active("payfirst")
# round trip
s2 = bg.AppState.from_dict(st.to_dict()); assert s2.funds[1].challenge == "52week" and s2.game.records["mill_haul"]["value"] == 64 and s2.game.nospend_challenge["started"]
# reminders: harvest
g.mill_last_collected = (datetime.now() - timedelta(hours=9)).isoformat(timespec="minutes")
msgs = bg._reminder_messages(st, datetime.combine(today, datetime.min.time()).replace(hour=9))
assert any(k == "harvest" for k, _, _ in msgs), msgs
print("engine 12 OK")
