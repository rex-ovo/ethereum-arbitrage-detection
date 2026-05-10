import types

from backtest.gather_samples.__main__ import _get_transfer_logs_with_backoff


class _FakeFilter:
    def __init__(self, result):
        self._result = result

    def get_all_entries(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeEth:
    def __init__(self):
        self.calls = []

    def filter(self, params):
        block_range = (params['fromBlock'], params['toBlock'])
        self.calls.append(block_range)

        if block_range == (10, 19):
            return _FakeFilter(ValueError({'code': -32005, 'message': 'query returned more than 10000 results'}))
        if block_range == (10, 14):
            return _FakeFilter([{'blockNumber': 10}, {'blockNumber': 14}])
        if block_range == (15, 19):
            return _FakeFilter([{'blockNumber': 15}, {'blockNumber': 19}])

        raise AssertionError(f'unexpected block range: {block_range}')


def test_get_transfer_logs_with_backoff_splits_limit_errors():
    fake_w3 = types.SimpleNamespace(eth=_FakeEth())

    logs = _get_transfer_logs_with_backoff(fake_w3, 10, 19)

    assert [x['blockNumber'] for x in logs] == [10, 14, 15, 19]
    assert fake_w3.eth.calls == [(10, 19), (10, 14), (15, 19)]
