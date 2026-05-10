# NOTE: I'm not sure if this is useful for anything


import json
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

FACTORIES = [
    'AaveLinearPoolFactory.json',
    'InvestmentPoolFactory.json',
    'LiquidityBootstrappingPoolFactory.json',
    'MetaStablePoolFactory.json',
    'StablePhantomPoolFactory.json',
    'StablePoolFactory.json',
    'WeightedPool2TokensFactory.json',
    'WeightedPoolFactory.json',
    'NoProtocolFeeLiquidityBootstrappingPoolFactory.json',
]

FACTORY_ADDRESSES_TO_POOL_TYPE = {
    '0xD7FAD3bd59D6477cbe1BE7f646F7f1BA25b230f8': 'AaveLinearPool',
    '0x48767F9F868a4A7b86A90736632F6E44C2df7fa9': 'InvestmentPool',
    '0x751A0bC0e3f75b38e01Cf25bFCE7fF36DE1C87DE': 'LiquidityBootstrappingPool',
    '0x67d27634E44793fE63c467035E31ea8635117cd4': 'MetaStablePool',
    '0xb08E16cFc07C684dAA2f93C70323BAdb2A6CBFd2': 'StablePhantomPool',
    '0xc66Ba2B6595D3613CCab350C886aCE23866EDe24': 'StablePool',
    '0x8E9aa87E45e92bad84D5F8DD1bff34Fb92637dE9': 'WeightedPool',
    '0xA5bf2ddF098bb0Ef6d120C98217dD6B141c74EE0': 'WeightedPool2Tokens',
    '0x0F3e0c4218b7b0108a3643cFe9D3ec0d4F57c54e': 'NoProtocolFeeLiquidityBootstrappingPool',
}

GET_POOL_FUNC = json.loads(
    """
    [{
        "inputs": [],
        "name": "getPoolId",
        "outputs": [
            {
                "internalType": "bytes32",
                "name": "",
                "type": "bytes32"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }]
    """
)

