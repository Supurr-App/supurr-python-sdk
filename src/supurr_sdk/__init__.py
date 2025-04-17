from supurr_sdk.Exchange import SupurrExchange, PythPriceClient, Market, User
from supurr_sdk.constants import zero_address, contracts
from typing import Any, cast
from web3 import Web3

__all__ = [
    "SupurrExchange",
]

dummy_account = {
    "address": "0x1F950c2945dB7D091a15300db6d38B7d21285859",
    "pk": "0x9052d8daf692ec428a084fb90de7e9d6dc7067bb499ec94ad23c1bbe568408f0",
}


def test_pyth_price_client():
    p = PythPriceClient()
    btc = Market("BTCUSD", "0xd")
    assert p.get_price(btc) > 0


def test_user_creation():
    user = User(dummy_account["pk"])
    assert Web3.toChecksumAddress(cast(Any, user.account).address) != zero_address


# def test_above_below_init():
#     exchange = SupurrExchange(pk=dummy_account["pk"],product='above_below')
#     assert exchange.token.name == 'WHYPE'
#     assert exchange.product.router == contracts["router"]["above_below"]
#     assert exchange.product.markets[0].name == 'BTCUSD'
#     assert exchange.product.markets[0].price_precision == 1
#     print("test above below passed")


def test_up_down_init():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="up_down")
    assert exchange.token.name == "WHYPE"
    assert exchange.product.router == contracts["router"]["up_down"]
    assert exchange.product.active_market.name == "BTCUSD"
    assert exchange.product.active_market.price_precision == 1
    print("test up down passed")


def test_approve():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="up_down")
    exchange.product.set_active_market("BTCUSD")
    exchange.place_order(
        is_up=True,
        amount=int(2 * 10**18),
        expiration=int(10 * 60),
    )


if __name__ == "__main__":
    test_approve()
    # test_pyth_price_client()
