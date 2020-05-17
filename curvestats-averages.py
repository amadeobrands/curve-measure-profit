#!/usr/bin/env python3

from collections import defaultdict
from time import time
import lmdb
import json

DB_NAME = 'curvestats.lmdb'  # <- DB [block][pool#]{...}
START_BLOCK = 9456294
TICKS = [1, 5, 10, 15, 30, 60 * 24]  # min
day_ago = time() - 86400

summarized_data = {}
db = lmdb.open(DB_NAME)
db.set_mapsize(2 ** 32)


def int2uid(value):
    return int.to_bytes(value, 4, 'big')


def get_block(b):
    with db.begin(write=False) as tx:
        obj = tx.get(int2uid(b))
        if not obj:
            return False
        return json.loads(obj)


if __name__ == "__main__":
    b = START_BLOCK
    decimals = {
            'compound': [18, 6],
            'usdt': [18, 6, 6],
            'y': [18, 6, 6, 18],
            'busd': [18, 6, 6, 18],
            'susd': [18, 6, 6, 18],
            'pax': [18, 6, 6, 18],
            'ren': [8, 8],
            'tbtc': [18, 8, 18]
    }
    virtual_prices = []
    daily_volumes = defaultdict(float)
    pools = ['compound', 'usdt', 'y', 'busd', 'susd', 'pax', 'ren', 'tbtc']
    ctr = 0
    while True:
        block = get_block(b)
        if not block:
            ctr += 1
            b += 1
            if ctr > 100:
                break
            else:
                continue
        else:
            ctr = 0

        virtual_prices.append(
            [block[pools[1]]['timestamp']] +
            [block[pool]['virtual_price'] / 1e18 if pool in block else 0 for pool in pools])

        for pool in block:
            if pool not in summarized_data:
                summarized_data[pool] = {}

            for tick in TICKS:
                ts = block[pool]['timestamp'] // (tick * 60) * (tick * 60)
                if tick not in summarized_data[pool]:
                    summarized_data[pool][tick] = {}
                if ts not in summarized_data[pool][tick]:
                    summarized_data[pool][tick][ts] = {}
                obj = block[pool].copy()
                obj['volume'] = summarized_data[pool][tick][ts].get('volume', {})
                obj['prices'] = summarized_data[pool][tick][ts].get('prices', {})
                for t in obj['trades']:
                    pair = sorted([(t['sold_id'], t['tokens_sold']), (t['bought_id'], t['tokens_bought'])])
                    pair, tokens = list(zip(*pair))  # (id1, id2), (vol1, vol2)
                    jpair = '{}-{}'.format(*pair)
                    t0 = tokens[0] * 10 ** (18 - decimals[pool][pair[0]])
                    t1 = tokens[1] * 10 ** (18 - decimals[pool][pair[1]])
                    if tick == 5 and ts > day_ago:
                        daily_volumes[pool] += (t0 + t1) / (2 * 1e18)
                    if t1 > 0 and t0 > 0:
                        price = t1 / t0
                        if jpair not in obj['prices']:
                            obj['prices'][jpair] = []
                        obj['prices'][jpair].append(price)
                    if jpair in obj['volume']:
                        obj['volume'][jpair] = (obj['volume'][jpair][0] + tokens[0]), (obj['volume'][jpair][1] + tokens[1])
                    else:
                        obj['volume'][jpair] = tokens
                del obj['trades']
                for jpair in obj['prices']:
                    prices = obj['prices'][jpair]
                    # OHLC
                    if prices:
                        obj['prices'][jpair] = [prices[0], min(prices), max(prices), prices[-1]]
                summarized_data[pool][tick][ts] = obj

        b += 1

    last_time, *p_last = virtual_prices[-1]
    first_time, *p_first = virtual_prices[0]

    day_ix = [(abs(vp[0] - (last_time - 86400)), tuple(vp)) for i, vp in enumerate(virtual_prices)]
    week_ix = [(abs(vp[0] - (last_time - 7 * 86400)), tuple(vp)) for i, vp in enumerate(virtual_prices)]
    month_ix = [(abs(vp[0] - (last_time - 30 * 86400)), tuple(vp)) for i, vp in enumerate(virtual_prices)]

    vps = {'day': min(day_ix)[1],
           'week': min(week_ix)[1],
           'month': min(month_ix)[1]}

    profits = {
        interval: {
            pool: ((last / v) ** (86400 / (last_time - vp[0]))) ** 365 - 1
            if v > 0 else 0
            for pool, v, last in zip(pools, vp[1:], p_last)}
        for interval, vp in vps.items()
    }
    profits['total'] = {}
    for i, pool in enumerate(pools):
        t, v = [(vp[0], vp[i + 1]) for vp in virtual_prices if vp[i + 1] > 0][0]
        profits['total'][pool] = ((p_last[i] / v) ** (86400 / (last_time - t))) ** 365 - 1

    for pool in summarized_data:
        for t in summarized_data[pool]:
            data = sorted(summarized_data[pool][t].values(), key=lambda x: x['timestamp'])[-1000:]
            with open(f'json/{pool}-{t}m.json', 'w') as f:
                json.dump(data, f)
    with open('json/virtual-prices.json', 'w') as f:
        json.dump({
            'pools': pools,
            'virtual_prices': virtual_prices}, f)
    with open('json/apys.json', 'w') as f:
        json.dump({'apy': profits, 'volume': daily_volumes}, f)
