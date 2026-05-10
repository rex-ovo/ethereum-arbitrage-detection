"""
Scrapes ShibaSwap exchange addresses
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

class ShibaSwapScraper(BaseLogScraper):
    FACTORY_ADDRESS = '0x115934131916C8b277DD010Ee02de363c09d037c'

    exchange_abi: typing.Dict
    pair_abi: typing.Dict
    factory: web3.contract.Contract
    swap_topic: bytes
    exchanges: typing.Set[str]

    def __init__(self) -> None:
        super().__init__()
        self.pair_abi = self._normalize_abi(get_abi('uniswap_v2/IUniswapV2Pair.json'))
        self.factory = web3.Web3().eth.contract(
            address = self.FACTORY_ADDRESS,
            abi = get_abi('shibaswap/factory.abi.json'),
        )
        self.pair_created_topic = event_abi_to_log_topic(self.factory.events.PairCreated().abi)
        pair = web3.Web3().eth.contract(address=b'\x00' * 20, abi=self.pair_abi)
        self.swap_topic = event_abi_to_log_topic(pair.events.Swap().abi)
        self.exchanges = set()

    def prime(self, curr: psycopg2.extensions.cursor):
        curr.execute(
            """
            CREATE TABLE IF NOT EXISTS shibaswap_exchanges (
                id SERIAL PRIMARY KEY NOT NULL,
                token0_id INTEGER NOT NULL,
                token1_id INTEGER NOT NULL,
                address BYTEA NOT NULL,
                origin_txn BYTEA NOT NULL,
                origin_block INTEGER NOT NULL,
                FOREIGN KEY (token0_id) REFERENCES tokens (id),
                FOREIGN KEY (token1_id) REFERENCES tokens (id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_shibaswap_tokens_pair ON shibaswap_exchanges (token0_id, token1_id);
            CREATE INDEX IF NOT EXISTS idx_shibaswap_token0 ON shibaswap_exchanges (token0_id);
            CREATE INDEX IF NOT EXISTS idx_shibaswap_token1 ON shibaswap_exchanges (token1_id);
            CREATE INDEX IF NOT EXISTS idx_shibaswap_ex_addr ON shibaswap_exchanges USING hash (address);

            CREATE TABLE IF NOT EXISTS shibaswap_swap_events (
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

            CREATE UNIQUE INDEX IF NOT EXISTS idx_shibaswap_swap_unique
            ON shibaswap_swap_events (tx_hash, exchange_addr, log_index);

            CREATE INDEX IF NOT EXISTS idx_shibaswap_swap_tx
            ON shibaswap_swap_events (tx_hash);

            CREATE INDEX IF NOT EXISTS idx_shibaswap_swap_block
            ON shibaswap_swap_events (block_number);
            """
        )

        curr.execute("SELECT address FROM shibaswap_exchanges")
        self.exchanges = set(self._decode_db_address(row[0]) for row in curr.fetchall())

        return PrimeResult([self.FACTORY_ADDRESS, *sorted(self.exchanges)])


    def scrape(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                logs: typing.List[typing.Dict]
            ) -> ScrapeResult:
        relevant_logs = []
        for log in logs:
            if log['address'] == self.factory.address and len(log['topics']) > 0 and log['topics'][0] == self.pair_created_topic:
                relevant_logs.append(log)

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
                log
            ) -> typing.Optional[str]:
        receipt = self.factory.events.PairCreated().processLog(log)
        pair_address = self._normalize_address(receipt['args']['pair'])

        # if we already know about this exchange then skip
        curr.execute(
            "SELECT id FROM shibaswap_exchanges WHERE address = %s",
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
            INSERT INTO shibaswap_exchanges (
                token0_id, token1_id, address, origin_txn, origin_block
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING (id)
            """,
            (
                token0_id,
                token1_id,
                bytes.fromhex(pair_address[2:]),
                receipt['transactionHash'],
                receipt['blockNumber'],
            )
        )
        new_id = curr.fetchone()[0]
        self.exchanges.add(pair_address)
        l.info(f'Registered shibaswap_exchanges exchange id={new_id}')
        return pair_address

    def _record_swap_event(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                log: typing.Dict,
            ) -> None:
        try:
            contract = w3.eth.contract(address=log['address'], abi=self.pair_abi)
            event = contract.events.Swap().processLog(log)
            args = event['args']

            curr.execute(
                """
                INSERT INTO shibaswap_swap_events (
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
            l.debug("Failed to parse Shiba swap log for %s: %s", log["address"], exc)

    @staticmethod
    def _decode_db_address(raw: typing.Any) -> str:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        return ShibaSwapScraper._normalize_address("0x" + raw.hex())

    @staticmethod
    def _normalize_abi(abi: typing.Any) -> typing.Any:
        if isinstance(abi, dict) and "abi" in abi:
            return abi["abi"]
        return abi

    @staticmethod
    def _normalize_address(address: str) -> str:
        return web3.Web3.toChecksumAddress(address)
