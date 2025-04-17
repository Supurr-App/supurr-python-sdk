from abc import ABC, abstractmethod
from enum import Enum
from supurr_sdk.utils import is_valid_literal
from eth_account import Account
from eth_account.messages import encode_structured_data, encode_defunct
from web3 import Web3
import copy
import time

import requests
from typing import Literal, TypedDict, cast, Any
from supurr_sdk.constants import (
    zero_address,
    contracts,
    exchange_remote_hosts,
    ValidTokens,
    ValidProducts,
    pyth_info,
    chain,
)


class MarketConfig(TypedDict):
    category: str
    tv_id: str
    pair: str
    price_precision: int
    token0: str
    token1: str
    full_name: str
    img: str
    pythId: str
    pythGroup: str
    expo: int


indexer = exchange_remote_hosts["indexer"]
api = exchange_remote_hosts["api"]
pyth = exchange_remote_hosts["pyth"]


def fetch_from_indexer(
    query: str,
) -> dict[str, dict[str, dict[str, list[dict[str, str]]]]]:
    response = requests.post(
        indexer,
        json={"query": query},
    )
    response.raise_for_status()
    return response.json()


class Market:
    name: str
    contract: str
    price_precision: int
    extra: Any

    def __init__(self, name: str, contract: str, price_precision=1, extra: Any = None):
        self.name = name
        self.contract = contract
        self.price_precision = price_precision
        self.extra = extra


class PriceClient(ABC):
    @abstractmethod
    def get_price(self, market: Market) -> float:
        pass


class PythPriceClient(PriceClient):
    pyth_mappings = pyth_info

    @staticmethod
    def get_decimal_price(price: str, expo: int) -> float:
        return float(price) * (float(10) ** expo)

    def get_price(self, market: Market) -> float:
        if market.name not in self.pyth_mappings:
            raise ValueError(f"{market.name} isn't supported")
        pyth_info = self.pyth_mappings[market.name]
        response = requests.get(f"{pyth}?ids[]={pyth_info['pythId']}")
        response.raise_for_status()
        data = response.json()

        if not len(data):
            raise ValueError(f"No price data found for {market.name}")

        price_data = data[0]["price"]
        price = self.get_decimal_price(price_data["price"], price_data["expo"])
        print("price", price)
        return int(price * 10 ** self.pyth_mappings[market.name]["expo"])


class SignerManager(ABC):
    primary_type: dict[str, Any]

    def sign_message(self, message: dict[str, Any], account: Account) -> str:
        msg_copy = copy.deepcopy(self.primary_type)
        msg_copy["message"] = message
        msg = encode_structured_data(msg_copy)
        return account.sign_message(msg)


class OneCtGenerator(SignerManager):
    def __init__(self):
        self.primary_type = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Registration": [
                    {"name": "content", "type": "string"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "chainId", "type": "uint256"},
                ],
            },
            "domain": {
                "name": "Ether Mail",
                "version": "1",
                "chainId": chain["id"],
                "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
            },
            "primaryType": "Registration",
        }


class OneCtRegisterer(SignerManager):
    def __init__(self):
        self.primary_type = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "RegisterAccount": [
                    {"name": "oneCT", "type": "address"},
                    {"name": "user", "type": "address"},
                    {"name": "nonce", "type": "uint256"},
                ],
            },
            "domain": {
                "name": "Validator",
                "version": "1",
                "chainId": chain["id"],
                "verifyingContract": Web3.toChecksumAddress(
                    contracts["account_registry"]
                ),
            },
            "primaryType": "RegisterAccount",
        }


class Signer:
    account: Account
    nonce: int
    auth_key: str

    def __init__(self, _private_key: str, nonce: int):
        self.account = Account.from_key(_private_key)
        auth_msg = encode_defunct(
            text="Sign to verify your user address with Buffer Finance v2.5 on Arbitrum One and Arbitrum Goerli"
        )
        pack = self.account.sign_message(auth_msg)
        self.auth_key = Web3.toHex(cast(Any, pack)["signature"])
        self.nonce = nonce