class BalancerV2Scraper(BaseLogScraper):
    VAULT_ADDRESS = '0xBA12222222228d8Ba445958a75a0704d566BF2C8'

    pool_created_topic: bytes
    swap_topic: bytes
    base_factory: web3.contract.Contract
    vault_contract: web3.contract.Contract
    known_pool_ids: typing.Set[bytes]

    def __init__(self) -> None:
        super().__init__()

        # get all factories
        abis = {}
        for fname in FACTORIES:
            l.debug(f'Loading {fname}')
            abis[fname] = get_abi(f'balancer_v2/{fname}')

        # ensure PoolCreated is the same everywhere
        all_pool_created_topic: typing.Optional[bytes] = None
        for fname in abis:
            contract = web3.Web3().eth.contract(b'\x00' * 20, abi=abis[fname])
            pool_created_topic = event_abi_to_log_topic(contract.events.PoolCreated().abi)
            if all_pool_created_topic is None:
                all_pool_created_topic = pool_created_topic
            else:
                assert all_pool_created_topic == pool_created_topic
        self.pool_created_topic = all_pool_created_topic
        l.debug(f'Using PoolCreated topic 0x{all_pool_created_topic.hex()}')

        first_factory = web3.Web3().eth.contract(b'\x00' * 20, abi=abis[FACTORIES[0]])
        self.base_factory = web3.Web3().eth.contract(
            b'\x00' * 20,
            abi = [first_factory.events.PoolCreated().abi]
        )
        self.vault_contract = web3.Web3().eth.contract(
            b'\x00' * 20,
            abi=get_abi('balancer_v2/Vault.json'),
        )
        self.swap_topic = event_abi_to_log_topic(self.vault_contract.events.Swap().abi)
        self.known_pool_ids = set()

    def prime(self, curr: psycopg2.extensions.cursor):
        curr.execute(
            """
            CREATE TABLE IF NOT EXISTS balancer_v2_exchanges (
                id SERIAL PRIMARY KEY NOT NULL,
                address BYTEA NOT NULL,
                pool_id BYTEA NOT NULL,
                pool_type TEXT NOT NULL,
                origin_txn BYTEA NOT NULL,
                origin_block INTEGER NOT NULL CHECK(origin_block >= 1)
            );
            CREATE INDEX IF NOT EXISTS idx_balancer_v2_type ON balancer_v2_exchanges (pool_type);
            CREATE INDEX IF NOT EXISTS idx_balancer_v2_addr ON balancer_v2_exchanges USING hash (address);

            CREATE TABLE IF NOT EXISTS balancer_v2_exchange_tokens (
                exchange_id INTEGER NOT NULL REFERENCES balancer_v2_exchanges (id),
                token_id INTEGER NOT NULL REFERENCES tokens (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_balancer_v2_exchange_tokens_exchange_id ON balancer_v2_exchange_tokens (exchange_id);

            CREATE TABLE IF NOT EXISTS balancer_v2_swap_events (
                id SERIAL PRIMARY KEY,
                tx_hash BYTEA NOT NULL,
                exchange_addr BYTEA NOT NULL,
                pool_id BYTEA NOT NULL,
                token_in BYTEA NOT NULL,
                token_out BYTEA NOT NULL,
                amount_in NUMERIC NOT NULL,
                amount_out NUMERIC NOT NULL,
                block_number INTEGER NOT NULL,
                log_index INTEGER NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_balancer_v2_swap_unique
            ON balancer_v2_swap_events (tx_hash, pool_id, log_index);

            CREATE INDEX IF NOT EXISTS idx_balancer_v2_swap_tx
            ON balancer_v2_swap_events (tx_hash);

            CREATE INDEX IF NOT EXISTS idx_balancer_v2_swap_block
            ON balancer_v2_swap_events (block_number);
            """
        )

        curr.execute("SELECT pool_id FROM balancer_v2_exchanges WHERE pool_id IS NOT NULL")
        self.known_pool_ids = set(
            row[0].tobytes() if isinstance(row[0], memoryview) else row[0]
            for row in curr.fetchall()
        )

        return PrimeResult(
            [*list(FACTORY_ADDRESSES_TO_POOL_TYPE.keys()), self.VAULT_ADDRESS],
        )

    def scrape(
                self,
                curr: psycopg2.extensions.cursor,
                w3: web3.Web3,
                logs: typing.List[typing.Dict]
            ) -> ScrapeResult:
        relevant_logs = []
        for log in logs:
            # filter out irrelevant logs
            if log['address'] in FACTORY_ADDRESSES_TO_POOL_TYPE and \
                len(log['topics']) > 0 and log['topics'][0] == self.pool_created_topic:
                relevant_logs.append(log)

        l.debug(f'Have {len(relevant_logs)} relevant logs')

        for log in relevant_logs:
            self.process_factory_event(
                w3,
                curr,
                log
            )

        swap_logs = []
        for log in logs:
            if (
                self._normalize_address(log['address']) == self._normalize_address(self.VAULT_ADDRESS)
                and len(log['topics']) > 0
                and log['topics'][0] == self.swap_topic
            ):
                swap_logs.append(log)

        for log in swap_logs:
            self._record_swap_event(curr, w3, log)
        return ScrapeResult(set())

    def process_factory_event(
                self,
                w3: web3.Web3,
                curr: psycopg2.extensions.cursor,
                log
            ) -> typing.Optional[str]:
        receipt = self.base_factory.events.PoolCreated().processLog(log)
        address = receipt['args']['pool']

        # if we already know about this exchange then skip
        curr.execute(
            "SELECT id FROM balancer_v2_exchanges WHERE address = %s",
            (bytes.fromhex(address[2:]),)
        )

        contract = w3.eth.contract(address=address, abi=GET_POOL_FUNC)
        pool_id = contract.functions.getPoolId().call()

        if curr.rowcount > 0:
            id_ = curr.fetchone()[0]
            
            # see if we need to fill pool id
            curr.execute('SELECT pool_id FROM balancer_v2_exchanges WHERE id = %s', (id_,))
            (db_pool_id,) = curr.fetchone()
            if db_pool_id is None:
                curr.execute('UPDATE balancer_v2_exchanges SET pool_id = %s WHERE id = %s', (pool_id, id_,))
                assert curr.rowcount == 1
                l.debug(f'Updated id={id_} where pool_id={pool_id.hex()}')

            self.fill_tokens(w3, curr, pool_id, id_)
            self.known_pool_ids.add(pool_id)

            l.debug(f'Already know about this exchange, id={id_}')
            return

        # record the exchange info
        curr.execute(
            """
            INSERT INTO balancer_v2_exchanges (
                address, pool_id, pool_type, origin_txn, origin_block
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING (id)
            """,
            (
                bytes.fromhex(receipt['args']['pool'][2:]),
                pool_id,
                FACTORY_ADDRESSES_TO_POOL_TYPE[receipt['address']],
                receipt['transactionHash'],
                receipt['blockNumber'],
            )
        )
        assert curr.rowcount == 1

        (id_,) = curr.fetchone()

        self.fill_tokens(w3, curr, pool_id, id_)
        self.known_pool_ids.add(pool_id)

        l.info(f'Registered balancer v2 exchange id={id_}')
        return receipt['args']['pool']

    def fill_tokens(self, w3: web3.Web3, curr: psycopg2.extensions.cursor, pool_id: bytes, exchange_id: int):
        curr.execute(
            'SELECT COUNT(*) FROM balancer_v2_exchange_tokens WHERE exchange_id=%s',
            (exchange_id,)
        )
        (n_tokens,) = curr.fetchone()

        if n_tokens > 0:
            l.debug(f'Already filled tokens for exchange id={exchange_id}')
            return

        vault = w3.eth.contract(
            address='0xBA12222222228d8Ba445958a75a0704d566BF2C8',
            abi = get_abi('balancer_v2/Vault.json'),
        )
        tokens, _, _ = vault.functions.getPoolTokens(pool_id).call()
        for t in tokens:
            tid = get_token(w3, curr, bytes.fromhex(t[2:]), block_identifier='latest').id

            curr.execute(
                '''
                INSERT INTO balancer_v2_exchange_tokens (exchange_id, token_id) VALUES (%s, %s)
                ''',
                (exchange_id, tid,)
            )
            assert curr.rowcount == 1

        l.debug(f'inserted {len(tokens)} tokens for exchange_id={exchange_id}')

    def _record_swap_event(self, curr: psycopg2.extensions.cursor, w3: web3.Web3, log: typing.Dict) -> None:
        try:
            event = self.vault_contract.events.Swap().processLog(log)
            args = event['args']
            pool_id = args['poolId']
            if pool_id not in self.known_pool_ids:
                return

            curr.execute(
                """
                SELECT address
                FROM balancer_v2_exchanges
                WHERE pool_id = %s
                LIMIT 1
                """,
                (pool_id,),
            )
            row = curr.fetchone()
            if row is None:
                return

            exchange_addr = row[0].tobytes() if isinstance(row[0], memoryview) else row[0]

            curr.execute(
                """
                INSERT INTO balancer_v2_swap_events (
                    tx_hash,
                    exchange_addr,
                    pool_id,
                    token_in,
                    token_out,
                    amount_in,
                    amount_out,
                    block_number,
                    log_index
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    log['transactionHash'],
                    exchange_addr,
                    pool_id,
                    bytes.fromhex(args['tokenIn'][2:]),
                    bytes.fromhex(args['tokenOut'][2:]),
                    int(args['amountIn']),
                    int(args['amountOut']),
                    log['blockNumber'],
                    log['logIndex'],
                )
            )
        except Exception as exc:
            l.debug("Failed to parse Balancer v2 swap log: %s", exc)

    @staticmethod
    def _normalize_address(addr: typing.Any) -> str:
        if isinstance(addr, bytes):
            addr = "0x" + addr.hex()
        return web3.Web3.toChecksumAddress(addr)
