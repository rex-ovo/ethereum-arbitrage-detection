from backtest.gather_samples.swap_only import (
    SwapOnlyRow,
    _signed_amounts_to_v2_style,
    _swap_row_to_exchange,
    get_swap_only_arbitrage_if_exists,
)


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
        tx_hash=b"\x33" * 32,
        block_number=1,
        exchange_addr=exchange_addr,
        token0=token0,
        token1=token1,
        amount0_in=amount0_in,
        amount1_in=amount1_in,
        amount0_out=amount0_out,
        amount1_out=amount1_out,
    )


def test_swap_row_to_exchange_parses_uniswap_v2_direction():
    row = _swap_row(
        exchange_addr="0x1111111111111111111111111111111111111111",
        token0="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        token1="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        amount0_in=10,
        amount1_out=12,
    )

    exc = _swap_row_to_exchange(row)

    assert exc is not None
    assert exc.token_in == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert exc.token_out == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert exc.items[0].amount_in == 10
    assert exc.items[0].amount_out == 12


def test_signed_amounts_to_v2_style_converts_uniswap_v3_deltas():
    amount0_in, amount1_in, amount0_out, amount1_out = _signed_amounts_to_v2_style(10, -12)

    assert amount0_in == 10
    assert amount1_in == 0
    assert amount0_out == 0
    assert amount1_out == 12


def test_swap_only_detects_simple_cycle():
    token_a = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token_b = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    token_c = "0xcccccccccccccccccccccccccccccccccccccccc"
    trader = "0x9999999999999999999999999999999999999999"

    swaps = [
        _swap_row("0x1111111111111111111111111111111111111111", token_a, token_b, amount0_in=10, amount1_out=12),
        _swap_row("0x2222222222222222222222222222222222222222", token_b, token_c, amount0_in=12, amount1_out=15),
        _swap_row("0x3333333333333333333333333333333333333333", token_c, token_a, amount0_in=15, amount1_out=18),
    ]

    receipt = {
        "transactionHash": b"\x33" * 32,
        "blockNumber": 1,
        "gasUsed": 100,
        "effectiveGasPrice": 2,
        "to": trader,
        "logs": [],
    }

    def _transfer(token, from_addr, to_addr, value):
        return {
            "address": token,
            "args": {
                "from": from_addr,
                "to": to_addr,
                "value": value,
            },
        }

    transfers = [
        _transfer(token_a, trader, "0x1111111111111111111111111111111111111111", 10),
        _transfer(token_b, "0x1111111111111111111111111111111111111111", "0x2222222222222222222222222222222222222222", 12),
        _transfer(token_c, "0x2222222222222222222222222222222222222222", "0x3333333333333333333333333333333333333333", 15),
        _transfer(token_a, "0x3333333333333333333333333333333333333333", trader, 18),
    ]

    class _FakeEth:
        def get_transaction_receipt(self, tx_hash_hex):
            assert tx_hash_hex == "0x" + (b"\x33" * 32).hex()
            return receipt

    fake_w3 = type("FakeW3", (), {"eth": _FakeEth()})()

    from backtest.gather_samples import swap_only as mod

    orig = mod._parse_transfer_logs
    mod._parse_transfer_logs = lambda _receipt: transfers
    try:
        arb = get_swap_only_arbitrage_if_exists(fake_w3, b"\x33" * 32, swaps)
    finally:
        mod._parse_transfer_logs = orig

    assert arb is not None
    assert arb.n_cycles == 1
    assert arb.only_cycle is not None
    assert arb.only_cycle.profit_token == token_a
    assert arb.only_cycle.profit_amount == 8
