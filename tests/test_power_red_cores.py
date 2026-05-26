import re
from pathlib import Path

import pytest

import core.database as db
from core.database import ActionLog, Player


ROOT = Path(__file__).resolve().parents[1]


def _create_player(user_id: int = 9001, coins: int = 1000, shards: int = 10, cores: int = 0) -> int:
    dbs = db.SessionLocal()
    try:
        player = Player(
            user_id=user_id,
            username="redcore",
            coins=coins,
            power_shards=shards,
            red_cores=cores,
        )
        dbs.add(player)
        dbs.commit()
        return user_id
    finally:
        dbs.close()


def _player(user_id: int) -> Player:
    dbs = db.SessionLocal()
    try:
        return dbs.query(Player).filter(Player.user_id == user_id).first()
    finally:
        dbs.close()


def test_red_core_success_spends_resources_and_rewards_once():
    user_id = _create_player(coins=1000, shards=10)

    result = db.apply_red_core_mine_atomic(
        user_id,
        "warm",
        1000,
        is_vip=False,
        is_vip_plus=False,
        roll={"success_roll": 0.1, "cores": 1, "coins": 333},
    )

    assert result["ok"] is True
    assert result["success"] is True
    assert result["power_shards_after"] == 7
    assert result["red_cores_after"] == 1
    assert result["coins_after"] == 1183
    assert result["rating_after"] == 2
    assert result["last_red_core_run"] == 1000
    assert result["red_core_runs"] == 1
    assert result["red_core_successes"] == 1

    player = _player(user_id)
    assert player.power_shards == 7
    assert player.red_cores == 1
    assert player.coins == 1183


def test_red_core_failure_refunds_without_cores():
    user_id = _create_player(coins=1000, shards=10)

    result = db.apply_red_core_mine_atomic(
        user_id,
        "warm",
        1000,
        is_vip=False,
        is_vip_plus=False,
        roll={"success_roll": 0.95, "refund_roll": 0.1, "refund": 1},
    )

    assert result["ok"] is True
    assert result["success"] is False
    assert result["power_shards_after"] == 8
    assert result["red_cores_after"] == 0
    assert result["coins_after"] == 850
    assert result["rating_after"] == 1
    assert result["red_core_runs"] == 1
    assert result["red_core_successes"] == 0


def test_red_core_insufficient_resources_do_not_start_cooldown_or_spend():
    user_id = _create_player(coins=1000, shards=2)

    result = db.apply_red_core_mine_atomic(
        user_id,
        "warm",
        1000,
        is_vip=False,
        is_vip_plus=False,
        roll={"success_roll": 0.1, "cores": 1, "coins": 333},
    )

    assert result == {"ok": False, "reason": "not_enough_shards", "need": 3, "have": 2, "mode": "warm"}
    player = _player(user_id)
    assert player.power_shards == 2
    assert player.coins == 1000
    assert player.last_red_core_run in (None, 0)
    assert player.red_core_runs in (None, 0)


