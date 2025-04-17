# Supurr SDK

A Python SDK for interacting with the Supurr protocol, supporting both Up/Down and Above/Below trading products.

## Installation

```bash
pip install supurr-sdk
```

## Quick Start

### Initialize the Exchange

```python
from supurr_sdk import SupurrExchange

# Initialize with your private key and desired product
exchange = SupurrExchange(
    pk="your_private_key",
    product="up_down"  # or "above_below"
)
```

### Accessing Token Information

```python
# Get token name
token_name = exchange.token.name  # e.g., "WHYPE"

# Get token decimals
decimals = exchange.token.decimals  # e.g., 18

# Convert human readable amount to token decimals
amount = int(0.1 * 10**exchange.token.decimals)  # 0.1 token in decimals

# Convert token decimals to human readable amount
human_readable = amount / 10**exchange.token.decimals  # back to 0.1
```

### Trading with Up/Down Product

```python
# Set the active market
exchange.product.set_active_market("BTCUSD")

# Place a trade
result = exchange.place_trade(
    is_up=True,  # True for up, False for down
    amount=int(0.1 * 10**18),  # Amount in token-decimals
    duration=360  # Expiration time in seconds (should be multiple of 60)
)
```

### Trading with Above/Below Product

```python
# Set the active market
exchange.product.set_active_market("BTCUSD")

# Get valid expiry timestamps
valid_timestamps = exchange.product.get_valid_expiry_timestamps()

# Place a trade with strike price
result = exchange.place_trade(
    is_up=True,  # True for above, False for below
    amount=int(0.01 * 10**18),  # Amount in token-decimals
    expiration=valid_timestamps[0],  # Use a valid timestamp
    strike=84000  # Strike price
)
```

### Checking Current Price

```python
# Get current price for the active market
current_price = exchange.price_provider.get_price(exchange.product.active_market)
```

## Features

- Support for both Up/Down and Above/Below trading products
- Integration with Pyth price feeds
- Automatic market selection and validation
- Built-in token approval handling
- Support for multiple markets (e.g., BTCUSD)

## Available Markets

```python
# Get current price for the active market
current_markets = exchange.product.markets
```

- BTCUSD (with price precision of 1)

## Error Handling

The SDK includes built-in validation for:

- Invalid expiration times
- Invalid strike prices
- Market availability
- Token approvals
- Max trade size availability

## Notes

- All amounts should be provided in token-decimals (if token has 18 decimals than; 1Token= 10^18)
- All time related information is expected in seconds (not ms).
- The SDK uses Web3.py for blockchain interactions
- Make sure to have sufficient token in wallet before trading

## Development

To run the test suite:

```bash
pytest tests/
```
