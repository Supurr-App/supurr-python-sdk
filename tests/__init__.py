from supurr_sdk.Exchange import SupurrExchange, PythPriceClient, Market, User
from typing import Any, cast
from web3 import Web3
import pytest
from supurr_sdk.constants import contracts, zero_address

# add your account here
dummy_account = {
    "address": "0xb12eec31E0b0Dd01CEc1B30b3c89bf09C3EB7BFE",
    "pk": "0x89bc75841ad12f7df8c5e93205edef9780bf50738aeecb067ba55da4b724837c",
}


def test_pyth_price_client():
    p = PythPriceClient()
    btc = Market("BTCUSD", "0xd")
    assert p.get_price(btc) > 0


def test_user_creation():
    user = User(dummy_account["pk"])
    assert Web3.toChecksumAddress(cast(Any, user.account).address) != zero_address


def test_up_down_init():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="up_down")
    assert exchange.token.name == "WHYPE"
    assert exchange.product.router == contracts["router"]["up_down"]
    assert exchange.product.active_market.name == "BTCUSD"
    assert exchange.product.active_market.price_precision == 1
    print("test up down passed")


def test_up_down_trade():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="up_down")
    exchange.product.set_active_market("BTCUSD")
    p = exchange.place_trade(
        is_up=True,
        amount=int(0.1 * 10**18),
        duration=360,
    )
    print("trade result", p)
    print("test up down passed")


def test_approve():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="up_down")
    exchange.product.set_active_market("BTCUSD")
    exchange.place_trade(
        is_up=True,
        amount=int(2 * 10**18),
        duration=int(10 * 60),
    )


def test_above_below_init():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="above_below")
    assert exchange.token.name == "WHYPE"
    assert exchange.product.router == contracts["router"]["above_below"]
    assert exchange.product.active_market.name == "BTCUSD"
    assert exchange.product.active_market.price_precision == 1
    print("test above below passed")
    exchange.product.set_active_market("BTCUSD")
    print("Trade with invalid expiration, tend to fail")

    with pytest.raises(ValueError):
        exchange.place_trade(
            is_up=True,
            amount=int(2 * 10**18),
            expiration=int(10 * 60),
            strike=80010,
        )
    ts = exchange.product.get_valid_expiry_timestamps()
    print(ts)

    print("Trade with enoromous strike, tend to fail")
    with pytest.raises(ValueError):
        exchange.place_trade(
            is_up=False,
            amount=int(2 * 10**18),
            expiration=ts[0],
            strike=800500,
        )
    p = exchange.place_trade(
        is_up=False,
        amount=int(0.01 * 10**18),
        expiration=ts[0],
        strike=84000,
    )
    print("trade result", p)
    # print("prob", p)
    # p = exchange.place_trade(
    #     is_up=True,
    #     amount=int(2 * 10**18),
    #     expiration=ts[0],
    #     strike=84000,
    # )
    # print("prob", p)
    print("test above below passed")


def test_above_below_trade():
    exchange = SupurrExchange(pk=dummy_account["pk"], product="above_below")
    exchange.product.set_active_market("BTCUSD")

    ts = exchange.product.get_valid_expiry_timestamps()

    p = exchange.place_trade(
        is_up=True,
        amount=int(0.01 * 10**18),
        expiration=ts[0],
        strike=84000,
    )
    print("trade result", p)
    # print("prob", p)
    # p = exchange.place_trade(
    #     is_up=True,
    #     amount=int(2 * 10**18),
    #     expiration=ts[0],
    #     strike=84000,
    # )
    # print("prob", p)
    print("test above below passed")
