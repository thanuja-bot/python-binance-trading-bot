"""Input validation for CLI arguments and Streamlit UI inputs."""

from __future__ import annotations

from bot.logging_config import logger

VALID_SIDES = {"BUY", "SELL"}
VALID_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


class ValidationError(Exception):
    """Raised when any input fails validation."""


def validate_symbol(symbol: str | None) -> str:
    """Return symbol in uppercase, or raise ValidationError if missing."""
    if not symbol or not symbol.strip():
        msg = "Validation error: --symbol is required."
        logger.warning(msg)
        raise ValidationError(msg)
    return symbol.strip().upper()


def validate_side(side: str | None) -> str:
    """Return side in uppercase, or raise ValidationError if not BUY/SELL."""
    if not side or side.upper() not in VALID_SIDES:
        msg = f"Validation error: --side must be BUY or SELL (got: {side!r})."
        logger.warning(msg)
        raise ValidationError(msg)
    return side.upper()


def validate_order_type(order_type: str | None) -> str:
    """Return order type in uppercase, or raise ValidationError if unsupported."""
    if not order_type or order_type.upper() not in VALID_TYPES:
        msg = (
            f"Validation error: --type must be one of "
            f"{', '.join(sorted(VALID_TYPES))} (got: {order_type!r})."
        )
        logger.warning(msg)
        raise ValidationError(msg)
    return order_type.upper()


def validate_quantity(quantity: float | None) -> float:
    """Return quantity, or raise ValidationError if not a positive number."""
    if quantity is None:
        msg = "Validation error: --quantity is required."
        logger.warning(msg)
        raise ValidationError(msg)
    if quantity <= 0:
        msg = f"Validation error: --quantity must be greater than 0 (got: {quantity})."
        logger.warning(msg)
        raise ValidationError(msg)
    return quantity


def validate_price(price: float | None, order_type: str) -> float | None:
    """For LIMIT orders, ensure --price is provided and positive."""
    if order_type == "LIMIT":
        if price is None:
            msg = "Validation error: --price is required for LIMIT orders."
            logger.warning(msg)
            raise ValidationError(msg)
        if price <= 0:
            msg = f"Validation error: --price must be greater than 0 (got: {price})."
            logger.warning(msg)
            raise ValidationError(msg)
    return price


def validate_stop_price(stop_price: float | None, order_type: str) -> float | None:
    """For STOP_MARKET orders, ensure --stop-price is provided and positive."""
    if order_type == "STOP_MARKET":
        if stop_price is None:
            msg = "Validation error: --stop-price is required for STOP_MARKET orders."
            logger.warning(msg)
            raise ValidationError(msg)
        if stop_price <= 0:
            msg = f"Validation error: --stop-price must be greater than 0 (got: {stop_price})."
            logger.warning(msg)
            raise ValidationError(msg)
    return stop_price


def validate_order_args(
    symbol: str | None,
    side: str | None,
    order_type: str | None,
    quantity: float | None,
    price: float | None,
    stop_price: float | None,
) -> tuple[str, str, str, float, float | None, float | None]:
    """
    Run all order-field validations and return the cleaned values.

    Returns:
        (symbol, side, order_type, quantity, price, stop_price)
    """
    symbol     = validate_symbol(symbol)
    side       = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity   = validate_quantity(quantity)
    price      = validate_price(price, order_type)
    stop_price = validate_stop_price(stop_price, order_type)
    return symbol, side, order_type, quantity, price, stop_price
