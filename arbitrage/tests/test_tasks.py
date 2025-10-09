from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from arbitrage import tasks
from arbitrage.models import ArbitrageOpportunity
from datafeed.models import TickerSnapshot
from markets.models import Symbol


class ScanSpreadsTests(TestCase):
    def setUp(self) -> None:
        self.symbol = Symbol.objects.create(
            name="BTCUSDT",
            base="BTC",
            quote="USDT",
            binance_symbol="BTCUSDT",
            trademn_symbol="BTCUSDT",
        )
        TickerSnapshot.objects.create(
            symbol=self.symbol,
            bi_bid=105.0,
            bi_ask=105.5,
            tr_bid=100.5,
            tr_ask=100.0,
        )

    @mock.patch("arbitrage.tasks.async_to_sync")
    @mock.patch("arbitrage.tasks.get_channel_layer")
    def test_emits_opportunities_above_threshold(self, mock_channel, mock_async):
        mock_channel.return_value = mock.Mock()

        tasks.scan_spreads.run()

        self.assertGreater(ArbitrageOpportunity.objects.count(), 0)
        mock_async.assert_called()

    @mock.patch("arbitrage.tasks.async_to_sync")
    @mock.patch("arbitrage.tasks.get_channel_layer")
    def test_skips_stale_snapshots(self, mock_channel, mock_async):
        mock_channel.return_value = mock.Mock()
        TickerSnapshot.objects.all().update(
            ts=timezone.now() - timedelta(hours=2)
        )

        tasks.scan_spreads.run()

        self.assertEqual(ArbitrageOpportunity.objects.count(), 0)
        mock_async.assert_not_called()

    @mock.patch("arbitrage.tasks.async_to_sync")
    @mock.patch("arbitrage.tasks.get_channel_layer")
    def test_deduplicates_identical_spreads(self, mock_channel, mock_async):
        mock_channel.return_value = mock.Mock()

        tasks.scan_spreads.run()
        first_count = ArbitrageOpportunity.objects.count()

        tasks.scan_spreads.run()

        self.assertEqual(ArbitrageOpportunity.objects.count(), first_count)
