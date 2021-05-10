import json
from web3.exceptions import BadFunctionCallOutput


def load_abi(fname):
    import os.path
    fname = os.path.join(os.path.dirname(__file__), 'abis', fname + '.json')
    with open(fname) as f:
        return json.load(f)['abi']


class Pool:
    def __init__(self, pool, token, stable_pool, w3=None):
        if not w3:
            from .w3 import w3 as our_w3
            self.w3 = our_w3()
        erc20 = load_abi("CurveTokenV4")

        self.pool_contract = self.w3.eth.contract(abi=load_abi("CurveCryptoSwap"), address=pool)
        self.pool = self.pool_contract.functions
        self.token_contract = self.w3.eth.contract(abi=erc20, address=token)
        self.token = self.token_contract.functions

        self.stableswap = self.w3.eth.contract(abi=load_abi("Stableswap"), address=stable_pool)

        self.N = 0
        self.underlying_coins = []
        self.coins = []
        self.decimals = []
        self.underlying_decimals = []

        for i in range(10):
            try:
                c = self.pool.coins(i).call()
                self.coins.append(c)
                self.N += 1
                if i == 0:
                    pass
                    # uc = self.w3.eth.contract(abi=erc20)
                else:
                    self.underlying_coins.append(c)
            except (BadFunctionCallOutput, ValueError):
                if i == 0:
                    raise
                else:
                    break
