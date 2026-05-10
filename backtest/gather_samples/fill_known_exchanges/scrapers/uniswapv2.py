"""
Scrapes canonical Uniswap v2 pairs and swap events.

To avoid mislabeled exchanges, swap events are only recorded for pools that
have already been confirmed through the factory's `PairCreated` event.
"""

import logging
import typing

import psycopg2.extensions
import web3
import web3.contract
from eth_utils import event_abi_to_log_topic

from backtest.gather_samples.tokens import get_token
from utils import get_abi

from .base_log_scraper import BaseLogScraper, PrimeResult, ScrapeResult

l = logging.getLogger(__name__)


class UniswapV2Scraper(BaseLogScraper):
    FACTORY_ADDRESS = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

    factory_abi: typing.Dict
    exchange_abi: typing.Dict
    pair_created_topic: bytes
    swap_topic: bytes
    exchanges: typing.Set[str]

    def __init__(self) -> None:
        super().__init__()
        self.factory_abi = self._normalize_abi(get_abi("uniswap_v2/IUniswapV2Factory.json"))
        self.exchange_abi = self._normalize_abi(get_abi("uniswap_v2/IUniswapV2Pair.json"))

        factory = web3.Web3().eth.contract(address=b"\x00" * 20, abi=self.factory_abi)
        pair = web3.Web3().eth.contract(address=b"\x00" * 20, abi=self.exchange_abi)
        self.pair_created_topic = event_abi_to_log_topic(factory.events.PairCreated().abi)
        self.swap_topic = event_abi_to_log_topic(pair.events.Swap().abi)
        self.exchanges = set()

    def prime(self, curr: psycopg2.extensions.cursor):
        curr.execute(
            """
            CREATE TABLE IF NOT EXISTS uniswap_v2_exchanges (
                id SERIAL PRIMARY KEY NOT NULL,
                token0_id INTEGER NOT NULL,
                token1_id INTEGER NOT NULL,
                index INTEGER NOT NULL,
                address BYTEA NOT NULL,
                origin_txn BYTEA NOT NULL,
                origin_block INTEGER NOT NULL,
                FOREIGN KEY (token0_id) REFERENCES tokens (id),
                FOREIGN KEY (token1_id) REFERENCES tokens (id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_uni2_ex_addr_unique
            ON uniswap_v2_exchanges (address);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_uni2_ex_tokens
            ON uniswap_v2_exchanges (token0_id, token1_id);

            CREATE INDEX IF NOT EXISTS idx_uni2_token0
            ON uniswap_v2_exchanges (token0_id);

            CREATE INDEX IF NOT EXISTS idx_uni2_token1
            ON uniswap_v2_exchanges (token1_id);

            CREATE INDEX IF NOT EXISTS idx_uni2_ex_addr
            ON uniswap_v2_exchanges USING hash (address);

            CREATE TABLE IF NOT EXISTS uniswap_v2_swap_events (
                id SERIAL PRIMARY KEY,
                tx_hash BYTEA NOT NULL,
                exchange_addr BYTEA NOT NULL,
                amount0_in NUMERIC NOT NULL,
                amount1_in NUMERIC NOT NULL,
                amount0_out NUMERIC NOT NULL,
                amount1_out NUMERIC NOT NULL,
                to_address BYTEA NOT NULL,
                block_number INTEGER NOT NULL,
                log_index INTEGER NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_uni2_swap_unique
            ON uniswap_v2_swap_events (tx_hash, exchange_addr, log_index);

            CREATE INDEX IF NOT EXISTS idx_uni2_swap_tx
            ON uniswap_v2_swap_events (tx_hash);

            CREATE INDEX IF NOT EXISTS idx_uni2_swap_block
            ON uniswap_v2_swap_events (block_number);
            """
        )

        curr.execute("SELECT address FROM uniswap_v2_exchanges")
        self.exchanges = set(self._decode_db_address(row[0]) for row in curr.fetchall())

        return PrimeResult([self.FACTORY_ADDRESS, *sorted(self.exchanges)])

    def scrape(
        self,
        curr: psycopg2.extensions.cursor,
        w3: web3.Web3,
        logs: typing.List[typing.Dict],
    ) -> ScrapeResult:
        factory: web3.contract.Contract = w3.eth.contract(
            address=self.FACTORY_ADDRESS,
            abi=self.factory_abi,
        )

        relevant_factory_logs = []
        for log in logs:
            if (
                self._normalize_address(log["address"]) == self._normalize_address(factory.address)
                and len(log["topics"]) > 0
                and log["topics"][0] == self.pair_created_topic
            ):
                relevant_factory_logs.append(log)

        new_addrs = set()
        for log in relevant_factory_logs:
            created_addr = self.process_factory_event(w3, curr, factory, log)
            if created_addr is not None:
                new_addrs.add(created_addr)

        known_for_batch = self.exchanges.union(new_addrs)
        swap_logs = []
        for log in logs:
            if (
                self._normalize_address(log["address"]) in known_for_batch
                and len(log["topics"]) > 0
                and log["topics"][0] == self.swap_topic
            ):
                swap_logs.append(log)

        l.debug(
            "Factory logs: %d, accepted swap logs: %d",
            len(relevant_factory_logs),
            len(swap_logs),
        )

        for log in swap_logs:
            self._record_swap_event(curr, w3, log)

        return ScrapeResult(new_addrs)

    def process_factory_event(
        self,
        w3: web3.Web3,
        curr: psycopg2.extensions.cursor,
        factory: web3.contract.Contract,
        log,
    ) -> typing.Optional[str]:
        receipt = factory.events.PairCreated().processLog(log)
        pair_address = receipt["args"]["pair"]
        pair_address = self._normalize_address(pair_address)

        curr.execute(
            "SELECT id FROM uniswap_v2_exchanges WHERE address = %s",
            (bytes.fromhex(pair_address[2:]),),
        )
        if curr.rowcount > 0:
            known_id = curr.fetchone()[0]
            self.exchanges.add(pair_address)
            l.debug("Already know about this exchange, id=%s", known_id)
            return None

        block_number = receipt["blockNumber"]
        token0_addr = bytes.fromhex(receipt["args"]["token0"][2:])
        token1_addr = bytes.fromhex(receipt["args"]["token1"][2:])

        token0_id = get_token(w3, curr, token0_addr, block_identifier=block_number + 1).id
        token1_id = get_token(w3, curr, token1_addr, block_identifier=block_number + 1).id

        curr.execute(
            """
            INSERT INTO uniswap_v2_exchanges (
                token0_id, token1_id, index, address, origin_txn, origin_block
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING (id)
            """,
            (
                token0_id,
                token1_id,
                0,
                bytes.fromhex(pair_address[2:]),
                receipt["transactionHash"],
                receipt["blockNumber"],
            ),
        )
        new_id = curr.fetchone()[0]
        self.exchanges.add(pair_address)
        l.info("Registered uniswap v2 exchange id=%s", new_id)
        return pair_address

    def _record_swap_event(
        self,
        curr: psycopg2.extensions.cursor,
        w3: web3.Web3,
        log: typing.Dict,
    ) -> None:
        try:
            contract = w3.eth.contract(address=log["address"], abi=self.exchange_abi)
            event = contract.events.Swap().processLog(log)
            args = event["args"]

            curr.execute(
                """
                INSERT INTO uniswap_v2_swap_events (
                    tx_hash,
                    exchange_addr,
                    amount0_in,
                    amount1_in,
                    amount0_out,
                    amount1_out,
                    to_address,
                    block_number,
                    log_index
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    log["transactionHash"],
                    bytes.fromhex(log["address"][2:]),
                    args["amount0In"],
                    args["amount1In"],
                    args["amount0Out"],
                    args["amount1Out"],
                    bytes.fromhex(args["to"][2:]),
                    log["blockNumber"],
                    log["logIndex"],
                ),
            )
        except Exception as exc:
            l.debug("Failed to parse swap log for %s: %s", log["address"], exc)

    @staticmethod
    def _decode_db_address(raw: typing.Any) -> str:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        return UniswapV2Scraper._normalize_address("0x" + raw.hex())

    @staticmethod
    def _normalize_abi(abi: typing.Any) -> typing.Any:
        if isinstance(abi, dict) and "abi" in abi:
            return abi["abi"]
        return abi

    @staticmethod
    def _normalize_address(address: str) -> str:
        return web3.Web3.toChecksumAddress(address)