class User:
    account: Account
    signer: Signer

    def __init__(self, _private_key: str):
        self.account = Account.from_key(_private_key)
        r = requests.get(
            f"{api}/user/onc_ct?environment={chain['id']}&user={cast(Any, self.account).address}"
        )
        r.raise_for_status()
        res = r.json()
        cast(Any, res)
        nonce = res["nonce"]
        one_ct_creation_signer = OneCtGenerator()
        sign_message = {
            "content": "I want to create a trading account with Supurr App",
            "nonce": nonce,
            "chainId": chain["id"],
        }
        pack = one_ct_creation_signer.sign_message(sign_message, self.account)
        signature = Web3.toHex(cast(Any, pack)["signature"])
        signature_bytes = Web3.toBytes(hexstr=signature)
        private_key = Web3.keccak(signature_bytes).hex()[2:]
        self.signer = Signer(private_key, nonce)
        if Web3.toChecksumAddress(res["one_ct"]) != Web3.toChecksumAddress(
            cast(Any, self.signer.account).address
        ):
            one_ct_registration_signer = OneCtRegisterer()
            sign_message = {
                "oneCT": cast(Any, self.signer.account).address,
                "user": cast(Any, self.account).address,
                "nonce": res["nonce"],
            }
            pack = one_ct_registration_signer.sign_message(sign_message, self.account)
            signature = Web3.toHex(cast(Any, pack)["signature"])
            apiParams = {
                "one_ct": cast(Any, self.signer.account).address,
                "account": cast(Any, self.account).address,
                "nonce": res["nonce"],
                "registration_signature": signature,
                "environment": chain["id"],
            }
            r = requests.post(f"{api}register/", params=apiParams)
            r.raise_for_status()
            res = r.json()
            cast(Any, res)


class Product(ABC):
    router: str
    markets: list[Market] = []
    signer_manager: SignerManager
    product_id: str
    active_market: Market

    def set_active_market(self, market: str):
        for m in self.markets:
            if m.name.lower() == market.lower():
                self.active_market = m
                return
        raise ValueError(f"Market {market} not found")

    @abstractmethod
    def place_order(
        self, is_up: bool, amount: int, expiration: int, context: Any
    ) -> float:
        pass

    @abstractmethod
    def get_max_trade_size(self, context: Any) -> int:
        pass

    def fill_allowance(self, amount: int, context: Any):
        (allowance, nonce) = context.token.get_allowance(
            cast(Any, context.user.account).address, context=self
        )
        if allowance < amount:
            context.token.approve(context.user, nonce, context=self)
        else:
            print("allowance is enough")


class Token(Market, SignerManager):
    decimals: int
    pool: str

    def __init__(
        self, name: str, decimals: int, contract: str, pool: str, price_precision=1
    ):
        self.name = name
        self.decimals = decimals
        self.contract = contract
        self.token0 = name
        self.token1 = "USD"
        self.price_precision = price_precision
        self.pool = pool
        self.primary_type = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "domain": {
                "name": name,
                "version": "1",
                "chainId": chain["id"],
                "verifyingContract": contract,
            },
            "primaryType": "Permit",
        }

    def get_allowance(self, owner: str, context: Product) -> tuple[Any, Any]:
        r = requests.get(
            f"{api}/user/approval/",
            params={
                "environment": chain["id"],
                "user": owner,
                "token": self.name,
                "product_id": context.product_id,
            },
        )
        r.raise_for_status()
        res = r.json()
        cast(Any, res)
        return (res["allowance"], res["nonce"])

    def approve(self, owner: User, nonce: int, context: Product):
        amount = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        deadline = int(time.time()) + 86400
        user_address = cast(Any, owner.account).address
        pack = self.sign_message(
            {
                "nonce": nonce,
                "value": amount,
                "owner": user_address,
                "deadline": deadline,
                "spender": context.router,
            },
            owner.account,
        )
        r = Web3.toHex(cast(Any, pack)["r"])
        s = Web3.toHex(cast(Any, pack)["s"])
        v = cast(Any, pack)["v"]
        api_params = {
            "user": user_address,
            "nonce": nonce,
            "allowance": amount,
            "deadline": deadline,
            "v": v,
            "r": r,
            "s": s,
            "user_signature": owner.signer.auth_key,
            "environment": chain["id"],
            "state": "PENDING",
            "product_id": context.product_id,
            "token": self.name,
        }
        r = requests.post(f"{api}approve/", params=api_params)
        r.raise_for_status()

    def get_balance(self, owner: str) -> float:
        return 32

    def get_price(self) -> float:
        return 32


