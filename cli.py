"""Command-line interface for the Binance Futures Testnet trading bot.

Commands
--------
    python -m bot.cli balance
    python -m bot.cli price  --symbol BTCUSDT
    python -m bot.cli order  --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
    python -m bot.cli order  --symbol BTCUSDT --side SELL --type LIMIT   --quantity 0.001 --price 120000
    python -m bot.cli order  --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 110000
"""

from __future__ import annotations

import argparse
import sys

from binance.exceptions import BinanceAPIException, BinanceRequestException
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.client import BinanceFuturesClient, MissingAPIKeysError
from bot.logging_config import logger
from bot.orders import OrderManager
from bot.validators import ValidationError, validate_order_args, validate_symbol

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Rich output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_order_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    stop_price: float | None,
) -> None:
    """Print a formatted order request summary before sending."""
    table = Table(
        title="Order Request", box=box.ROUNDED, border_style="cyan", show_header=False
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Symbol",   symbol)
    table.add_row(
        "Side",
        f"[green]{side}[/green]" if side == "BUY" else f"[red]{side}[/red]",
    )
    table.add_row("Type",     order_type)
    table.add_row("Quantity", str(quantity))
    if price is not None:
        table.add_row("Price",      str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))
    console.print(table)


def _print_order_response(result: dict) -> None:
    """Print a formatted order confirmation table."""
    table = Table(
        title="Order Response", box=box.ROUNDED, border_style="green", show_header=False
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    fields = [
        ("Order ID",        "orderId"),
        ("Symbol",          "symbol"),
        ("Side",            "side"),
        ("Type",            "type"),
        ("Status",          "status"),
        ("Orig Qty",        "origQty"),
        ("Executed Qty",    "executedQty"),
        ("Avg Price",       "avgPrice"),
        ("Price",           "price"),
        ("Stop Price",      "stopPrice"),
        ("Time In Force",   "timeInForce"),
        ("Client Order ID", "clientOrderId"),
    ]

    for label, key in fields:
        value = result.get(key)
        if value not in (None, "", "0", "0.00000000", "0.0"):
            table.add_row(label, str(value))

    console.print(table)
    console.print(
        Panel("[bold green]✔  Order submitted successfully![/bold green]", border_style="green")
    )


def _print_error(message: str) -> None:
    console.print(Panel(f"[bold red]✘  {message}[/bold red]", border_style="red"))


# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────

def cmd_balance(client: BinanceFuturesClient) -> None:
    """Fetch and display all non-zero futures balances."""
    try:
        balances = client.get_account_balance()
    except (BinanceAPIException, BinanceRequestException) as exc:
        _print_error(f"API error: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error fetching balance")
        _print_error(f"Unexpected error: {exc}")
        sys.exit(1)

    non_zero = [b for b in balances if float(b.get("balance", 0)) != 0]

    if not non_zero:
        console.print("[yellow]No non-zero balances found.[/yellow]")
        return

    table = Table(title="Account Balances", box=box.ROUNDED, border_style="cyan")
    table.add_column("Asset",             style="bold")
    table.add_column("Wallet Balance",    justify="right")
    table.add_column("Available Balance", justify="right")
    table.add_column("Unrealized PnL",    justify="right")

    for b in non_zero:
        pnl = float(b.get("crossUnPnl", 0))
        pnl_fmt = (
            f"[green]{pnl:.4f}[/green]" if pnl >= 0 else f"[red]{pnl:.4f}[/red]"
        )
        table.add_row(
            b.get("asset", ""),
            f"{float(b.get('balance', 0)):.4f}",
            f"{float(b.get('availableBalance', 0)):.4f}",
            pnl_fmt,
        )

    console.print(table)


def cmd_price(client: BinanceFuturesClient, symbol: str) -> None:
    """Fetch and display the mark/index price for a symbol."""
    try:
        symbol = validate_symbol(symbol)
    except ValidationError as exc:
        _print_error(str(exc))
        sys.exit(1)

    try:
        data = client.get_symbol_price(symbol)
    except (BinanceAPIException, BinanceRequestException) as exc:
        _print_error(f"API error: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error fetching price")
        _print_error(f"Unexpected error: {exc}")
        sys.exit(1)

    table = Table(
        title=f"Price — {symbol}", box=box.ROUNDED, border_style="cyan", show_header=False
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Symbol",            data.get("symbol", symbol))
    table.add_row("Mark Price",        data.get("markPrice",        "N/A"))
    table.add_row("Index Price",       data.get("indexPrice",       "N/A"))
    table.add_row("Last Funding Rate", data.get("lastFundingRate",  "N/A"))
    console.print(table)


def cmd_order(
    client: BinanceFuturesClient,
    symbol: str | None,
    side: str | None,
    order_type: str | None,
    quantity: float | None,
    price: float | None,
    stop_price: float | None,
) -> None:
    """Validate arguments, show a request summary, place the order, and display the result."""
    try:
        symbol, side, order_type, quantity, price, stop_price = validate_order_args(
            symbol, side, order_type, quantity, price, stop_price
        )
    except ValidationError as exc:
        _print_error(str(exc))
        sys.exit(1)

    _print_order_summary(symbol, side, order_type, quantity, price, stop_price)

    manager = OrderManager(client)
    try:
        result = manager.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except BinanceAPIException as exc:
        msg = f"Binance API error {exc.code}: {exc.message}"
        logger.error(msg)
        _print_error(msg)
        sys.exit(1)
    except BinanceRequestException as exc:
        msg = f"Network/request error: {exc.message}"
        logger.error(msg)
        _print_error(msg)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error placing order")
        _print_error(f"Unexpected error: {exc}")
        sys.exit(1)

    _print_order_response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bot.cli",
        description="Binance Futures Testnet — Trading Bot CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # balance
    subparsers.add_parser("balance", help="Show account balances")

    # price
    price_p = subparsers.add_parser("price", help="Show mark price for a symbol")
    price_p.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")

    # order
    order_p = subparsers.add_parser("order", help="Place a futures order")
    order_p.add_argument("--symbol",     required=True,  help="Trading pair, e.g. BTCUSDT")
    order_p.add_argument("--side",       required=True,  help="BUY or SELL")
    order_p.add_argument("--type",       required=True,  dest="order_type",
                         help="MARKET, LIMIT, or STOP_MARKET")
    order_p.add_argument("--quantity",   required=True,  type=float, help="Order quantity")
    order_p.add_argument("--price",      required=False, type=float,
                         help="Limit price in USDT (required for LIMIT orders)")
    order_p.add_argument("--stop-price", required=False, type=float, dest="stop_price",
                         help="Stop trigger price in USDT (required for STOP_MARKET orders)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        client = BinanceFuturesClient()
    except MissingAPIKeysError as exc:
        _print_error(str(exc))
        sys.exit(1)

    if args.command == "balance":
        cmd_balance(client)

    elif args.command == "price":
        cmd_price(client, args.symbol)

    elif args.command == "order":
        cmd_order(
            client=client,
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )


if __name__ == "__main__":
    main()
