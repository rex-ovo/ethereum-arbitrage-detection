from backtest.gather_samples.analyses import (
    KNOWN_RELAYER_CONTRACTS,
    KNOWN_SETTLEMENT_CONTRACTS,
    get_arbitrage_if_exists,
    get_address_semantic_role,
    get_potential_exchanges,
    is_known_non_arbitrage_protocol_transaction,
)


def _transfer(token, from_addr, to_addr, value=1):
    return {
        "address": token,
        "transactionHash": b"\x11" * 32,
        "args": {
            "from": from_addr,
            "to": to_addr,
            "value": value,
        },
    }


def test_known_settlement_is_not_treated_as_exchange():
    settlement = next(iter(KNOWN_SETTLEMENT_CONTRACTS))
    trader = "0x1111111111111111111111111111111111111111"
    token_a = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token_b = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    full_txn = {"from": trader, "to": settlement}
    addr_to_movements = {
        settlement: {
            "in": [_transfer(token_a, trader, settlement)],
            "out": [_transfer(token_b, settlement, trader)],
        }
    }

    assert get_address_semantic_role(settlement, full_txn) == "settlement"
    assert get_potential_exchanges(full_txn, addr_to_movements) == set()


def test_known_relayer_is_not_treated_as_exchange():
    relayer = next(iter(KNOWN_RELAYER_CONTRACTS))
    trader = "0x2222222222222222222222222222222222222222"
    token_a = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token_b = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    full_txn = {"from": trader, "to": relayer}
    addr_to_movements = {
        relayer: {
            "in": [_transfer(token_a, trader, relayer)],
            "out": [_transfer(token_b, relayer, trader)],
        }
    }

    assert get_address_semantic_role(relayer, full_txn) == "relayer"
    assert get_potential_exchanges(full_txn, addr_to_movements) == set()


def test_observed_relayer_shooter_is_not_treated_as_exchange():
    relayer = "0x5050e08626c499411b5d0e0b5af0e83d3fd82edf"
    trader = "0x5555555555555555555555555555555555555555"
    token_a = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token_b = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    full_txn = {"from": trader, "to": relayer}
    addr_to_movements = {
        relayer: {
            "in": [_transfer(token_a, trader, relayer)],
            "out": [_transfer(token_b, relayer, trader)],
        }
    }

    assert get_address_semantic_role(relayer, full_txn) == "relayer"
    assert get_potential_exchanges(full_txn, addr_to_movements) == set()


def test_transaction_sender_is_not_treated_as_exchange():
    sender = "0x3333333333333333333333333333333333333333"
    amm = "0x4444444444444444444444444444444444444444"
    token_a = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token_b = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    full_txn = {"from": sender, "to": amm}
    addr_to_movements = {
        sender: {
            "in": [_transfer(token_b, amm, sender)],
            "out": [_transfer(token_a, sender, amm)],
        },
        amm: {
            "in": [_transfer(token_a, sender, amm)],
            "out": [_transfer(token_b, amm, sender)],
        },
    }

    assert get_address_semantic_role(sender, full_txn) == "transaction_sender"
    assert get_potential_exchanges(full_txn, addr_to_movements) == {amm}


def test_known_settlement_transaction_is_filtered_before_graph_analysis(monkeypatch):
    tx_hash = b"\x22" * 32
    settlement = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
    fake_receipt = {
        "transactionHash": tx_hash,
        "blockNumber": 1,
        "gasUsed": 1,
        "effectiveGasPrice": 1,
        "from": "0x1111111111111111111111111111111111111111",
        "to": settlement,
    }

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            assert tx_hash_hex == "0x" + tx_hash.hex()
            return fake_receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    monkeypatch.setattr(
        "backtest.gather_samples.analyses.get_arbitrage_from_receipt_if_exists",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not be reached")),
    )

    assert is_known_non_arbitrage_protocol_transaction(fake_receipt) is True
    assert get_arbitrage_if_exists(fake_w3, tx_hash, []) is None