def test_red_core_cooldown_blocks_second_click_and_prevents_double_spend():
    user_id = _create_player(coins=1000, shards=10)

    first = db.apply_red_core_mine_atomic(
        user_id,
        "warm",
        1000,
        is_vip=False,
        is_vip_plus=False,
        roll={"success_roll": 0.1, "cores": 1, "coins": 333},
    )
    second = db.apply_red_core_mine_atomic(
        user_id,
        "warm",
        1000,
        is_vip=False,
        is_vip_plus=False,
        roll={"success_roll": 0.1, "cores": 1, "coins": 333},
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason"] == "cooldown"

    player = _player(user_id)
    assert player.power_shards == 7
    assert player.red_cores == 1
    assert player.coins == 1183
    assert player.red_core_runs == 1


def test_red_core_vip_cooldowns_match_plan():
    assert db.get_red_core_cooldown("warm", False, False) == 600
    assert db.get_red_core_cooldown("warm", True, False) == 480
    assert db.get_red_core_cooldown("warm", True, True) == 360
    assert db.get_red_core_cooldown("deep", False, False) == 1500
    assert db.get_red_core_cooldown("deep", True, False) == 1200
    assert db.get_red_core_cooldown("deep", True, True) == 900
    assert db.get_red_core_cooldown("heart", False, False) == 3600
    assert db.get_red_core_cooldown("heart", True, False) == 2700
    assert db.get_red_core_cooldown("heart", True, True) == 2100


def test_red_core_luck_exchange_spends_exact_cores_and_logs():
    user_id = _create_player(coins=1000, shards=0, cores=6)

    result = db.exchange_red_cores_atomic(user_id, "luck")

    assert result["ok"] is True
    assert result["core_cost"] == 6
    assert result["red_cores_after"] == 0
    assert result["rewards"] == {"luck_coupon_charges": 1}

    dbs = db.SessionLocal()
    try:
        player = dbs.query(Player).filter(Player.user_id == user_id).first()
        action = dbs.query(ActionLog).filter(ActionLog.user_id == user_id, ActionLog.action_type == "power_red_cores").first()
        assert player.red_cores == 0
        assert player.luck_coupon_charges == 1
        assert action is not None
        assert action.action_details == "exchange:luck"
    finally:
        dbs.close()


@pytest.mark.parametrize(
    ("exchange_key", "start_cores", "expected_rewards", "expected_cores"),
    [
        ("coins", 1, {"coins": 750}, 0),
        ("search_skip", 3, {"last_search": 0}, 0),
        ("fragment", 4, {"selyuk_fragments": 1}, 0),
    ],
)
def test_red_core_exchange_recipes_mutate_only_expected_fields(exchange_key, start_cores, expected_rewards, expected_cores):
    user_id = _create_player(coins=1000, shards=2, cores=start_cores)

    result = db.exchange_red_cores_atomic(user_id, exchange_key)

    assert result["ok"] is True
    assert result["rewards"] == expected_rewards
    assert result["red_cores_after"] == expected_cores

    player = _player(user_id)
    assert player.red_cores == expected_cores
    if exchange_key == "coins":
        assert player.coins == 1750
        assert player.power_shards == 2
    elif exchange_key == "search_skip":
        assert player.last_search == 0
        assert player.coins == 1000
    elif exchange_key == "fragment":
        assert player.selyuk_fragments == 1
        assert player.coins == 1000


def test_red_core_auto_search_exchange_extends_boost_window(monkeypatch):
    user_id = _create_player(coins=1000, shards=0, cores=10)
    monkeypatch.setattr(db.time, "time", lambda: 2000)

    result = db.exchange_red_cores_atomic(user_id, "auto3")

    assert result["ok"] is True
    assert result["red_cores_after"] == 0
    assert result["rewards"] == {
        "auto_search_boost_count": 3,
        "auto_search_boost_until": 88400,
    }
    player = _player(user_id)
    assert player.auto_search_boost_count == 3
    assert player.auto_search_boost_until == 88400


def test_red_core_exchange_insufficient_cores_does_not_mutate():
    user_id = _create_player(coins=1000, shards=0, cores=5)

    result = db.exchange_red_cores_atomic(user_id, "luck")

    assert result == {"ok": False, "reason": "not_enough_cores", "need": 6, "have": 5, "exchange_key": "luck"}
    player = _player(user_id)
    assert player.red_cores == 5
    assert player.luck_coupon_charges in (None, 0)


def test_red_core_bot_source_has_active_menu_routing_and_group_privacy():
    source = (ROOT / "Bot_new.py").read_text(encoding="utf-8")
    match = re.search(r"async def _render_power_red_cores_menu\(.*?async def show_power_glasswool_field", source, re.S)
    assert match is not None
    red_core_section = match.group(0)

    assert "ЛОКАЦИЯ В РАЗРАБОТКЕ" not in red_core_section
    assert "power_red_cores_mine:warm" in red_core_section
    assert "power_red_cores_exchange:luck" in red_core_section
    assert "elif data.startswith('power_red_cores_mine:')" in source
    assert "elif data.startswith('power_red_cores_exchange:')" in source
    assert "'power_'" in source
    assert "'sematori_ans:'" in source


def test_powerlines_use_access_profile_so_admins_act_like_vip_plus():
    source = (ROOT / "Bot_new.py").read_text(encoding="utf-8")
    match = re.search(r"def _get_powerlines_access_flags\(.*?async def show_power_glasswool_field", source, re.S)
    assert match is not None
    powerlines_section = match.group(0)

    assert "acts_like_vip_plus" in powerlines_section
    assert "acts_like_vip" in powerlines_section
    assert "db.is_vip_plus" not in powerlines_section
    assert "db.is_vip(" not in powerlines_section
