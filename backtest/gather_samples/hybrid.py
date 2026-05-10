import argparse
import logging
import typing

import psycopg2.extensions
import web3
import web3.types

from backtest.gather_samples.analyses import (
    _get_receipt_with_retry,
    get_arbitrage_from_receipt_if_exists,
    is_known_non_arbitrage_protocol_transaction,
)
from backtest.gather_samples.database import get_exchange_ids
from backtest.gather_samples.models import Arbitrage
from backtest.gather_samples.swap_only import (
    SwapOnlyRow,
    _load_candidate_transactions,
    _load_swaps_for_tx,
    _parse_transfer_logs,
    _swap_row_to_exchange,
)
from backtest.gather_samples.tokens import get_token
from backtest.utils import connect_db
from utils import connect_web3, setup_logging

l = logging.getLogger(__name__)

# Hybrid strategy: keep the high-coverage Transfer-based arbitrage detector,
# then require that the detected cycle is corroborated by explicit Swap
# semantics. We accept three levels of corroboration:
#   1) exact directed token transition matches a swap event,
#   2) the same token pair appears in swap events regardless of direction,
#   3) an exchange address in the detected cycle is directly observed in swap
#      events for the same transaction.
# This keeps the method stricter than Transfer-only while acknowledging that
# routers / wrappers / proxy pools often distort the exact transition seen by
# the transfer-based reconstruction.
MIN_SWAP_SUPPORT_SCORE = 1


