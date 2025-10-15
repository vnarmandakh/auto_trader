# ArbMon (Arbitrage Monitor)

ArbMon is a Django-based dashboard that polls spot market order books, derives
cross-exchange arbitrage spreads, and broadcasts actionable opportunities over
WebSockets and REST APIs.

This guide walks through environment configuration, local development, task
orchestration, and operational best practices.

## Requirements

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node/npm (optional) for front-end asset workflows

## Configuration

Populate the required environment variables before running the application.
ArbMon uses [`python-dotenv`](https://pypi.org/project/python-dotenv/) during
development but **will fail fast** if critical secrets are absent.

| Variable | Description |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret key (generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`). |
| `DJANGO_DEBUG` | Set to `1` for development debugging. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames when `DEBUG=0`. |
| `REDIS_URL` | Connection string for Redis (used by Celery and Channels). |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL configuration. |
| `BINANCE_BOOK_TICKER_URL` | URL template for Binance best bid/ask endpoint. Must include `{symbol}` placeholder. |
| `TRADEMN_BOOK_TICKER_URL` or `TRADEMN_ORDERBOOK_URL` | Either a direct ticker endpoint or level-2 order book endpoint for TradeMN. |
| `POLL_INTERVAL_SEC`, `SCAN_INTERVAL_SEC` | Celery beat cadence (seconds) for data polling and arbitrage scanning. |
| `DATA_RETENTION_DAYS` | Rolling window of historical rows to keep. |
| `DATA_RETENTION_PRUNE_INTERVAL` | Frequency (seconds) of the pruning task. |
| `WEBSOCKET_MAX_CONNECTIONS_PER_USER`, `WEBSOCKET_CONNECTION_WINDOW_SEC` | Authenticated WebSocket rate-limiting knobs. |
| `DJANGO_USE_SQLITE` | Set to `1` during local development/tests to use SQLite instead of PostgreSQL. |
| `BINANCE_API_KEY`, `BINANCE_API_SECRET` | Credentials for authenticated Binance trading endpoints. |
| `TRADEMN_API_KEY`, `TRADEMN_API_SECRET` | Credentials for authenticated TradeMN trading endpoints. |
| `ARBITRAGE_DEPOSIT_ADDRESSES` | JSON mapping of deposit addresses per exchange and network (e.g. `{ "binance": { "USDT:TRX": "T123" } }`). |
| `ARBITRAGE_EXECUTION_INTERVAL_SEC` | Cadence (seconds) for the automated execution task. |
| `ARBITRAGE_BRIDGE_NETWORK` | Network identifier for cross-exchange withdrawals (default `TRX`). |
| `ARBITRAGE_QUOTE_TRANSFER_FEE`, `ARBITRAGE_BASE_TRANSFER_FEE` | Estimated network withdrawal fees for quote/base assets. |
| `ARBITRAGE_MIN_QUANTITY`, `ARBITRAGE_SLIPPAGE_BUFFER` | Sizing and slippage assumptions for executed orders. |

Optional knobs allow fine tuning of API pagination (`API_PAGE_SIZE`), rate
limits (`API_USER_THROTTLE`, `API_ANON_THROTTLE`, `API_TRADES_THROTTLE`), and
exchange fee assumptions (`FEE_*`). See `arbmon/settings.py` for the complete
list.

## Local Development

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file (see `.env.example`) with development credentials. A
   sample configuration for local services is included below:

   ```dotenv
   DJANGO_SECRET_KEY=dev-secret
   DJANGO_DEBUG=1
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   REDIS_URL=redis://localhost:6379/0
   POSTGRES_DB=arbmon
   POSTGRES_USER=arbmon
   POSTGRES_PASSWORD=arbmon
   BINANCE_BOOK_TICKER_URL=https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}
   TRADEMN_ORDERBOOK_URL=https://api.example.com/orderbook?symbol={symbol}
   ```

4. Run migrations and seed the database with symbols:

   ```bash
   python manage.py migrate
   python manage.py loaddata markets/fixtures/symbols.json  # create your own fixture
   ```

5. Start services:

   ```bash
   python manage.py runserver
   celery -A arbmon worker -l info
   celery -A arbmon beat -l info
   ```

### Docker Compose

`docker-compose.yml` builds self-contained images without bind mounts so the
production image remains immutable. For iterative development, create an
override file (`docker-compose.override.yml`) that mounts the project root.

```yaml
services:
  web:
    volumes:
      - ./:/app
  worker:
    volumes:
      - ./:/app
  beat:
    volumes:
      - ./:/app
```

Bring the stack up with `docker compose up --build` once PostgreSQL and Redis
credentials are supplied through `.env`.

## Celery Tasks and Scheduling

- `datafeed.tasks.poll_all_symbols` polls exchanges with retries, backoff, and
  snapshot deduplication before broadcasting WebSocket updates.
- `arbitrage.tasks.scan_spreads` analyzes the latest ticker snapshots and
  emits WebSocket alerts only when net spreads exceed
  `ARBITRAGE_MIN_NET_SPREAD`.
- `trades.tasks.execute_arbitrage` turns high-confidence spreads into live
  trades, handling TradeMN↔Binance transfers over the configured Tron network
  and rebalancing quote assets for continuous 24/7 cycling.
- `datafeed.tasks.prune_timeseries` periodically deletes historical ticker,
  arbitrage, and trade rows older than `DATA_RETENTION_DAYS` to keep the
  database lean.

Celery beat schedules these tasks separately to avoid overlap. Adjust the
intervals through environment variables if feed latency changes.

## Testing

```bash
python manage.py test
```

The suite includes coverage for Celery task resiliency, arbitrage filtering,
and serializer validation. Add additional tests as new strategies or fee rules
are introduced.

## Monitoring & Logging

- Structured JSON-friendly logging is emitted to stdout for ingestion by log
  shippers.
- Feed polling, arbitrage scanning, and pruning tasks emit success/failure
  events with contextual metadata.
- Configure external monitoring (e.g., Prometheus, Sentry) around Redis and
  Celery queue health to detect feed outages quickly.

## Operations

- Use `python manage.py createsuperuser` to provision admin accounts and gate
  WebSocket access.
- Rotate `DJANGO_SECRET_KEY` and database credentials via your secret manager.
- Execute `python manage.py migrate` as part of your release pipeline before
  deploying new containers.
- Schedule periodic database backups and monitor table growth between pruning
  runs.

## Contributing

1. Fork and clone the repository.
2. Create a feature branch: `git checkout -b feature/my-improvement`.
3. Run `python manage.py test` before submitting pull requests.
4. Document environment or schema changes in this README.

Happy hacking!
