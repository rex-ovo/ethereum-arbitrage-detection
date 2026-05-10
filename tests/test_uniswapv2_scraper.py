import types

import pytest
import web3

from backtest.gather_samples.fill_known_exchanges.scrapers.uniswapv2 import UniswapV2Scraper


class FakeCursor:
    def __init__(self, known_exchange_addresses=None):
        self.known_exchange_addresses = {}
        self.swap_rows = []
        self.rowcount = 0
        self._fetchone = None
        self._fetchall = []
        self._next_exchange_id = 1

        for addr in known_exchange_addresses or []:
            self.known_exchange_addresses[bytes.fromhex(addr[2:])] = self._next_exchange_id
            self._next_exchange_id += 1

    def execute(self, query, params=None):
        normalized = " ".join(query.split()).lower()

        if normalized.startswith("create table") or normalized.startswith("create unique index") or normalized.startswith("create index"):
            self.rowcount = 0
            self._fetchone = None
            self._fetchall = []
            return

        if normalized == "select address from uniswap_v2_exchanges":
            self.rowcount = len(self.known_exchange_addresses)
            self._fetchall = [(addr,) for addr in self.known_exchange_addresses]
            self._fetchone = None
            return

        if normalized.startswith("select id from uniswap_v2_exchanges where address = %s"):
            addr = params[0]
            maybe_id = self.known_exchange_addresses.get(addr)
            if maybe_id is None:
                self.rowcount = 0
                self._fetchone = None
            else:
                self.rowcount = 1
                self._fetchone = (maybe_id,)
            return

        if normalized.startswith("insert into uniswap_v2_exchanges"):
            addr = params[3]
            self.known_exchange_addresses[addr] = self._next_exchange_id
            self.rowcount = 1
            self._fetchone = (self._next_exchange_id,)
            self._next_exchange_id += 1
            return

        if normalized.startswith("insert into uniswap_v2_swap_events"):
            self.swap_rows.append(params)
            self.rowcount = 1
            self._fetchone = None
            return

        raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return list(self._fetchall)


class _FactoryEvents:
    def PairCreated(self):
        class _PairCreated:
            abi = {}

            def processLog(self, log):
                return log["decoded_event"]

        return _PairCreated()


class _PairEvents:
    def Swap(self):
        class _Swap:
            abi = {}

            def processLog(self, log):
                return log["decoded_event"]

        return _Swap()


class FakeFactoryContract:
    def __init__(self, address):
        self.address = address
        self.events = _FactoryEvents()


class FakePairContract:
    def __init__(self, address):
        self.address = address
        self.events = _PairEvents()


class FakeEth:
    def contract(self, address, abi):
        if web3.Web3.toChecksumAddress(address) == UniswapV2Scraper.FACTORY_ADDRESS:
            return FakeFactoryContract(UniswapV2Scraper.FACTORY_ADDRESS)
        return FakePairContract(address)


class FakeWeb3:
    def __init__(self):
        self.eth = FakeEth()


def _swap_log(scraper: UniswapV2Scraper, address: str, tx_hash: bytes, log_index: int):
    return {
        "address": address,
        "topics": [scraper.swap_topic],
        "transactionHash": tx_hash,
        "blockNumber": 15,
        "logIndex": log_index,
        "decoded_event": {
            "args": {
                "amount0In": 10,
                "amount1In": 0,
                "amount0Out": 0,
                "amount1Out": 9,
                "to": "0x00000000000000000000000000000000000000AA",
            }
        },
    }


def test_scrape_only_records_swaps_for_known_pairs():
    scraper = UniswapV2Scraper()
    known_pair = "0x00000000000000000000000000000000000000F1"
    unknown_pair = "0x00000000000000000000000000000000000000F2"
    curr = FakeCursor([known_pair])

    scraper.prime(curr)
    scraper.scrape(
        curr,
        FakeWeb3(),
        [
            _swap_log(scraper, known_pair, b"\x01" * 32, 0),
            _swap_log(scraper, unknown_pair, b"\x02" * 32, 1),
        ],
    )

    assert len(curr.swap_rows) == 1
    assert curr.swap_rows[0][1] == bytes.fromhex(known_pair[2:])


def test_scrape_accepts_swap_for_pair_created_in_same_batch(monkeypatch):
    scraper = UniswapV2Scraper()
    curr = FakeCursor()

    monkeypatch.setattr(
        "backtest.gather_samples.fill_known_exchanges.scrapers.uniswapv2.get_token",
        lambda *args, **kwargs: types.SimpleNamespace(id=7),
    )

    scraper.prime(curr)

    new_pair = "0x00000000000000000000000000000000000000F3"
    factory_log = {
        "address": UniswapV2Scraper.FACTORY_ADDRESS,
        "topics": [scraper.pair_created_topic],
        "transactionHash": b"\x03" * 32,
        "blockNumber": 15,
        "decoded_event": {
            "args": {
                "pair": new_pair,
                "token0": "0x0000000000000000000000000000000000000010",
                "token1": "0x0000000000000000000000000000000000000020",
            },
            "transactionHash": b"\x03" * 32,
            "blockNumber": 15,
        },
    }

    scraper.scrape(
        curr,
        FakeWeb3(),
        [
            factory_log,
            _swap_log(scraper, new_pair, b"\x03" * 32, 1),
        ],
    )

    assert bytes.fromhex(new_pair[2:]) in curr.known_exchange_addresses
    assert len(curr.swap_rows) == 1
    assert curr.swap_rows[0][1] == bytes.fromhex(new_pair[2:])
