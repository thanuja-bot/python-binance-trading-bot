# trading_bot — Binance Futures Testnet Trading Bot

A clean, well-structured Python 3 project for placing and managing orders on the **Binance USDT-M Futures Testnet** — usable both from the command line and via a Streamlit web UI.

---

## Features

- Place **MARKET**, **LIMIT**, and **STOP_MARKET** orders (BUY / SELL)
- Check **account balances** and **live mark price**
- **Rich-formatted** tables and panels for all CLI output
- **Streamlit UI** (`app.py`) — browser-based order form with live results
- Full **input validation** with clear error messages in both CLI and UI
- **Rotating log file** (`logs/trading_bot.log`) — every request, response, and error
- Robust error handling: API errors, network errors, missing keys, bad input

---

## Folder Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package marker
│   ├── client.py            # BinanceFuturesClient — auth, API calls, logging
│   ├── orders.py            # OrderManager — builds params, dispatches, cleans response
│   ├── validators.py        # Input validation with clear error messages
│   ├── logging_config.py    # Rotating file + console logger
│   └── cli.py               # argparse CLI — balance / price / order subcommands
├── logs/                    # Auto-created; rotating log file written here
│   └── trading_bot.log
├── app.py                   # Streamlit web UI — reuses bot/ code, no duplicate logic
├── .env.example             # Credential template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Unzip / clone the project

```bash
unzip trading_bot.zip        # or: git clone <repo-url>
cd trading_bot
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get Binance Futures Testnet API keys

1. Go to **[https://testnet.binancefuture.com](https://testnet.binancefuture.com)**
2. Log in — a GitHub account is sufficient
3. Click **API Key** in the top navigation bar
4. Copy your **API Key** and **Secret Key**

### 5. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
BINANCE_API_KEY=paste_your_key_here
BINANCE_API_SECRET=paste_your_secret_here
```

> `.env` is listed in `.gitignore` — your keys will never be committed.

---

## CLI Usage

All commands are run from inside the `trading_bot/` directory.

### Check account balance

```bash
python -m bot.cli balance
```

### Check live mark price

```bash
python -m bot.cli price --symbol BTCUSDT
```

### Place a MARKET order

```bash
python -m bot.cli order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Place a LIMIT order

```bash
python -m bot.cli order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 120000
```

### Place a STOP_MARKET order

```bash
python -m bot.cli order --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 110000
```

### All order flags

| Flag           | Required              | Description                                     |
|----------------|-----------------------|-------------------------------------------------|
| `--symbol`     | Always                | Trading pair, e.g. `BTCUSDT`, `ETHUSDT`        |
| `--side`       | Always                | `BUY` or `SELL`                                 |
| `--type`       | Always                | `MARKET`, `LIMIT`, or `STOP_MARKET`            |
| `--quantity`   | Always                | Order size in base asset (must be > 0)          |
| `--price`      | For `LIMIT`           | Limit price in USDT (must be > 0)               |
| `--stop-price` | For `STOP_MARKET`     | Stop trigger price in USDT (must be > 0)        |

---

## Streamlit UI

Launch the browser-based trading interface:

```bash
streamlit run app.py
```

Then open the URL shown in your terminal (usually `http://localhost:8501`).

**UI features:**
- Symbol, side, order type, and quantity inputs
- Price input (shown only for LIMIT orders)
- Stop price input (shown only for STOP_MARKET orders)
- Order request summary before submission
- Order response panel showing orderId, status, executedQty, avgPrice
- Sidebar with live account balances and mark price lookup
- Success / failure messages for every action

The UI reuses `bot.client`, `bot.orders`, and `bot.validators` — no order logic is duplicated.

---

## Sample CLI Output

### `balance`
```
╭───────────────────────────────────────────────────╮
│                  Account Balances                  │
├──────────┬────────────────┬─────────────────────── ┤
│ Asset    │ Wallet Balance │ Available Balance       │
├──────────┼────────────────┼─────────────────────── ┤
│ USDT     │ 9952.1000      │ 9952.1000               │
╰──────────┴────────────────┴───────────────────────╯
```

