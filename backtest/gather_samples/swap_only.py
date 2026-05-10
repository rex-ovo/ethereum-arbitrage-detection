import argparse
import collections
import logging
import typing

import networkx as nx
import psycopg2.extensions
import web3
import web3.types

from backtest.gather_samples.analyses import _get_receipt_with_retry
from backtest.gather_samples.database import get_exchange_ids
from backtest.gather_samples.models import Arbitrage, ArbitrageCycle, ArbitrageCycleExchange, ArbitrageCycleExchangeItem
from backtest.gather_samples.tokens import get_token
from backtest.utils import ERC20_TRANSFER_TOPIC, connect_db
from utils import connect_web3, erc20, setup_logging

l = logging.getLogger(__name__)


class SwapOnlyRow(typing.NamedTuple):
    tx_hash: bytes
    block_number: int
    exchange_addr: str
    token0: str
    token1: str
    amount0_in: int
    amount1_in: int
    amount0_out: int
    amount1_out: int


def _signed_amounts_to_v2_style(amount0: int, amount1: int) -> typing.Tuple[int, int, int, int]:
    return (
        max(amount0, 0),
        max(amount1, 0),
        max(-amount0, 0),
        max(-amount1, 0),
    )


def setup_db(curr: psycopg2.extensions.cursor):
    curr.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_arbitrages_swap_only (
            id            SERIAL PRIMARY KEY NOT NULL,
            txn_hash      BYTEA NOT NULL,
            block_number  INTEGER NOT NULL,
            n_cycles      INTEGER NOT NULL,
            gas_used      NUMERIC(78, 0) NOT NULL,
            gas_price     NUMERIC(78, 0) NOT NULL,
            shooter       BYTEA DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sample_arbitrages_swap_only_block
        ON sample_arbitrages_swap_only (block_number);

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycles_swap_only (
            id SERIAL PRIMARY KEY NOT NULL,
            sample_arbitrage_id INTEGER NOT NULL REFERENCES sample_arbitrages_swap_only(id) ON DELETE CASCADE,
            profit_token  INTEGER NOT NULL REFERENCES tokens(id),
            profit_amount NUMERIC(78, 0) NOT NULL,
            profit_taker  BYTEA DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycle_exchanges_swap_only (
            id           SERIAL PRIMARY KEY NOT NULL,
            exchange_idx SMALLINT NOT NULL,
            cycle_id     INTEGER NOT NULL REFERENCES sample_arbitrage_cycles_swap_only(id) ON DELETE CASCADE,
            token_in     INTEGER NOT NULL REFERENCES tokens(id),
            token_out    INTEGER NOT NULL REFERENCES tokens(id)
        );

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycle_exchange_items_swap_only (
            id                SERIAL PRIMARY KEY NOT NULL,
            cycle_exchange_id INTEGER NOT NULL REFERENCES sample_arbitrage_cycle_exchanges_swap_only(id) ON DELETE CASCADE,
            exchange_id       INTEGER NOT NULL REFERENCES sample_arbitrage_exchanges (id),
            amount_in         NUMERIC(78, 0) NOT NULL,
            amount_out        NUMERIC(78, 0) NOT NULL
        );
        """
    )
    curr.connection.commit()


def _decode_addr(raw) -> str:
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, bytes):
        return web3.Web3.toChecksumAddress("0x" + raw.hex())
    return web3.Web3.toChecksumAddress(raw)


def _load_candidate_transactions(
    curr: psycopg2.extensions.cursor,
    start_block: int,
    end_block_exclusive: int,
) -> typing.List[typing.Tuple[bytes, int]]:
    curr.execute(
        """
        SELECT tx_hash, MIN(block_number) AS block_number
        FROM (
            SELECT tx_hash, block_number
            FROM uniswap_v2_swap_events
            WHERE block_number >= %s AND block_number < %s
            UNION ALL
            SELECT tx_hash, block_number
            FROM uniswap_v3_swap_events
            WHERE block_number >= %s AND block_number < %s
            UNION ALL
            SELECT tx_hash, block_number
            FROM sushiv2_swap_events
            WHERE block_number >= %s AND block_number < %s
            UNION ALL
            SELECT tx_hash, block_number
            FROM shibaswap_swap_events
            WHERE block_number >= %s AND block_number < %s
            UNION ALL
            SELECT tx_hash, block_number
            FROM balancer_v2_swap_events
            WHERE block_number >= %s AND block_number < %s
            UNION ALL
            SELECT tx_hash, block_number
            FROM curvefi_swap_events
            WHERE block_number >= %s AND block_number < %s
        ) s
        GROUP BY tx_hash
        ORDER BY block_number ASC
        """,
        (
            start_block, end_block_exclusive,
            start_block, end_block_exclusive,
            start_block, end_block_exclusive,
            start_block, end_block_exclusive,
            start_block, end_block_exclusive,
            start_block, end_block_exclusive,
        ),
    )
    return [(tx_hash.tobytes() if isinstance(tx_hash, memoryview) else tx_hash, block_number) for tx_hash, block_number in curr.fetchall()]


def _load_uniswap_v2_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            s.tx_hash,
            s.block_number,
            s.exchange_addr,
            t0.address,
            t1.address,
            s.amount0_in,
            s.amount1_in,
            s.amount0_out,
            s.amount1_out
        FROM uniswap_v2_swap_events s
        JOIN uniswap_v2_exchanges e ON e.address = s.exchange_addr
        JOIN tokens t0 ON t0.id = e.token0_id
        JOIN tokens t1 ON t1.id = e.token1_id
        WHERE s.tx_hash = %s
        ORDER BY s.log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=_decode_addr(row[3]),
                token1=_decode_addr(row[4]),
                amount0_in=int(row[5]),
                amount1_in=int(row[6]),
                amount0_out=int(row[7]),
                amount1_out=int(row[8]),
            )
        )
    return rows


def _load_uniswap_v3_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            s.tx_hash,
            s.block_number,
            s.exchange_addr,
            t0.address,
            t1.address,
            s.amount0,
            s.amount1
        FROM uniswap_v3_swap_events s
        JOIN uniswap_v3_exchanges e ON e.address = s.exchange_addr
        JOIN tokens t0 ON t0.id = e.token0_id
        JOIN tokens t1 ON t1.id = e.token1_id
        WHERE s.tx_hash = %s
        ORDER BY s.log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        amount0_in, amount1_in, amount0_out, amount1_out = _signed_amounts_to_v2_style(
            int(row[5]),
            int(row[6]),
        )
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=_decode_addr(row[3]),
                token1=_decode_addr(row[4]),
                amount0_in=amount0_in,
                amount1_in=amount1_in,
                amount0_out=amount0_out,
                amount1_out=amount1_out,
            )
        )
    return rows


def _load_sushiv2_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            s.tx_hash,
            s.block_number,
            s.exchange_addr,
            t0.address,
            t1.address,
            s.amount0_in,
            s.amount1_in,
            s.amount0_out,
            s.amount1_out
        FROM sushiv2_swap_events s
        JOIN sushiv2_swap_exchanges e ON e.address = s.exchange_addr
        JOIN tokens t0 ON t0.id = e.token0_id
        JOIN tokens t1 ON t1.id = e.token1_id
        WHERE s.tx_hash = %s
        ORDER BY s.log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=_decode_addr(row[3]),
                token1=_decode_addr(row[4]),
                amount0_in=int(row[5]),
                amount1_in=int(row[6]),
                amount0_out=int(row[7]),
                amount1_out=int(row[8]),
            )
        )
    return rows


def _load_shibaswap_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            s.tx_hash,
            s.block_number,
            s.exchange_addr,
            t0.address,
            t1.address,
            s.amount0_in,
            s.amount1_in,
            s.amount0_out,
            s.amount1_out
        FROM shibaswap_swap_events s
        JOIN shibaswap_exchanges e ON e.address = s.exchange_addr
        JOIN tokens t0 ON t0.id = e.token0_id
        JOIN tokens t1 ON t1.id = e.token1_id
        WHERE s.tx_hash = %s
        ORDER BY s.log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=_decode_addr(row[3]),
                token1=_decode_addr(row[4]),
                amount0_in=int(row[5]),
                amount1_in=int(row[6]),
                amount0_out=int(row[7]),
                amount1_out=int(row[8]),
            )
        )
    return rows


def _load_balancer_v2_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            tx_hash,
            block_number,
            exchange_addr,
            token_in,
            token_out,
            amount_in,
            amount_out
        FROM balancer_v2_swap_events
        WHERE tx_hash = %s
        ORDER BY log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        token_in = _decode_addr(row[3])
        token_out = _decode_addr(row[4])
        amount_in = int(row[5])
        amount_out = int(row[6])
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=token_in,
                token1=token_out,
                amount0_in=amount_in,
                amount1_in=0,
                amount0_out=0,
                amount1_out=amount_out,
            )
        )
    return rows


def _load_curvefi_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    curr.execute(
        """
        SELECT
            tx_hash,
            block_number,
            exchange_addr,
            token_in,
            token_out,
            amount_in,
            amount_out
        FROM curvefi_swap_events
        WHERE tx_hash = %s
        ORDER BY log_index ASC
        """,
        (tx_hash,),
    )
    rows = []
    for row in curr.fetchall():
        token_in = _decode_addr(row[3])
        token_out = _decode_addr(row[4])
        amount_in = int(row[5])
        amount_out = int(row[6])
        rows.append(
            SwapOnlyRow(
                tx_hash=row[0].tobytes() if isinstance(row[0], memoryview) else row[0],
                block_number=row[1],
                exchange_addr=_decode_addr(row[2]),
                token0=token_in,
                token1=token_out,
                amount0_in=amount_in,
                amount1_in=0,
                amount0_out=0,
                amount1_out=amount_out,
            )
        )
    return rows


def _load_swaps_for_tx(curr: psycopg2.extensions.cursor, tx_hash: bytes) -> typing.List[SwapOnlyRow]:
    return (
        _load_uniswap_v2_swaps_for_tx(curr, tx_hash)
        + _load_uniswap_v3_swaps_for_tx(curr, tx_hash)
        + _load_sushiv2_swaps_for_tx(curr, tx_hash)
        + _load_shibaswap_swaps_for_tx(curr, tx_hash)
        + _load_balancer_v2_swaps_for_tx(curr, tx_hash)
        + _load_curvefi_swaps_for_tx(curr, tx_hash)
    )


def _swap_row_to_exchange(row: SwapOnlyRow) -> typing.Optional[ArbitrageCycleExchange]:
    direction_0_to_1 = row.amount0_in > 0 and row.amount1_out > 0 and row.amount1_in == 0 and row.amount0_out == 0
    direction_1_to_0 = row.amount1_in > 0 and row.amount0_out > 0 and row.amount0_in == 0 and row.amount1_out == 0

    if direction_0_to_1:
        return ArbitrageCycleExchange(
            token_in=row.token0,
            token_out=row.token1,
            items=[
                ArbitrageCycleExchangeItem(
                    address=row.exchange_addr,
                    amount_in=row.amount0_in,
                    amount_out=row.amount1_out,
                )
            ],
        )
    if direction_1_to_0:
        return ArbitrageCycleExchange(
            token_in=row.token1,
            token_out=row.token0,
            items=[
                ArbitrageCycleExchangeItem(
                    address=row.exchange_addr,
                    amount_in=row.amount1_in,
                    amount_out=row.amount0_out,
                )
            ],
        )
    return None


def _parse_transfer_logs(receipt: web3.types.TxReceipt) -> typing.List[typing.Dict]:
    parsed = []
    for log in receipt["logs"]:
        if len(log["topics"]) > 0 and log["topics"][0] == ERC20_TRANSFER_TOPIC:
            try:
                parsed.append(erc20.events.Transfer().processLog(log))
            except web3.exceptions.LogTopicError:
                continue
    return parsed


def _infer_profit_from_cycle(
    txns: typing.List[typing.Dict],
    parsed_cycle: typing.List[ArbitrageCycleExchange],
    least_profitable: bool = False,
) -> typing.Optional[ArbitrageCycle]:
    cycle_tokens = set()
    for exc in parsed_cycle:
        cycle_tokens.add(exc.token_in)
        cycle_tokens.add(exc.token_out)

    addr_to_movements = collections.defaultdict(lambda: {"ins": set(), "outs": set()})
    token_movement_sums = collections.defaultdict(lambda: collections.defaultdict(int))
    for txn in txns:
        token = txn["address"]
        if token not in cycle_tokens:
            continue
        from_addr = txn["args"]["from"]
        to_addr = txn["args"]["to"]
        value = int(txn["args"]["value"])
        addr_to_movements[from_addr]["outs"].add((token, value))
        addr_to_movements[to_addr]["ins"].add((token, value))
        token_movement_sums[from_addr][token] -= value
        token_movement_sums[to_addr][token] += value

    optimizing_test = (lambda x, y: x > y) if not least_profitable else (lambda x, y: x < y)
    best_a = None
    for account_addr, token_movements in token_movement_sums.items():
        tokens_in = set(tok for tok, _ in addr_to_movements[account_addr]["ins"])
        tokens_out = set(tok for tok, _ in addr_to_movements[account_addr]["outs"])
        both = tokens_in.intersection(tokens_out)
        if not both:
            continue

        best_token = None
        best_amount = float("-inf") if not least_profitable else float("inf")
        for token in both:
            net = token_movements[token]
            if optimizing_test(net, best_amount):
                best_token = token
                best_amount = net
        if best_token is not None and optimizing_test(best_amount, 0):
            report = (account_addr, best_token, best_amount)
            if best_a is None or optimizing_test(best_amount, best_a[2]):
                best_a = report

    if best_a is not None:
        return ArbitrageCycle(
            cycle=parsed_cycle,
            profit_token=best_a[1],
            profit_taker=best_a[0],
            profit_amount=int(best_a[2]),
        )

    token_to_only_sent = collections.defaultdict(list)
    token_to_only_received = collections.defaultdict(list)
    for addr, movements in token_movement_sums.items():
        sent = set()
        received = set()
        for token_addr, net_movement in movements.items():
            if net_movement < 0:
                sent.add(token_addr)
            elif net_movement > 0:
                received.add(token_addr)
        if len(sent) == 1 and len(received) == 0:
            token_to_only_sent[next(iter(sent))].append(addr)
        if len(sent) == 0 and len(received) == 1:
            token_to_only_received[next(iter(received))].append(addr)

    best_b = None
    for token in set(token_to_only_sent.keys()).intersection(token_to_only_received.keys()):
        amount_sent = sum(-(token_movement_sums[sender][token]) for sender in token_to_only_sent[token])
        amount_received = sum(token_movement_sums[receiver][token] for receiver in token_to_only_received[token])
        profit = amount_received - amount_sent
        if optimizing_test(profit, 0):
            if best_b is None or optimizing_test(profit, best_b[1]):
                best_b = (token, profit)

    if best_b is not None:
        return ArbitrageCycle(
            cycle=parsed_cycle,
            profit_token=best_b[0],
            profit_taker=None,
            profit_amount=int(best_b[1]),
        )

    return None


def get_swap_only_arbitrage_if_exists(
    w3: web3.Web3,
    tx_hash: bytes,
    swaps: typing.List[SwapOnlyRow],
) -> typing.Optional[Arbitrage]:
    if len(swaps) < 2:
        return None

    receipt = _get_receipt_with_retry(w3, "0x" + tx_hash.hex())
    g = nx.DiGraph()
    for row in swaps:
        exchange = _swap_row_to_exchange(row)
        if exchange is None:
            continue
        item = exchange.items[0]
        if not g.has_edge(exchange.token_in, exchange.token_out):
            g.add_edge(
                exchange.token_in,
                exchange.token_out,
                exchange=ArbitrageCycleExchange(
                    token_in=exchange.token_in,
                    token_out=exchange.token_out,
                    items=[item],
                ),
            )
        else:
            g[exchange.token_in][exchange.token_out]["exchange"].items.append(item)

    if g.number_of_edges() < 2:
        return None

    cycles = list(nx.simple_cycles(g))
    if len(cycles) == 0:
        return None

    first_cycle = cycles[0]
    parsed_cycle = []
    for u, v in zip(first_cycle, first_cycle[1:] + [first_cycle[0]]):
        parsed_cycle.append(g[u][v]["exchange"])

    transfers = _parse_transfer_logs(receipt)
    only_cycle = _infer_profit_from_cycle(transfers, parsed_cycle)
    if only_cycle is None:
        return None

    return Arbitrage(
        txn_hash=receipt["transactionHash"],
        block_number=receipt["blockNumber"],
        gas_used=receipt["gasUsed"],
        gas_price=receipt["effectiveGasPrice"],
        shooter=receipt["to"],
        n_cycles=len(cycles),
        only_cycle=only_cycle,
    )


def _insert_swap_only_arb(
    w3: web3.Web3,
    curr: psycopg2.extensions.cursor,
    arb: Arbitrage,
) -> None:
    curr.execute(
        """
        INSERT INTO sample_arbitrages_swap_only (
            txn_hash, block_number, n_cycles, gas_used, gas_price, shooter
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            arb.txn_hash,
            arb.block_number,
            arb.n_cycles,
            arb.gas_used,
            arb.gas_price,
            bytes.fromhex(arb.shooter[2:]) if arb.shooter is not None else None,
        ),
    )
    (arbitrage_id,) = curr.fetchone()

    exchange_addrs = sorted({item.address for exc in arb.only_cycle.cycle for item in exc.items})
    exchange_ids = get_exchange_ids(curr, exchange_addrs)
    exchange_to_id = {addr: exc_id for addr, exc_id in zip(exchange_addrs, exchange_ids)}

    all_tokens = sorted({exc.token_in for exc in arb.only_cycle.cycle}.union({exc.token_out for exc in arb.only_cycle.cycle}))
    for token_addr in all_tokens:
        get_token(w3, curr, token_addr, arb.block_number)

    profit_token = get_token(w3, curr, arb.only_cycle.profit_token, arb.block_number)
    curr.execute(
        """
        INSERT INTO sample_arbitrage_cycles_swap_only (
            sample_arbitrage_id, profit_token, profit_amount, profit_taker
        ) VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            arbitrage_id,
            profit_token.id,
            arb.only_cycle.profit_amount,
            bytes.fromhex(arb.only_cycle.profit_taker[2:]) if arb.only_cycle.profit_taker is not None else None,
        ),
    )
    (cycle_id,) = curr.fetchone()

    for exchange_idx, exchange in enumerate(arb.only_cycle.cycle):
        token_in = get_token(w3, curr, exchange.token_in, arb.block_number)
        token_out = get_token(w3, curr, exchange.token_out, arb.block_number)
        curr.execute(
            """
            INSERT INTO sample_arbitrage_cycle_exchanges_swap_only (
                exchange_idx, cycle_id, token_in, token_out
            ) VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (exchange_idx, cycle_id, token_in.id, token_out.id),
        )
        (cycle_exchange_id,) = curr.fetchone()

        for item in exchange.items:
            curr.execute(
                """
                INSERT INTO sample_arbitrage_cycle_exchange_items_swap_only (
                    cycle_exchange_id, exchange_id, amount_in, amount_out
                ) VALUES (%s, %s, %s, %s)
                """,
                (
                    cycle_exchange_id,
                    exchange_to_id[item.address],
                    item.amount_in,
                    item.amount_out,
                ),
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup-db", action="store_true", dest="setup_db")
    parser.add_argument("--start-block", type=int)
    parser.add_argument("--end-block", type=int)
    args = parser.parse_args()

    setup_logging("swap_only", stdout_level=logging.INFO)
    db = connect_db()
    curr = db.cursor()

    if args.setup_db:
        setup_db(curr)
        l.info("setup db")
        return

    assert args.start_block is not None and args.end_block is not None, "must provide --start-block and --end-block"
    assert args.start_block < args.end_block

    w3 = connect_web3()

    txs = _load_candidate_transactions(curr, args.start_block, args.end_block)
    l.info("Processing %d transactions with swap events", len(txs))

    inserted = 0
    for i, (tx_hash, _) in enumerate(txs, start=1):
        swaps = _load_swaps_for_tx(curr, tx_hash)
        arb = get_swap_only_arbitrage_if_exists(w3, tx_hash, swaps)
        if arb is None:
            continue
        _insert_swap_only_arb(w3, curr, arb)
        inserted += 1
        if inserted % 100 == 0:
            curr.connection.commit()
            l.info("Inserted %d swap-only arbitrages (%d/%d txs scanned)", inserted, i, len(txs))

    curr.connection.commit()
    l.info("done, inserted %d swap-only arbitrages", inserted)


if __name__ == "__main__":
    main()
