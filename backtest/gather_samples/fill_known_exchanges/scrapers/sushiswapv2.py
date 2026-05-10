"""
Scrapes SushiSwap exchange addresses (uniswap v2 clone)
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
from backtest.gather_samples.tokens import get_token
from .base_log_scraper import BaseLogScraper, ScrapeResult, PrimeResult

l = logging.getLogger(__name__)

class SushiSwapV2Scraper(BaseLogScraper):
    FACTORY_ADDRESS = '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac'

    factory_abi: typing.Dict
    exchange_abi: typing.Dict
    pair_created_topic: bytes
    swap_topic: bytes
    exchanges: typing.Set[str]

    def __init__(self) -> None:
        super().__init__()
        self.factory_abi = self._normalize_abi(get_abi('uniswap_v2/IUniswapV2Factory.json'))
        self.exchange_abi = self._normalize_abi(get_abi('uniswap_v2/IUniswapV2Pair.json'))

        factory = web3.Web3().eth.contract(address=b'\x00' * 20, abi=self.factory_abi)
        pair = web3.Web3().eth.contract(address=b'\x00' * 20, abi=self.exchange_abi)
        self.pair_created_topic = event_abi_to_log_topic(factory.events.PairCreated().abi)
        self.swap_topic = event_abi_to_log_topic(pair.events.Swap().abi)
        self.exchanges = set()

    def prime(self, curr: psycopg2.extensions.cursor):
        curr.execute(
            """
            CREATE TABLE IF NOT EXISTS sushiv2_swap_exchanges (
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
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sushiv2_tokens ON sushiv2_swap_exchanges (token0_id, token1_id);
            CREATE INDEX IF NOT EXISTS idx_sushiv2_token0 ON sushiv2_swap_exchanges (token0_id);
            CREATE INDEX IF NOT EXISTS idx_sushiv2_token1 ON sushiv2_swap_exchanges (token1_id);
            CREATE INDEX IF NOT EXISTS idx_sushiv2_ex_addr ON sushiv2_swap_exchanges USING hash (address);

            CREATE TABLE IF NOT EXISTS sushiv2_swap_events (
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

            CREATE UNIQUE INDEX IF NOT EXISTS idx_sushiv2_swap_unique
            ON sushiv2_swap_events (tx_hash, exchange_addr, log_index);

            CREATE INDEX IF NOT EXISTS idx_sushiv2_swap_tx
            ON sushiv2_swap_events (tx_hash);

            CREATE INDEX IF NOT EXISTS idx_sushiv2_swap_block
            ON sushiv2_swap_events (block_number);
            """
        )

        curr.execute("SELECT address FROM sushiv2_swap_exchanges")
        self.exchanges = set(self._decode_db_address(row[0]) for row in curr.fetchall())

        return PrimeResult([self.FACTORY_ADDRESS, *sorted(self.exchanges)])


    def scrape(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                logs: typing.List[typing.Dict]
            ) -> ScrapeResult:
        factory: web3.contract.Contract = w3.eth.contract(
            address=self.FACTORY_ADDRESS,
            abi=self.factory_abi,
        )
        relevant_logs = []
        for log in logs:
            if (
                self._normalize_address(log['address']) == self._normalize_address(factory.address)
                and len(log['topics']) > 0
                and log['topics'][0] == self.pair_created_topic
            ):
                relevant_logs.append(log)

        new_addrs = set()
        for log in relevant_logs:
            created_addr = self.process_factory_event(
                w3,
                curr,
                factory,
                log
            )
            if created_addr is not None:
                new_addrs.add(created_addr)

        known_for_batch = self.exchanges.union(new_addrs)
        swap_logs = []
        for log in logs:
            if (
                self._normalize_address(log['address']) in known_for_batch
                and len(log['topics']) > 0
                and log['topics'][0] == self.swap_topic
            ):
                swap_logs.append(log)

        for log in swap_logs:
            self._record_swap_event(curr, w3, log)

        return ScrapeResult(new_addrs)

    def process_factory_event(
                self,
                w3: web3.Web3,
                curr: psycopg2.extensions.cursor,
                factory: web3.contract.Contract,
                log
            ) -> typing.Optional[str]:
        receipt = factory.events.PairCreated().processLog(log)
        pair_address = self._normalize_address(receipt['args']['pair'])

        # if we already know about this exchange then skip
        curr.execute(
            "SELECT id FROM sushiv2_swap_exchanges WHERE address = %s",
            (bytes.fromhex(pair_address[2:]),)
        )
        if curr.rowcount > 0:
            id_ = curr.fetchone()[0]
            self.exchanges.add(pair_address)
            l.debug(f'Already know about this exchange, id={id_}')
            return None

        block_number = receipt['blockNumber']

        token0_addr_sz: str = receipt['args']['token0']
        token0_addr = bytes.fromhex(token0_addr_sz[2:])
        token1_addr_sz: str = receipt['args']['token1']
        token1_addr = bytes.fromhex(token1_addr_sz[2:])
        
        token0_id = get_token(w3, curr, token0_addr, block_identifier=block_number + 1).id
        token1_id = get_token(w3, curr, token1_addr, block_identifier=block_number + 1).id

        # sanity check
        assert isinstance(token0_id, int)
        assert isinstance(token1_id, int)

        # record the exchange info
        curr.execute(
            """
            INSERT INTO sushiv2_swap_exchanges (
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
                receipt['transactionHash'],
                receipt['blockNumber'],
            )
        )
        new_id = curr.fetchone()[0]
        self.exchanges.add(pair_address)
        l.info(f'Registered sushiv2_swap_exchanges exchange id={new_id}')
        return pair_address

    def _record_swap_event(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                log: typing.Dict,
            ) -> None:
        try:
            contract = w3.eth.contract(address=log['address'], abi=self.exchange_abi)
            event = contract.events.Swap().processLog(log)
            args = event['args']

            curr.execute(
                """
                INSERT INTO sushiv2_swap_events (
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
                    log['transactionHash'],
                    bytes.fromhex(log['address'][2:]),
                    args['amount0In'],
                    args['amount1In'],
                    args['amount0Out'],
                    args['amount1Out'],
                    bytes.fromhex(args['to'][2:]),
                    log['blockNumber'],
                    log['logIndex'],
                )
            )
        except Exception as exc:
            l.debug("Failed to parse Sushi swap log for %s: %s", log["address"], exc)

    @staticmethod
    def _decode_db_address(raw: typing.Any) -> str:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        return SushiSwapV2Scraper._normalize_address("0x" + raw.hex())

    @staticmethod
    def _normalize_abi(abi: typing.Any) -> typing.Any:
        if isinstance(abi, dict) and "abi" in abi:
            return abi["abi"]
        return abi

    @staticmethod
    def _normalize_address(address: str) -> str:
        return web3.Web3.toChecksumAddress(address)
