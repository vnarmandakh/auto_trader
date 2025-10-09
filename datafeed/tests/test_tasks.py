from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from markets.models import Symbol
from datafeed.models import TickerSnapshot
from datafeed import tasks


class PollAllSymbolsTests(TestCase):
    def setUp(self) -> None:
        self.symbol = Symbol.objects.create(
            name="BTCUSDT",
            base="BTC",
            quote="USDT",
            binance_symbol="BTCUSDT",
            trademn_symbol="BTCUSDT",
        )

    @mock.patch("datafeed.tasks.async_to_sync")
    @mock.patch("datafeed.tasks.get_channel_layer")
    @mock.patch("datafeed.tasks._trademn")
    @mock.patch("datafeed.tasks._binance")
    def test_creates_snapshot_when_prices_change(
        self, mock_binance, mock_trademn, mock_channel, mock_async
    ):
        mock_binance.return_value = (100.0, 101.0)
        mock_trademn.return_value = (99.0, 100.5)
        mock_channel.return_value = mock.Mock()

        tasks.poll_all_symbols.run()

        self.assertEqual(TickerSnapshot.objects.count(), 1)
        snapshot = TickerSnapshot.objects.first()
        self.assertEqual(snapshot.bi_bid, 100.0)
        mock_async.assert_called()

    @mock.patch("datafeed.tasks.async_to_sync")
    @mock.patch("datafeed.tasks.get_channel_layer")
    @mock.patch("datafeed.tasks._trademn")
    @mock.patch("datafeed.tasks._binance")
    def test_skips_duplicate_prices(
        self, mock_binance, mock_trademn, mock_channel, mock_async
    ):
        mock_channel.return_value = mock.Mock()
        mock_binance.return_value = (100.0, 101.0)
        mock_trademn.return_value = (99.0, 100.5)
        TickerSnapshot.objects.create(
            symbol=self.symbol,
            bi_bid=100.0,
            bi_ask=101.0,
            tr_bid=99.0,
            tr_ask=100.5,
        )

        tasks.poll_all_symbols.run()

        self.assertEqual(TickerSnapshot.objects.count(), 1)
        mock_async.assert_not_called()

    @mock.patch("datafeed.tasks.async_to_sync")
    @mock.patch("datafeed.tasks.get_channel_layer")
    @mock.patch("datafeed.tasks._trademn")
    @mock.patch("datafeed.tasks._binance")
    def test_handles_polling_exceptions_per_symbol(
        self, mock_binance, mock_trademn, mock_channel, mock_async
    ):
        other_symbol = Symbol.objects.create(
            name="ETHUSDT",
            base="ETH",
            quote="USDT",
            binance_symbol="ETHUSDT",
            trademn_symbol="ETHUSDT",
        )

        def _binance_side_effect(symbol, timeout):
            if symbol == "BTCUSDT":
                raise RuntimeError("feed down")
            return (10.0, 11.0)

        mock_channel.return_value = mock.Mock()
        mock_binance.side_effect = _binance_side_effect
        mock_trademn.return_value = (9.0, 11.0)

        tasks.poll_all_symbols.run()

        self.assertEqual(TickerSnapshot.objects.count(), 1)
        snapshot = TickerSnapshot.objects.get(symbol=other_symbol)
        self.assertEqual(snapshot.bi_bid, 10.0)


class PruneTimeseriesTests(TestCase):
    def setUp(self) -> None:
        self.symbol = Symbol.objects.create(
            name="LTCUSDT",
            base="LTC",
            quote="USDT",
            binance_symbol="LTCUSDT",
            trademn_symbol="LTCUSDT",
        )

    @mock.patch("datafeed.tasks.logger")
    def test_prunes_records_older_than_retention(self, mock_logger):
        old_ts = timezone.now() - timedelta(days=30)
        recent_ts = timezone.now() - timedelta(hours=1)
        TickerSnapshot.objects.bulk_create(
            [
                TickerSnapshot(
                    symbol=self.symbol,
                    ts=old_ts,
                    bi_bid=1,
                    bi_ask=2,
                    tr_bid=1,
                    tr_ask=2,
                ),
                TickerSnapshot(
                    symbol=self.symbol,
                    ts=recent_ts,
                    bi_bid=3,
                    bi_ask=4,
                    tr_bid=3,
                    tr_ask=4,
                ),
            ]
        )

        tasks.prune_timeseries.run()

        remaining = list(TickerSnapshot.objects.values_list("ts", flat=True))
        self.assertEqual(len(remaining), 1)
        self.assertGreater(remaining[0], old_ts)
        mock_logger.info.assert_called()
