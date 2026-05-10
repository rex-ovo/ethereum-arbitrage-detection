from backtest.gather_samples.hybrid import (
    _count_exact_swap_supported_cycle_transitions,
    _count_pair_supported_cycle_transitions,
    _count_address_supported_cycle_exchanges,
    get_hybrid_arbitrage_if_exists,
)
from backtest.gather_samples.models import Arbitrage, ArbitrageCycle, ArbitrageCycleExchange, ArbitrageCycleExchangeItem
from backtest.gather_samples.swap_only import SwapOnlyRow


def _swap_row(
    exchange_addr,
    token0,
    token1,
    amount0_in=0,
    amount1_in=0,
    amount0_out=0,
    amount1_out=0,
):
    return SwapOnlyRow(
        tx_hash=b"\x44" * 32,
        block_number=1,
        exchange_addr=exchange_addr,
        token0=token0,
        token1=token1,
        amount0_in=amount0_in,
        amount1_in=amount1_in,
        amount0_out=amount0_out,
        amount1_out=amount1_out,
    )


def _arb_with_exchange(exchange_addr, token_in="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", token_out="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"):
    return Arbitrage(
        txn_hash=b"\x44" * 32,
        block_number=1,
        gas_used=100,
        gas_price=2,
        shooter="0x9999999999999999999999999999999999999999",
        n_cycles=1,
        only_cycle=ArbitrageCycle(
            cycle=[
                ArbitrageCycleExchange(
                    token_in=token_in,
                    token_out=token_out,
                    items=[
                        ArbitrageCycleExchangeItem(
                            address=exchange_addr,
                            amount_in=10,
                            amount_out=12,
                        )
                    ],
                )
            ],
            profit_token="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            profit_taker="0x9999999999999999999999999999999999999999",
            profit_amount=2,
        ),
    )


def test_count_exact_swap_supported_cycle_transitions_counts_unique_matches():
    arb = _arb_with_exchange("0x1111111111111111111111111111111111111111")
    supported = {(
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )}

    assert _count_exact_swap_supported_cycle_transitions(arb, supported) == 1


def test_count_pair_supported_cycle_transitions_ignores_direction():
    arb = _arb_with_exchange("0x1111111111111111111111111111111111111111")
    supported_pairs = {
        frozenset((
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ))
    }

    assert _count_pair_supported_cycle_transitions(arb, supported_pairs) == 1


def test_count_address_supported_cycle_exchanges_counts_matching_exchange():
    arb = _arb_with_exchange("0x1111111111111111111111111111111111111111")
    supported_addrs = {"0x1111111111111111111111111111111111111111"}

    assert _count_address_supported_cycle_exchanges(arb, supported_addrs) == 1


def test_hybrid_accepts_baseline_arb_with_swap_supported_transition_even_when_exchange_addr_differs(monkeypatch):
    tx_hash = b"\x44" * 32
    receipt = {
        "transactionHash": tx_hash,
        "blockNumber": 1,
        "gasUsed": 100,
        "effectiveGasPrice": 2,
        "from": "0x9999999999999999999999999999999999999999",
        "to": "0x9999999999999999999999999999999999999999",
        "logs": [],
    }
    swaps = [
        _swap_row(
            exchange_addr="0x1111111111111111111111111111111111111111",
            token0="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            token1="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            amount0_in=10,
            amount1_out=12,
        )
    ]

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            assert tx_hash_hex == "0x" + tx_hash.hex()
            return receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    monkeypatch.setattr("backtest.gather_samples.hybrid._parse_transfer_logs", lambda _receipt: [{"dummy": True}] * 3)
    monkeypatch.setattr(
        "backtest.gather_samples.hybrid.get_arbitrage_from_receipt_if_exists",
        lambda *_args, **_kwargs: _arb_with_exchange("0x9999999999999999999999999999999999999998"),
    )

    arb = get_hybrid_arbitrage_if_exists(fake_w3, tx_hash, swaps)

    assert arb is not None
    assert arb.only_cycle is not None


