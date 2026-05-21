"""Streamlit UI for the Binance Futures Testnet Trading Bot.

Reuses bot.client, bot.orders, and bot.validators — no duplicate order logic.

Run (from the trading_bot/ directory):
    streamlit run app.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure the project root (trading_bot/) is on sys.path so that
# "from bot.xxx import ..." works regardless of the working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from bot.client import BinanceFuturesClient, MissingAPIKeysError
from bot.logging_config import logger
from bot.orders import OrderManager
from bot.validators import ValidationError, validate_order_args

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Binance Futures Testnet Trading Bot",
    page_icon="📈",
    layout="centered",
)

st.title("📈 Binance Futures Testnet Trading Bot")
st.caption("Base URL: https://testnet.binancefuture.com — no real funds at risk")

# ──────────────────────────────────────────────────────────────────────────────
# Client — initialised once per process via st.cache_resource.
# Never call st.* inside a @st.cache_resource function; let it raise instead.
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Connecting to Binance Futures Testnet…")
def _create_client() -> BinanceFuturesClient:
    return BinanceFuturesClient()


try:
    client: BinanceFuturesClient = _create_client()
except MissingAPIKeysError as _exc:
    st.error(
        f"**API keys not configured.** {_exc}\n\n"
        "Copy `.env.example` to `.env`, add your Binance Futures Testnet keys, "
        "then restart with `streamlit run app.py`."
    )
    logger.error("Streamlit: missing API keys — %s", _exc)
    st.stop()
except Exception as _exc:
    st.error(f"**Failed to connect:** {_exc}")
    logger.exception("Streamlit: unexpected error creating client")
    st.stop()

manager = OrderManager(client)

# ──────────────────────────────────────────────────────────────────────────────
# Recent Orders — log parser
# ──────────────────────────────────────────────────────────────────────────────

# Matches lines written by client.py's ORDER_PLACED logger:
#   2026-05-21 08:00:00 | INFO     | trading_bot | ORDER_PLACED | orderId=... | ...
_ORDER_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"   # timestamp
    r".+ORDER_PLACED"                                     # marker
    r"\s*\|\s*orderId=(?P<orderId>[^\|]+)"
    r"\s*\|\s*symbol=(?P<symbol>[^\|]+)"
    r"\s*\|\s*side=(?P<side>[^\|]+)"
    r"\s*\|\s*type=(?P<type>[^\|]+)"
    r"\s*\|\s*status=(?P<status>[^\|]+)"
    r"\s*\|\s*qty=(?P<qty>[^\|]+)"
    r"\s*\|\s*avgPrice=(?P<avgPrice>.+)$"
)

_LOG_FILE = _PROJECT_ROOT / "logs" / "trading_bot.log"


def _load_recent_orders(max_rows: int = 50) -> list[dict]:
    """Parse the log file and return the last *max_rows* ORDER_PLACED entries."""
    if not _LOG_FILE.exists():
        return []
    rows: list[dict] = []
    try:
        with _LOG_FILE.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _ORDER_LINE_RE.match(line.rstrip())
                if m:
                    rows.append({
                        "Time":      m.group("ts"),
                        "Order ID":  m.group("orderId").strip(),
                        "Symbol":    m.group("symbol").strip(),
                        "Side":      m.group("side").strip(),
                        "Type":      m.group("type").strip(),
                        "Status":    m.group("status").strip(),
                        "Qty":       m.group("qty").strip(),
                        "Avg Price": m.group("avgPrice").strip(),
                    })
    except Exception as exc:
        logger.warning("Could not parse log file: %s", exc)
    return rows[-max_rows:]


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — account info & live price
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Account")

    if st.button("🔄 Refresh Balances"):
        st.session_state.pop("balances", None)

    if "balances" not in st.session_state:
        try:
            st.session_state["balances"] = client.get_account_balance()
        except Exception as exc:
            st.session_state["balances"] = []
            st.error(f"Could not load balances: {exc}")
            logger.error("Streamlit balance fetch failed: %s", exc)

    balances: list[dict] = st.session_state.get("balances", [])
    non_zero = [b for b in balances if float(b.get("balance", 0)) != 0]

    if non_zero:
        for b in non_zero:
            bal   = float(b.get("balance", 0))
            avail = float(b.get("availableBalance", 0))
            pnl   = float(b.get("crossUnPnl", 0))
            st.metric(
                label=b.get("asset", ""),
                value=f"{bal:.4f}",
                delta=f"PnL {pnl:+.4f}" if pnl != 0 else None,
            )
            st.caption(f"Available: {avail:.4f}")
    else:
        st.info("No non-zero balances.")

    st.divider()
    st.header("Live Price")
    price_symbol = st.text_input("Symbol", value="BTCUSDT", key="price_symbol").strip().upper()
    if st.button("Get Price"):
        try:
            data = client.get_symbol_price(price_symbol)
            st.metric("Mark Price", f"{float(data.get('markPrice', 0)):,.2f} USDT")
            st.caption(f"Index: {data.get('indexPrice', 'N/A')}")
        except Exception as exc:
            st.error(f"Price fetch failed: {exc}")
            logger.error("Streamlit price fetch failed: %s", exc)

# ──────────────────────────────────────────────────────────────────────────────
# Main panel — place order form
# ──────────────────────────────────────────────────────────────────────────────
st.header("Place Order")

col1, col2 = st.columns(2)

with col1:
    symbol     = st.text_input("Symbol", value="BTCUSDT").strip().upper()
    side       = st.selectbox("Side", ["BUY", "SELL"])
    order_type = st.selectbox("Order Type", ["MARKET", "LIMIT", "STOP_MARKET"])

with col2:
    quantity = st.number_input(
        "Quantity", min_value=0.0, value=0.001, step=0.001, format="%.3f"
    )

    price: float | None      = None
    stop_price: float | None = None

    if order_type == "LIMIT":
        raw_price = st.number_input(
            "Limit Price (USDT)", min_value=0.0, value=0.0, step=100.0, format="%.2f"
        )
        price = raw_price if raw_price > 0 else None

    if order_type == "STOP_MARKET":
        raw_stop = st.number_input(
            "Stop Price (USDT)", min_value=0.0, value=0.0, step=100.0, format="%.2f"
        )
        stop_price = raw_stop if raw_stop > 0 else None

# ── Order request summary ─────────────────────────────────────────────────────
st.subheader("Order Request Summary")
c0, c1, c2, c3 = st.columns(4)
c0.metric("Symbol",   symbol or "—")
c1.metric("Side",     side)
c2.metric("Type",     order_type)
c3.metric("Quantity", f"{quantity:.3f}")

if order_type == "LIMIT" and price is not None:
    st.caption(f"Limit Price: **{price:,.2f} USDT**")
if order_type == "STOP_MARKET" and stop_price is not None:
    st.caption(f"Stop Price: **{stop_price:,.2f} USDT**")

# ── Place Order button ────────────────────────────────────────────────────────
st.divider()
if st.button("🚀 Place Order", type="primary", use_container_width=True):

    try:
        sym, sd, ot, qty, pr, sp = validate_order_args(
            symbol, side, order_type, quantity, price, stop_price
        )
    except ValidationError as exc:
        st.error(f"❌ {exc}")
        logger.warning("Streamlit validation error: %s", exc)
        st.stop()

    with st.spinner("Placing order…"):
        try:
            result = manager.place_order(
                symbol=sym, side=sd, order_type=ot,
                quantity=qty, price=pr, stop_price=sp,
            )
        except BinanceAPIException as exc:
            msg = f"Binance API error {exc.code}: {exc.message}"
            st.error(f"❌ {msg}")
            logger.error("Streamlit order failed: %s", msg)
            st.stop()
        except BinanceRequestException as exc:
            msg = f"Network error: {exc.message}"
            st.error(f"❌ {msg}")
            logger.error("Streamlit order failed: %s", msg)
            st.stop()
        except Exception as exc:
            st.error(f"❌ Unexpected error: {exc}")
            logger.exception("Streamlit unexpected order error")
            st.stop()

    # ── Order response ─────────────────────────────────────────────────────────
    st.success("✅ Order submitted successfully!")
    st.subheader("Order Response")

    r0, r1, r2, r3 = st.columns(4)
    r0.metric("Order ID",     str(result.get("orderId", "—")))
    r1.metric("Status",       result.get("status", "—"))
    r2.metric("Executed Qty", result.get("executedQty", "—"))
    avg = result.get("avgPrice")
    r3.metric("Avg Price", f"{float(avg):,.2f}" if avg and avg != "0" else "—")

    with st.expander("Full Response"):
        cleaned = {
            k: v for k, v in result.items()
            if v not in (None, "", "0", "0.00000000", "0.0")
        }
        st.json(cleaned)

    logger.info(
        "Streamlit order placed | orderId=%s | status=%s",
        result.get("orderId"), result.get("status"),
    )

    # Invalidate the cached order history so the table refreshes immediately
    st.session_state.pop("recent_orders", None)

# ──────────────────────────────────────────────────────────────────────────────
# Recent Orders — parsed from logs/trading_bot.log
# ──────────────────────────────────────────────────────────────────────────────
st.divider()
st.header("📋 Recent Orders")

_orders_col, _refresh_col = st.columns([6, 1])
with _refresh_col:
    if st.button("🔄", help="Refresh order history"):
        st.session_state.pop("recent_orders", None)

if "recent_orders" not in st.session_state:
    st.session_state["recent_orders"] = _load_recent_orders()

orders = st.session_state["recent_orders"]

if not orders:
    st.info(
        "No orders recorded yet. Place an order above and it will appear here. "
        "Orders are read from `logs/trading_bot.log` — both CLI and UI orders are shown."
    )
else:
    # Reverse so newest is at the top
    display_rows = list(reversed(orders))

    # Colour-code the Side column
    import pandas as pd

    df = pd.DataFrame(display_rows)

    def _style_side(val: str) -> str:
        if val == "BUY":
            return "color: #22c55e; font-weight: bold"
        if val == "SELL":
            return "color: #ef4444; font-weight: bold"
        return ""

    def _style_status(val: str) -> str:
        if val == "FILLED":
            return "color: #22c55e; font-weight: bold"
        if val in ("CANCELED", "EXPIRED", "REJECTED"):
            return "color: #ef4444"
        return "color: #f59e0b"   # NEW / PARTIALLY_FILLED → amber

    styled = (
        df.style
        .applymap(_style_side,    subset=["Side"])
        .applymap(_style_status,  subset=["Status"])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(
        f"Showing last {len(orders)} order(s) from `logs/trading_bot.log`. "
        "Includes orders placed via CLI and this UI."
    )