### `order` (MARKET BUY)
```
╭──────────────────────────╮
│       Order Request      │
│  Symbol    │  BTCUSDT    │
│  Side      │  BUY        │
│  Type      │  MARKET     │
│  Quantity  │  0.001      │
╰──────────────────────────╯
╭──────────────────────────────────────────╮
│              Order Response              │
│  Order ID       │  4149616518            │
│  Symbol         │  BTCUSDT               │
│  Side           │  BUY                   │
│  Type           │  MARKET                │
│  Status         │  FILLED                │
│  Executed Qty   │  0.001                 │
│  Avg Price      │  67432.50              │
╰──────────────────────────────────────────╯
╭──────────────────────────────────────────╮
│  ✔  Order submitted successfully!        │
╰──────────────────────────────────────────╯
```

### Validation error
```
╭──────────────────────────────────────────────────────────────╮
│  ✘  Validation error: --price is required for LIMIT orders.  │
╰──────────────────────────────────────────────────────────────╯
```

---

## Logging

Every run appends to **`logs/trading_bot.log`** (rotating, max 5 MB, 3 backups).

| Event                   | Level   | Example                                              |
|-------------------------|---------|------------------------------------------------------|
| API request sent        | INFO    | `API REQUEST | futures_create_order | params={…}`    |
| API response received   | INFO    | `API RESPONSE | futures_create_order | response={…}` |
| Validation failure      | WARNING | `Validation error: --quantity must be > 0`           |
| Binance API error       | ERROR   | `BinanceAPIException | code=-1121 | msg=Invalid symbol` |
| Network error           | ERROR   | `BinanceRequestException | msg=…`                    |
| Unexpected exception    | ERROR   | Full traceback                                       |

Both CLI and Streamlit UI write to the same log file.

---

## Error Handling

| Scenario                  | Behaviour                                               |
|---------------------------|---------------------------------------------------------|
| Missing `.env` keys       | Clear error at startup in both CLI and UI, exits/stops  |
| Invalid CLI flags         | Validation error panel printed, process exits           |
| Invalid UI inputs         | `st.error()` shown inline, order not placed             |
| Binance API error         | Error code + message shown and logged                   |
| Network / timeout error   | Message shown and logged                                |
| Unexpected exception      | Full traceback in log, brief message on screen          |

---

## Assumptions

- Targets the **testnet only** — `https://testnet.binancefuture.com`. Do not use real mainnet keys.
- Testnet balances are simulated — no real funds are at risk.
- python-binance >= 1.0.36: conditional order types (STOP_MARKET etc.) are routed directly to `/fapi/v1/order` to bypass the library's algo-endpoint routing which is not available on testnet.
- Minimum order quantity and price precision are enforced by the exchange. Adjust `--quantity` and `--price` to match the symbol's step size (e.g. 0.001 BTC for BTCUSDT) if you receive a filter error.

---

## Submission Checklist

- [x] Python 3.10+ compatible
- [x] `bot/client.py` — `BinanceFuturesClient` with testnet base URL
- [x] `bot/orders.py` — `OrderManager` with clean response output
- [x] `bot/validators.py` — full input validation with clear error messages
- [x] `bot/logging_config.py` — rotating file handler (`logs/trading_bot.log`)
- [x] `bot/cli.py` — `argparse` CLI with `balance`, `price`, `order` subcommands
- [x] `app.py` — Streamlit UI reusing bot/ code
- [x] MARKET order support
- [x] LIMIT order support
- [x] STOP_MARKET order support (bonus)
- [x] BUY and SELL sides
- [x] `requirements.txt` (python-binance, python-dotenv, rich, streamlit)
- [x] `.env.example` (no real keys)
- [x] `.gitignore`
- [x] `README.md` with full setup, CLI, and Streamlit run instructions
- [x] Rich tables/panels for CLI output
- [x] Logging of all requests, responses, and errors
