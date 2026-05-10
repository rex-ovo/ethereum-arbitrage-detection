"""
Scrapes Curve exchange addresses
"""


import typing
import logging
import psycopg2.extensions
import web3
import web3.logs
import web3.contract
import web3._utils.events
from eth_utils import event_abi_to_log_topic

from utils import get_abi
from .base_log_scraper import BaseLogScraper, ScrapeResult, PrimeResult


l = logging.getLogger(__name__)

class CurveScraper(BaseLogScraper):
    TOKEN_EXCHANGE_EVENT_ABI = {
        'anonymous': False,
        'name': 'TokenExchange',
        'type': 'event',
        'inputs': [
            {'indexed': True, 'name': 'buyer', 'type': 'address'},
            {'indexed': False, 'name': 'sold_id', 'type': 'int128'},
            {'indexed': False, 'name': 'tokens_sold', 'type': 'uint256'},
            {'indexed': False, 'name': 'bought_id', 'type': 'int128'},
            {'indexed': False, 'name': 'tokens_bought', 'type': 'uint256'},
        ],
    }
    TOKEN_EXCHANGE_UNDERLYING_EVENT_ABI = {
        'anonymous': False,
        'name': 'TokenExchangeUnderlying',
        'type': 'event',
        'inputs': [
            {'indexed': True, 'name': 'buyer', 'type': 'address'},
            {'indexed': False, 'name': 'sold_id', 'type': 'int128'},
            {'indexed': False, 'name': 'tokens_sold', 'type': 'uint256'},
            {'indexed': False, 'name': 'bought_id', 'type': 'int128'},
            {'indexed': False, 'name': 'tokens_bought', 'type': 'uint256'},
        ],
    }

    exchange_abi: typing.Dict
    registry: web3.contract.Contract
    token_exchange_topic: bytes
    token_exchange_underlying_topic: bytes
    exchanges: typing.Set[str]
    pool_coins_cache: typing.Dict[str, typing.List[str]]
    underlying_pool_coins_cache: typing.Dict[str, typing.List[str]]

    def __init__(self) -> None:
        super().__init__()
        self.registry = web3.Web3().eth.contract(
            address = '0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5',
            abi = get_abi('curvefi/registry.abi.json'),
        )
        self.pool_added_topic = event_abi_to_log_topic(self.registry.events.PoolAdded().abi)
        self.token_exchange_topic = event_abi_to_log_topic(self.TOKEN_EXCHANGE_EVENT_ABI)
        self.token_exchange_underlying_topic = event_abi_to_log_topic(self.TOKEN_EXCHANGE_UNDERLYING_EVENT_ABI)
        self.exchanges = set()
        self.pool_coins_cache = {}
        self.underlying_pool_coins_cache = {}

    def prime(self, curr: psycopg2.extensions.cursor):
        curr.execute(
            """
            CREATE TABLE IF NOT EXISTS curvefi_exchanges (
                id SERIAL PRIMARY KEY NOT NULL,
                address BYTEA NOT NULL,
                registered_txn BYTEA NOT NULL,
                registered_block INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_curvefi_ex_addr ON curvefi_exchanges USING hash (address);

            CREATE TABLE IF NOT EXISTS curvefi_swap_events (
                id SERIAL PRIMARY KEY,
                tx_hash BYTEA NOT NULL,
                exchange_addr BYTEA NOT NULL,
                token_in BYTEA NOT NULL,
                token_out BYTEA NOT NULL,
                amount_in NUMERIC NOT NULL,
                amount_out NUMERIC NOT NULL,
                is_underlying BOOLEAN NOT NULL,
                block_number INTEGER NOT NULL,
                log_index INTEGER NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_curvefi_swap_unique
            ON curvefi_swap_events (tx_hash, exchange_addr, log_index);

            CREATE INDEX IF NOT EXISTS idx_curvefi_swap_tx
            ON curvefi_swap_events (tx_hash);

            CREATE INDEX IF NOT EXISTS idx_curvefi_swap_block
            ON curvefi_swap_events (block_number);
            """
        )

        curr.execute("SELECT address FROM curvefi_exchanges")
        self.exchanges = set(self._decode_db_address(row[0]) for row in curr.fetchall())

        return PrimeResult(['0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5', *sorted(self.exchanges)])


    def scrape(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                logs: typing.List[typing.Dict]
            ) -> ScrapeResult:
        relevant_logs = []
        for log in logs:
            # filter out irrelevant logs
            if log['address'] == self.registry.address and len(log['topics']) > 0 and log['topics'][0] == self.pool_added_topic:
                relevant_logs.append(log)

        l.debug(f'Have {len(relevant_logs)} relevant logs')

        new_addrs = set()
        for log in relevant_logs:
            created_addr = self.process_factory_event(
                w3,
                curr,
                log
            )
            if created_addr is not None:
                new_addrs.add(created_addr)

        known_for_batch = self.exchanges.union(new_addrs)
        swap_logs = []
        for log in logs:
            if self._normalize_address(log['address']) in known_for_batch and len(log['topics']) > 0:
                if log['topics'][0] == self.token_exchange_topic or log['topics'][0] == self.token_exchange_underlying_topic:
                    swap_logs.append(log)

        for log in swap_logs:
            self._record_swap_event(curr, w3, log)

        return ScrapeResult(new_addrs)

    def process_factory_event(
                self,
                w3: web3.Web3,
                curr: psycopg2.extensions.cursor,
                log
            ) -> typing.Optional[str]:
        receipt = self.registry.events.PoolAdded().processLog(log)

        # if we already know about this exchange then skip
        curr.execute(
            "SELECT id FROM curvefi_exchanges WHERE address = %s",
            (bytes.fromhex(receipt['args']['pool'][2:]),)
        )
        if curr.rowcount > 0:
            id_ = curr.fetchone()[0]
            self.exchanges.add(self._normalize_address(receipt['args']['pool']))
            l.debug(f'Already know about this exchange, id={id_}')
            return None

        block_number = receipt['blockNumber']
        
        # record the exchange info
        curr.execute(
            """
            INSERT INTO curvefi_exchanges (
                address, registered_txn, registered_block
            )
            VALUES (%s, %s, %s)
            RETURNING (id)
            """,
            (
                bytes.fromhex(receipt['args']['pool'][2:]),
                receipt['transactionHash'],
                receipt['blockNumber'],
            )
        )
        new_id = curr.fetchone()[0]
        pool_addr = self._normalize_address(receipt['args']['pool'])
        self.exchanges.add(pool_addr)
        l.info(f'Registered curvefi_exchanges exchange id={new_id}')
        return pool_addr

    def _record_swap_event(self, curr: psycopg2.extensions.cursor, w3: web3.Web3, log: typing.Dict) -> None:
        try:
            event_abi = (
                self.TOKEN_EXCHANGE_UNDERLYING_EVENT_ABI
                if log['topics'][0] == self.token_exchange_underlying_topic
                else self.TOKEN_EXCHANGE_EVENT_ABI
            )
            decoded = web3._utils.events.get_event_data(w3.codec, event_abi, log)
            args = decoded['args']
            pool_addr = self._normalize_address(log['address'])
            is_underlying = log['topics'][0] == self.token_exchange_underlying_topic
            coins = self._get_pool_coins(pool_addr, use_underlying=is_underlying)
            sold_id = int(args['sold_id'])
            bought_id = int(args['bought_id'])
            if sold_id < 0 or bought_id < 0:
                return
            if sold_id >= len(coins) or bought_id >= len(coins):
                return

            token_in = coins[sold_id]
            token_out = coins[bought_id]
            if token_in is None or token_out is None:
                return

            curr.execute(
                """
                INSERT INTO curvefi_swap_events (
                    tx_hash,
                    exchange_addr,
                    token_in,
                    token_out,
                    amount_in,
                    amount_out,
                    is_underlying,
                    block_number,
                    log_index
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    log['transactionHash'],
                    bytes.fromhex(pool_addr[2:]),
                    bytes.fromhex(token_in[2:]),
                    bytes.fromhex(token_out[2:]),
                    int(args['tokens_sold']),
                    int(args['tokens_bought']),
                    is_underlying,
                    log['blockNumber'],
                    log['logIndex'],
                )
            )
        except Exception as exc:
            l.debug("Failed to parse Curve swap log for %s: %s", log["address"], exc)

    def _get_pool_coins(self, pool_addr: str, use_underlying: bool) -> typing.List[typing.Optional[str]]:
        cache = self.underlying_pool_coins_cache if use_underlying else self.pool_coins_cache
        if pool_addr in cache:
            return cache[pool_addr]

        if use_underlying:
            raw = self.registry.functions.get_underlying_coins(pool_addr).call()
        else:
            raw = self.registry.functions.get_coins(pool_addr).call()

        coins: typing.List[typing.Optional[str]] = []
        for item in raw:
            normalized = self._normalize_maybe_zero_address(item)
            if normalized is not None:
                coins.append(normalized)
        cache[pool_addr] = coins
        return coins

    @staticmethod
    def _decode_db_address(raw: typing.Any) -> str:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        return CurveScraper._normalize_address("0x" + raw.hex())

    @staticmethod
    def _normalize_address(addr: typing.Any) -> str:
        if isinstance(addr, bytes):
            addr = "0x" + addr.hex()
        return web3.Web3.toChecksumAddress(addr)

    @staticmethod
    def _normalize_maybe_zero_address(addr: typing.Any) -> typing.Optional[str]:
        if isinstance(addr, bytes):
            addr = "0x" + addr.hex()
        normalized = CurveScraper._normalize_address(addr)
        if normalized.lower() == "0x0000000000000000000000000000000000000000":
            return None
        return normalized