class UpDownSignerManager(SignerManager):
    def __init__(self, verifying_contract: str):
        self.primary_type = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "UserTradeSignatureWithSettlementFee": [
                    {"name": "user", "type": "address"},
                    {"name": "totalFee", "type": "uint256"},
                    {"name": "period", "type": "uint256"},
                    {"name": "targetContract", "type": "address"},
                    {"name": "strike", "type": "uint256"},
                    {"name": "slippage", "type": "uint256"},
                    {"name": "allowPartialFill", "type": "bool"},
                    {"name": "referralCode", "type": "string"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "settlementFee", "type": "uint256"},
                    {"name": "isAbove", "type": "bool"},
                ],
            },
            "domain": {
                "name": "Validator",
                "version": "1",
                "chainId": chain["id"],
                "verifyingContract": verifying_contract,
            },
            "primaryType": "UserTradeSignatureWithSettlementFee",
        }


class SupurrExchange:
    token: Token
    user: User
    product: Product
    price_provider: PriceClient
    rpc = Web3(Web3.HTTPProvider(chain["rpc"]))

    def __init__(
        self,
        pk: str,
        product: ValidProducts,
        token: ValidTokens = "WHYPE",
        price_provider: PriceClient = PythPriceClient(),
    ):
        self._set_token(token)
        self._set_product(product)
        self._set_price_provider(price_provider)

        self._set_account(pk)

    def set_market(self, market: str):
        self.product.set_active_market(market)

    def _set_token(self, token_str: ValidTokens):
        if not is_valid_literal(token_str, ValidTokens):
            raise ValueError(f"Invalid token: {token_str}")
        token_config = contracts["token"][token_str]
        self.token = Token(
            token_str,
            token_config["decimals"],
            token_config["address"],
            token_config["pool"],
        )

    def _set_product(self, product_str: ValidProducts):
        if not is_valid_literal(product_str, ValidProducts):
            raise ValueError(f"Invalid product: {product_str}")
        product = UpDownProduct(product_str, self.token.pool)
        self.product = product

    def _set_price_provider(self, price_provider: PriceClient):
        self.price_provider = price_provider

    def _set_account(self, pk: str):
        self.user = User(pk)

    def place_order(self, is_up: bool, amount: int, expiration: int) -> float:
        return self.product.place_order(is_up, amount, expiration, context=self)

    def get_max_trade_size(self) -> int:
        return self.product.get_max_trade_size(context=self)


