"""Binance Futures Testnet API client.

Wraps python-binance's Client for USDT-M Futures Testnet, loading
credentials from .env and targeting https://testnet.binancefuture.com.

python-binance >= 1.0.36 notes
──────────────────────────────
• testnet=True makes _create_futures_api_uri use FUTURES_TESTNET_URL
  (https://testnet.binancefuture.com/fapi) automatically — no manual
  URL override is needed.
• In v1.0.36, futures_create_order silently reroutes conditional order
  types (STOP_MARKET, STOP, TAKE_PROFIT_MARKET …) to /fapi/v1/algoOrder
  and renames stopPrice → triggerPrice. The testnet does not expose the
  algo endpoint, so we bypass this routing and call _request_futures_api
  directly for those types.
"""

from __future__ import annotations

import os
import uuid

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

from bot.logging_config import logger

load_dotenv()

TESTNET_FUTURES_BASE = "https://testnet.binancefuture.com"

# Order types that v1.0.36 routes to /algoOrder — we bypass that on testnet
_CONDITIONAL_TYPES = frozenset(
    {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET"}
)


class MissingAPIKeysError(Exception):
    """Raised when BINANCE_API_KEY or BINANCE_API_SECRET is not set."""


class BinanceFuturesClient:
    """
    Authenticated client for Binance USDT-M Futures Testnet.

    Credentials are loaded from environment variables:
        BINANCE_API_KEY
        BINANCE_API_SECRET
    """

    def __init__(self) -> None:
        api_key    = os.getenv("BINANCE_API_KEY",    "").strip()
        api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

        if not api_key or not api_secret:
            msg = (
                "BINANCE_API_KEY and BINANCE_API_SECRET must be set. "
                "Copy .env.example to .env and fill in your testnet credentials."
            )
            logger.error(msg)
            raise MissingAPIKeysError(msg)

        # testnet=True  → _create_futures_api_uri picks FUTURES_TESTNET_URL
        #                  (https://testnet.binancefuture.com/fapi) automatically.
        # ping=False    → skip the spot-API connectivity ping that Client.__init__
        #                  fires by default; we only use the futures endpoint.
        self._client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True,
            ping=False,
        )

        logger.info(
            "BinanceFuturesClient initialised | base=%s", TESTNET_FUTURES_BASE
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _place_order_direct(self, **params: object) -> dict:
        """
        POST to /fapi/v1/order directly, bypassing python-binance's
        algo-endpoint routing for conditional order types.

        Required for STOP_MARKET, STOP, TAKE_PROFIT_MARKET, etc. on the
        testnet, which does not expose /fapi/v1/algoOrder.
        """
        if "newClientOrderId" not in params:
            params["newClientOrderId"] = "x-testbot-" + uuid.uuid4().hex[:8]
        return self._client._request_futures_api("post", "order", True, data=params)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def futures_create_order(self, **kwargs: object) -> dict:
        """
        Place a futures order.

        MARKET / LIMIT  → delegates to the library's futures_create_order
                          (/fapi/v1/order via the library's normal path).
        Conditional types (STOP_MARKET, STOP, TAKE_PROFIT_MARKET …)
                        → calls /fapi/v1/order directly to avoid the
                          v1.0.36 algo routing that the testnet does not support.

        Logs the outgoing parameters and the raw response.
        """
        order_type = str(kwargs.get("type", "")).upper()
        logger.info("API REQUEST | futures_create_order | params=%s", kwargs)

        try:
            if order_type in _CONDITIONAL_TYPES:
                response = self._place_order_direct(**kwargs)
            else:
                response = self._client.futures_create_order(**kwargs)

            logger.info("API RESPONSE | futures_create_order | response=%s", response)

            # Structured marker parsed by the Streamlit "Recent Orders" panel.
            # Format: ORDER_PLACED | field=value | field=value ...
            logger.info(
                "ORDER_PLACED | orderId=%s | symbol=%s | side=%s | type=%s"
                " | status=%s | qty=%s | avgPrice=%s",
                response.get("orderId", ""),
                response.get("symbol", ""),
                response.get("side", ""),
                response.get("type", ""),
                response.get("status", ""),
                response.get("executedQty", response.get("origQty", "")),
                response.get("avgPrice", ""),
            )

            return response

        except BinanceAPIException as exc:
            logger.error(
                "BinanceAPIException | status=%s | code=%s | msg=%s",
                exc.status_code, exc.code, exc.message,
            )
            raise
        except BinanceRequestException as exc:
            logger.error("BinanceRequestException | msg=%s", exc.message)
            raise
        except Exception as exc:
            logger.exception("Unexpected error in futures_create_order: %s", exc)
            raise

    def get_account_balance(self) -> list[dict]:
        """
        Return all asset balances for the futures account.
        Uses /fapi/v3/balance (python-binance default for futures_account_balance).
        """
        logger.info("API REQUEST | futures_account_balance")
        try:
            response = self._client.futures_account_balance()
            logger.info(
                "API RESPONSE | futures_account_balance | assets=%d", len(response)
            )
            return response
        except BinanceAPIException as exc:
            logger.error(
                "BinanceAPIException | futures_account_balance | code=%s | msg=%s",
                exc.code, exc.message,
            )
            raise
        except BinanceRequestException as exc:
            logger.error(
                "BinanceRequestException | futures_account_balance | msg=%s",
                exc.message,
            )
            raise
        except Exception as exc:
            logger.exception("Unexpected error in get_account_balance: %s", exc)
            raise

    def get_symbol_price(self, symbol: str) -> dict:
        """
        Return mark price and index price for *symbol* via
        /fapi/v1/premiumIndex.
        """
        symbol = symbol.upper()
        logger.info("API REQUEST | futures_mark_price | symbol=%s", symbol)
        try:
            response = self._client.futures_mark_price(symbol=symbol)
            logger.info(
                "API RESPONSE | futures_mark_price | symbol=%s | markPrice=%s",
                symbol, response.get("markPrice"),
            )
            return response
        except BinanceAPIException as exc:
            logger.error(
                "BinanceAPIException | futures_mark_price | code=%s | msg=%s",
                exc.code, exc.message,
            )
            raise
        except BinanceRequestException as exc:
            logger.error(
                "BinanceRequestException | futures_mark_price | msg=%s", exc.message
            )
            raise
        except Exception as exc:
            logger.exception("Unexpected error in get_symbol_price: %s", exc)
            raise
