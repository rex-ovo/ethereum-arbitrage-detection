import decimal

from pricers.balancer_v2.common import ONE
from pricers.balancer_v2.liquidity_bootstrapping_pool import (
    BalancerV2LiquidityBootstrappingPoolPricer,
)
from pricers.balancer_v2.weighted_pool import BalancerV2WeightedPoolPricer


def test_weighted_pool_copy_without_cache_preserves_vault(monkeypatch):
    captured = {}
    original = BalancerV2WeightedPoolPricer

    class FakeCtor:
        def __init__(self, w3, vault, address, pool_id=None):
            captured["args"] = (w3, vault, address)
            captured["pool_id"] = pool_id

    monkeypatch.setattr("pricers.balancer_v2.weighted_pool.BalancerV2WeightedPoolPricer", FakeCtor)

    dummy = object.__new__(original)
    dummy.w3 = "w3"
    dummy.vault = "vault"
    dummy.address = "pool"
    dummy.pool_id = b"pool-id"

    original.copy_without_cache(dummy)

    assert captured["args"] == ("w3", "vault", "pool")
    assert captured["pool_id"] == b"pool-id"


def test_lbp_copy_without_cache_preserves_vault(monkeypatch):
    captured = {}
    original = BalancerV2LiquidityBootstrappingPoolPricer

    class FakeCtor:
        def __init__(self, w3, vault, address, pool_id=None):
            captured["args"] = (w3, vault, address)
            captured["pool_id"] = pool_id

    monkeypatch.setattr(
        "pricers.balancer_v2.liquidity_bootstrapping_pool.BalancerV2LiquidityBootstrappingPoolPricer",
        FakeCtor,
    )

    dummy = object.__new__(original)
    dummy.w3 = "w3"
    dummy.vault = "vault"
    dummy.address = "pool"
    dummy.pool_id = b"pool-id"

    original.copy_without_cache(dummy)

    assert captured["args"] == ("w3", "vault", "pool")
    assert captured["pool_id"] == b"pool-id"


def test_lbp_get_token_weight_uses_weight_value():
    dummy = object.__new__(BalancerV2LiquidityBootstrappingPoolPricer)
    dummy.get_weight = lambda token_address, block_identifier: ONE // 2

    weight = BalancerV2LiquidityBootstrappingPoolPricer.get_token_weight(dummy, "token", 123)

    assert weight == decimal.Decimal("0.5")
