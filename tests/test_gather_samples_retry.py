import types

from backtest.gather_samples.analyses import _get_receipt_with_retry


class _FakeEth:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = 0

    def get_transaction_receipt(self, tx_hash_hex):
        self.calls += 1
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


def test_get_receipt_with_retry_recovers_from_transient_value_error(monkeypatch):
    fake_eth = _FakeEth([
        ValueError({'code': -32000, 'message': 'internal error'}),
        {'transactionHash': b'\x01' * 32},
    ])
    fake_w3 = types.SimpleNamespace(eth=fake_eth)

    monkeypatch.setattr('backtest.gather_samples.analyses.time.sleep', lambda _: None)

    receipt = _get_receipt_with_retry(fake_w3, '0x' + '01' * 32)

    assert receipt['transactionHash'] == b'\x01' * 32
    assert fake_eth.calls == 2


def test_get_receipt_with_retry_does_not_swallow_non_retryable_errors(monkeypatch):
    fake_eth = _FakeEth([
        ValueError({'code': -32602, 'message': 'invalid argument'}),
    ])
    fake_w3 = types.SimpleNamespace(eth=fake_eth)

    monkeypatch.setattr('backtest.gather_samples.analyses.time.sleep', lambda _: None)

    try:
        _get_receipt_with_retry(fake_w3, '0x' + '02' * 32)
    except ValueError as exc:
        assert 'invalid argument' in str(exc)
    else:
        raise AssertionError('Expected ValueError to be raised')