def test_hybrid_rejects_baseline_arb_without_swap_supported_transition(monkeypatch):
    tx_hash = b"\x44" * 32
    receipt = {
        "transactionHash": tx_hash,
        "blockNumber": 1,
        "gasUsed": 100,
        "effectiveGasPrice": 2,
        "from": "0x9999999999999999999999999999999999999999",
        "to": "0x9999999999999999999999999999999999999999",
        "logs": [],
    }
    swaps = [
        _swap_row(
            exchange_addr="0x2222222222222222222222222222222222222222",
            token0="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            token1="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            amount0_in=10,
            amount1_out=12,
        )
    ]

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            return receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    monkeypatch.setattr("backtest.gather_samples.hybrid._parse_transfer_logs", lambda _receipt: [{"dummy": True}] * 3)
    monkeypatch.setattr(
        "backtest.gather_samples.hybrid.get_arbitrage_from_receipt_if_exists",
        lambda *_args, **_kwargs: _arb_with_exchange(
            "0x1111111111111111111111111111111111111111",
            token_in="0xcccccccccccccccccccccccccccccccccccccccc",
            token_out="0xdddddddddddddddddddddddddddddddddddddddd",
        ),
    )

    arb = get_hybrid_arbitrage_if_exists(fake_w3, tx_hash, swaps)

    assert arb is None


def test_hybrid_accepts_pair_supported_transition_even_if_direction_differs(monkeypatch):
    tx_hash = b"\x45" * 32
    receipt = {
        "transactionHash": tx_hash,
        "blockNumber": 1,
        "gasUsed": 100,
        "effectiveGasPrice": 2,
        "from": "0x9999999999999999999999999999999999999999",
        "to": "0x9999999999999999999999999999999999999999",
        "logs": [],
    }
    swaps = [
        _swap_row(
            exchange_addr="0x2222222222222222222222222222222222222222",
            token0="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            token1="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            amount0_in=10,
            amount1_out=12,
        )
    ]

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            return receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    monkeypatch.setattr("backtest.gather_samples.hybrid._parse_transfer_logs", lambda _receipt: [{"dummy": True}] * 3)
    monkeypatch.setattr(
        "backtest.gather_samples.hybrid.get_arbitrage_from_receipt_if_exists",
        lambda *_args, **_kwargs: _arb_with_exchange(
            "0x9999999999999999999999999999999999999998",
            token_in="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            token_out="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ),
    )

    arb = get_hybrid_arbitrage_if_exists(fake_w3, tx_hash, swaps)

    assert arb is not None


def test_hybrid_accepts_exchange_address_supported_cycle_even_without_transition_match(monkeypatch):
    tx_hash = b"\x46" * 32
    receipt = {
        "transactionHash": tx_hash,
        "blockNumber": 1,
        "gasUsed": 100,
        "effectiveGasPrice": 2,
        "from": "0x9999999999999999999999999999999999999999",
        "to": "0x9999999999999999999999999999999999999999",
        "logs": [],
    }
    swaps = [
        _swap_row(
            exchange_addr="0x1111111111111111111111111111111111111111",
            token0="0xcccccccccccccccccccccccccccccccccccccccc",
            token1="0xdddddddddddddddddddddddddddddddddddddddd",
            amount0_in=10,
            amount1_out=12,
        )
    ]

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            return receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    monkeypatch.setattr("backtest.gather_samples.hybrid._parse_transfer_logs", lambda _receipt: [{"dummy": True}] * 3)
    monkeypatch.setattr(
        "backtest.gather_samples.hybrid.get_arbitrage_from_receipt_if_exists",
        lambda *_args, **_kwargs: _arb_with_exchange(
            "0x1111111111111111111111111111111111111111",
            token_in="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            token_out="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ),
    )

    arb = get_hybrid_arbitrage_if_exists(fake_w3, tx_hash, swaps)

    assert arb is not None