class UpDownProduct(Product):
    slippage = 5
    allow_partial_fill = True
    referral_code = ""

    def __init__(self, router: str, pool: str):
        self.router = contracts["router"][router]
        self.product_id = "abc"
        self.signer_manager = UpDownSignerManager(self.router)
        query = """
        {
        optionContracts(limit:1000,where:{routerContract:"${router}", poolContract:"${pool}"}){
            items{
            configContract {
                address
                maxFee
                maxPeriod
                minFee
                minPeriod
                platformFee
                earlyCloseThreshold
                isEarlyCloseEnabled
                IV
                IVFactorOTM
                IVFactorITM
                creationWindowAddress
            }
            routerContract
            address
            poolContract
            isPaused
            category
            asset
            isRegistered
            pool
            }
        }
        }
        """

        res = fetch_from_indexer(
            query.replace("${router}", self.router).replace("${pool}", pool)
        )
        cmarkets = res["data"]["optionContracts"]["items"]
        for cmarket in cmarkets:
            if cmarket["isRegistered"] and not cmarket["isPaused"]:
                self.markets.append(
                    Market(
                        name=cmarket["asset"],
                        contract=cmarket["address"],
                        extra=cmarket,
                    )
                )
        self.set_active_market(self.markets[0].name)

    def place_order(
        self, is_up: bool, amount: int, period: int, context: SupurrExchange
    ) -> Any:
        self.fill_allowance(amount, context=context)
        e = self.active_market.extra["configContract"]
        min_fee = int(e["minFee"])
        max_period = int(e["maxPeriod"])
        min_period = int(e["minPeriod"])
        max_size = self.get_max_trade_size(context=context)
        if amount < min_fee:
            raise ValueError(f"Amount is less than min fee : {min_fee}")
        if period < min_period:
            raise ValueError(f"Period is less than min period : {min_period}")
        if period > max_period:
            raise ValueError(f"Period is greater than max period : {max_period}")
        if amount > max_size:
            raise ValueError(f"Amount is greater than max trade size : {max_size}")
        sf_pack = self._get_specific_sf(duration=period, isAbove=is_up)
        sf = sf_pack["settlement_fee"]
        timestamp = int(time.time())
        price = context.price_provider.get_price(self.active_market)
        msg_to_sign = {
            "user": cast(Any, context.user.account).address,
            "totalFee": amount,
            "period": period,
            "targetContract": self.active_market.contract,
            "strike": price,
            "slippage": self.slippage,
            "allowPartialFill": self.allow_partial_fill,
            "referralCode": self.referral_code,
            "settlementFee": sf,
            "timestamp": timestamp,
            "isAbove": is_up,
        }
        pack = self.signer_manager.sign_message(
            msg_to_sign,
            context.user.signer.account,
        )
        signature = Web3.to_hex(cast(Any, pack)["signature"])
        apiParams = {
            "signature_timestamp": timestamp,
            "strike": price,
            "period": period,
            "target_contract": self.active_market.contract,
            "partial_signature": signature,
            "full_signature": signature,
            "user_address": cast(Any, context.user.account).address,
            "trade_size": amount,
            "allow_partial_fill": self.allow_partial_fill,
            "referral_code": self.referral_code,
            "trader_nft_id": 0,
            "slippage": self.slippage,
            "is_above": is_up,
            "is_limit_order": False,
            "limit_order_duration": 0,
            "settlement_fee": sf,
            "settlement_fee_sign_expiration": sf_pack["settlement_fee_sign_expiration"],
            "settlement_fee_signature": sf_pack["settlement_fee_signature"],
            "product_id": self.product_id,
            "token": context.token.name,
            "strike_timestamp": timestamp,
        }
        print("apiParams", apiParams)
        r = requests.post(
            f"{api}/create/", json=apiParams, params={"environment": chain["id"]}
        )
        r.raise_for_status()
        res = r.json()
        return res

    def get_max_trade_size(self, context: SupurrExchange) -> int:
        """Get the maximum trade size from the active market contract."""
        market_contract = context.rpc.eth.contract(
            address=Web3.to_checksum_address(self.active_market.contract),
            abi=[
                {
                    "inputs": [],
                    "name": "getMaxTradeSize",
                    "outputs": [
                        {"internalType": "uint256", "name": "", "type": "uint256"}
                    ],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )
        return market_contract.functions.getMaxTradeSize().call()

    def _get_specific_sf(self, duration: int, isAbove: bool):
        sf = self.get_sf()
        dir = "up" if isAbove else "down"
        last_active_sf = None
        duration = int(duration / 60)
        for s in sf[dir]:
            if s["period"] <= duration:
                last_active_sf = s
        if last_active_sf is None:
            raise ValueError(
                f"No settlement fee found for duration: {duration} and direction: {dir}"
            )
        return last_active_sf

    def get_sf(self):
        r = requests.get(
            f"{api}/settlement_fee/",
            params={
                "environment": chain["id"],
                "product_id": self.product_id,
                "queryPair": self.active_market.name,
            },
        )
        r.raise_for_status()
        res = r.json()
        cast(Any, res)

        return res


class AboveBelowProduct(Product):
    def place_order(
        self, is_up: bool, amount: int, expiration: int, context: SupurrExchange
    ):
        pass


# fetch sf  : 10
# fetch iv : 10
# calculate maxfeepercontract based on iv using black scholes : 60
# prepare api params : 30
# sign : 30
# call api : 30

# add ongoing trade tracking


# TODO add balance check
# TODO add ongoing trade tracking
