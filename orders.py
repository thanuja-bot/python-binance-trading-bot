"""Order management layer.

OrderManager prepares parameters and delegates to BinanceFuturesClient.
It returns a clean, normalised response dict.
"""

from __future__ import annotations

from bot.client import BinanceFuturesClient
from bot.logging_config import logger


class OrderManager:
    """
    Handles order preparation and dispatch for USDT-M Futures Testnet.

    Supported order types: MARKET, LIMIT, STOP_MARKET
    """

    def __init__(self, client: BinanceFuturesClient) -> None:
        self._client = client

    def _build_params(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "GTC",
    ) -> dict:
        """Assemble the order parameter dict for the given order type."""
        params: dict = {
            "symbol":   symbol,
            "side":     side,
            "type":     order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            params["price"]       = price
            params["timeInForce"] = time_in_force

        elif order_type == "STOP_MARKET":
            params["stopPrice"] = stop_price

        logger.debug("Order params assembled: %s", params)
        return params

    def _clean_response(self, raw: dict) -> dict:
        """Extract and return the most relevant fields from the raw API response."""
        return {
            "orderId":       raw.get("orderId"),
            "symbol":        raw.get("symbol"),
            "side":          raw.get("side"),
            "type":          raw.get("type"),
            "status":        raw.get("status"),
            "origQty":       raw.get("origQty"),
            "executedQty":   raw.get("executedQty"),
            "avgPrice":      raw.get("avgPrice"),
            "price":         raw.get("price"),
            "stopPrice":     raw.get("stopPrice"),
            "timeInForce":   raw.get("timeInForce"),
            "clientOrderId": raw.get("clientOrderId"),
        }

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "GTC",
    ) -> dict:
        """
        Place an order and return a clean response dict.

        Args:
            symbol:        Trading pair, e.g. "BTCUSDT"
            side:          "BUY" or "SELL"
            order_type:    "MARKET", "LIMIT", or "STOP_MARKET"
            quantity:      Order quantity in base asset
            price:         Limit price (required for LIMIT)
            stop_price:    Stop trigger price (required for STOP_MARKET)
            time_in_force: "GTC", "IOC", or "FOK" (LIMIT only, default GTC)
        """
        params = self._build_params(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )
        raw_response = self._client.futures_create_order(**params)
        return self._clean_response(raw_response)