def setup_db(curr: psycopg2.extensions.cursor):
    curr.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_arbitrages_hybrid (
            id            SERIAL PRIMARY KEY NOT NULL,
            txn_hash      BYTEA NOT NULL,
            block_number  INTEGER NOT NULL,
            n_cycles      INTEGER NOT NULL,
            gas_used      NUMERIC(78, 0) NOT NULL,
            gas_price     NUMERIC(78, 0) NOT NULL,
            shooter       BYTEA DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sample_arbitrages_hybrid_block
        ON sample_arbitrages_hybrid (block_number);

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycles_hybrid (
            id SERIAL PRIMARY KEY NOT NULL,
            sample_arbitrage_id INTEGER NOT NULL REFERENCES sample_arbitrages_hybrid(id) ON DELETE CASCADE,
            profit_token  INTEGER NOT NULL REFERENCES tokens(id),
            profit_amount NUMERIC(78, 0) NOT NULL,
            profit_taker  BYTEA DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycle_exchanges_hybrid (
            id           SERIAL PRIMARY KEY NOT NULL,
            exchange_idx SMALLINT NOT NULL,
            cycle_id     INTEGER NOT NULL REFERENCES sample_arbitrage_cycles_hybrid(id) ON DELETE CASCADE,
            token_in     INTEGER NOT NULL REFERENCES tokens(id),
            token_out    INTEGER NOT NULL REFERENCES tokens(id)
        );

        CREATE TABLE IF NOT EXISTS sample_arbitrage_cycle_exchange_items_hybrid (
            id                SERIAL PRIMARY KEY NOT NULL,
            cycle_exchange_id INTEGER NOT NULL REFERENCES sample_arbitrage_cycle_exchanges_hybrid(id) ON DELETE CASCADE,
            exchange_id       INTEGER NOT NULL REFERENCES sample_arbitrage_exchanges (id),
            amount_in         NUMERIC(78, 0) NOT NULL,
            amount_out        NUMERIC(78, 0) NOT NULL
        );
        """
    )
    curr.connection.commit()


def _normalized_swap_token_transitions(
    swaps: typing.List[SwapOnlyRow],
) -> typing.Tuple[
    typing.Set[typing.Tuple[str, str]],
    typing.Set[typing.FrozenSet[str]],
    typing.Set[str],
]:
    directed: typing.Set[typing.Tuple[str, str]] = set()
    undirected: typing.Set[typing.FrozenSet[str]] = set()
    exchange_addrs: typing.Set[str] = set()
    for row in swaps:
        exchange = _swap_row_to_exchange(row)
        if exchange is None:
            continue
        token_in = exchange.token_in.lower()
        token_out = exchange.token_out.lower()
        directed.add((token_in, token_out))
        undirected.add(frozenset((token_in, token_out)))
        for item in exchange.items:
            exchange_addrs.add(item.address.lower())
    return directed, undirected, exchange_addrs


def _count_exact_swap_supported_cycle_transitions(
    arb: Arbitrage,
    directed_swap_transitions: typing.Set[typing.Tuple[str, str]],
) -> int:
    if arb.only_cycle is None:
        return 0

    supported: typing.Set[typing.Tuple[str, str]] = set()
    for cycle_exchange in arb.only_cycle.cycle:
        transition = (cycle_exchange.token_in.lower(), cycle_exchange.token_out.lower())
        if transition in directed_swap_transitions:
            supported.add(transition)
    return len(supported)


def _count_pair_supported_cycle_transitions(
    arb: Arbitrage,
    undirected_swap_pairs: typing.Set[typing.FrozenSet[str]],
) -> int:
    if arb.only_cycle is None:
        return 0

    supported: typing.Set[typing.FrozenSet[str]] = set()
    for cycle_exchange in arb.only_cycle.cycle:
        pair = frozenset((cycle_exchange.token_in.lower(), cycle_exchange.token_out.lower()))
        if pair in undirected_swap_pairs:
            supported.add(pair)
    return len(supported)


def _count_address_supported_cycle_exchanges(
    arb: Arbitrage,
    swap_exchange_addrs: typing.Set[str],
) -> int:
    if arb.only_cycle is None:
        return 0

    supported = 0
    for cycle_exchange in arb.only_cycle.cycle:
        if any(item.address.lower() in swap_exchange_addrs for item in cycle_exchange.items):
            supported += 1
    return supported


def get_hybrid_arbitrage_if_exists(
    w3: web3.Web3,
    tx_hash: bytes,
    swaps: typing.List[SwapOnlyRow],
) -> typing.Optional[Arbitrage]:
    if len(swaps) == 0:
        return None

    receipt = _get_receipt_with_retry(w3, "0x" + tx_hash.hex())
    if is_known_non_arbitrage_protocol_transaction(receipt):
        return None

    transfers = _parse_transfer_logs(receipt)
    if len(transfers) < 3:
        return None

    arb = get_arbitrage_from_receipt_if_exists(receipt, transfers)
    if arb is None or arb.only_cycle is None:
        return None

    directed_swap_transitions, undirected_swap_pairs, swap_exchange_addrs = _normalized_swap_token_transitions(swaps)
    exact_supported = _count_exact_swap_supported_cycle_transitions(arb, directed_swap_transitions)
    pair_supported = _count_pair_supported_cycle_transitions(arb, undirected_swap_pairs)
    address_supported = _count_address_supported_cycle_exchanges(arb, swap_exchange_addrs)

    support_score = max(exact_supported, pair_supported, address_supported)
    if support_score < MIN_SWAP_SUPPORT_SCORE:
        return None

    return arb


def _insert_hybrid_arb(
    w3: web3.Web3,
    curr: psycopg2.extensions.cursor,
    arb: Arbitrage,
) -> None:
    curr.execute(
        """
        INSERT INTO sample_arbitrages_hybrid (
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
        INSERT INTO sample_arbitrage_cycles_hybrid (
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
            INSERT INTO sample_arbitrage_cycle_exchanges_hybrid (
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
                INSERT INTO sample_arbitrage_cycle_exchange_items_hybrid (
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

    setup_logging("hybrid", stdout_level=logging.INFO)
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
        arb = get_hybrid_arbitrage_if_exists(w3, tx_hash, swaps)
        if arb is None:
            continue
        _insert_hybrid_arb(w3, curr, arb)
        inserted += 1
        if inserted % 100 == 0:
            curr.connection.commit()
            l.info("Inserted %d hybrid arbitrages (%d/%d txs scanned)", inserted, i, len(txs))

    curr.connection.commit()
    l.info("done, inserted %d hybrid arbitrages", inserted)


if __name__ == "__main__":
    main()
