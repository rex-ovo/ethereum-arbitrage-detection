import argparse
import collections
import datetime
import itertools
import logging
import os
import socket
import time
import typing
from eth_utils import event_abi_to_log_topic
import psycopg2
import psycopg2.extensions
import psycopg2.extras
import numpy as np


import web3
import web3.contract
import web3._utils.filters

from backtest.utils import connect_db

from .scrapers.balancer import BalancerScraper
from .scrapers.balancerv2 import BalancerV2Scraper
from .scrapers.uniswapv2 import UniswapV2Scraper
from .scrapers.uniswapv3 import UniswapV3Scraper
from .scrapers.cryptodotcom import CryptoDotComScraper
from .scrapers.curvefi import CurveScraper
from .scrapers.shibaswap import ShibaSwapScraper
from .scrapers.sushiswapv2 import SushiSwapV2Scraper
from .scrapers.capital_dex import CapitalDEXScraper
from .scrapers.kyberswap import KyberSwapScraper
from .scrapers.indexed import IndexedScraper
from .scrapers.orionv2 import OrionV2Scraper
from .scrapers.powerpool import PowerPoolScraper
from .scrapers.convergence import ConvergenceScraper
from .scrapers.sakeswap import SakeSwapScraper
from .scrapers.cream import CreamScraper
from .scrapers.bitberry import BitberryScraper
from .scrapers.bancorv2 import BancorV2Scraper
from .scrapers.wswap import WSwapScraper
from .scrapers.equalizer import EqualizerScraper
from .scrapers.oneinch import OneInchScraper
from .scrapers.dodo import DodoScraper

from .scrapers.base_log_scraper import BaseLogScraper

from utils import BALANCER_VAULT_ADDRESS, connect_web3, get_abi, setup_logging

ROLLING_WINDOW_SIZE_BLOCKS = 60 * 60 // 13 # about 1 hour
MAX_LOG_RANGE_BLOCKS = 1_000

l = logging.getLogger(__name__)


def _get_logs_with_backoff(
    w3: web3.Web3,
    all_addresses: typing.Set[str],
    start_block: int,
    end_block: int,
) -> typing.List[typing.Dict]:
    """
    Fetch logs for the requested block range.

    Some providers such as Infura reject requests that would return more than
    10,000 logs. In that case, recursively split the range until it succeeds.
    """
    try:
        f: web3._utils.filters.Filter = w3.eth.filter({
            'address': list(all_addresses),
            'fromBlock': start_block,
            'toBlock': end_block,
        })
        return f.get_all_entries()
    except ValueError as exc:
        msg = str(exc)
        if 'more than 10000 results' not in msg and 'block range being too large' not in msg:
            raise
        if start_block >= end_block:
            raise

        midpoint = (start_block + end_block) // 2
        l.warning(
            'Provider log limit hit for %s-%s, splitting into %s-%s and %s-%s',
            f'{start_block:,}',
            f'{end_block:,}',
            f'{start_block:,}',
            f'{midpoint:,}',
            f'{midpoint + 1:,}',
            f'{end_block:,}',
        )
        left = _get_logs_with_backoff(w3, all_addresses, start_block, midpoint)
        right = _get_logs_with_backoff(w3, all_addresses, midpoint + 1, end_block)
        return left + right

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose')
    parser.add_argument('--setup-db', action='store_true', dest='setup_db')

    args = parser.parse_args()

    setup_logging('fill_known_exchanges', stdout_level=logging.DEBUG if args.verbose else logging.INFO)

    db = connect_db()
    curr = db.cursor()

    scrapers: typing.List[BaseLogScraper] = []
    scrapers.append(UniswapV2Scraper())
    scrapers.append(UniswapV3Scraper())
    scrapers.append(CryptoDotComScraper())
    scrapers.append(BalancerScraper())
    scrapers.append(CurveScraper())
    scrapers.append(ShibaSwapScraper())
    scrapers.append(SushiSwapV2Scraper())
    scrapers.append(CapitalDEXScraper())
    scrapers.append(KyberSwapScraper())
    scrapers.append(BalancerV2Scraper())
    scrapers.append(IndexedScraper())
    scrapers.append(OrionV2Scraper())
    scrapers.append(PowerPoolScraper())
    scrapers.append(ConvergenceScraper())
    scrapers.append(SakeSwapScraper())
    scrapers.append(CreamScraper())
    scrapers.append(BitberryScraper())
    scrapers.append(BancorV2Scraper())
    scrapers.append(WSwapScraper())
    scrapers.append(EqualizerScraper())
    scrapers.append(OneInchScraper())
    scrapers.append(DodoScraper())


    if args.setup_db:
        setup_db(curr, scrapers)
        db.commit()
        l.info('setup db')
        return

    w3 = connect_web3()

    #
    # do scrape
    # 
    l.info('Starting scrape')
    curr.execute('SELECT MIN(start_block), MAX(end_block) FROM block_samples')
    start_block, end_block = curr.fetchone()

    l.info(f'Scraping from {start_block:,} to {end_block:,}')

    # get all monitored addresses
    all_addresses: typing.Set[str] = set()
    for scraper in scrapers:
        all_addresses.update(scraper.prime(curr).watch_addrs)

    l.debug(f'Watching {len(all_addresses):,} addresses')

    t_start = time.time()
    batch_size = MAX_LOG_RANGE_BLOCKS
    for i in itertools.count():
        this_start_block = i * batch_size + start_block
        this_end_block   = min(end_block, (i + 1) * batch_size + start_block - 1)
        if this_start_block > this_end_block:
            l.info('Done scrape.')
            break

        if i % 10 == 1:
            elapsed = time.time() - t_start
            processed = this_start_block - start_block
            nps = processed / elapsed
            remain = end_block - this_start_block
            eta_s = remain / nps
            eta = datetime.timedelta(seconds=eta_s)
            l.info(f'Processing at block {this_start_block:,} -- ETA {eta}')

        l.debug(f'Polling {this_start_block:,} to {this_end_block:,}')

        logs = _get_logs_with_backoff(
            w3,
            all_addresses,
            this_start_block,
            this_end_block,
        )

        for s in scrapers:
            scrape_result = s.scrape(curr, w3, logs)
            if scrape_result is not None and len(scrape_result.new_watch_addrs) > 0:
                all_addresses.update(scrape_result.new_watch_addrs)

        db.commit()

    db.commit()



def setup_db(curr: psycopg2.extensions.cursor, all_scrapers: typing.List[BaseLogScraper]):
    for scraper in all_scrapers:
        scraper.prime(curr)


if __name__ == '__main__':
    main()
