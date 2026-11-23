"""
SWING_PLUS indicator for USSwing (test example).

Gives the highest high, the lowest low, or the high-to-low range
over the last N candles. "Previous" skips the candle that is still forming.
"""
from usswing import Input, Number, USSwingIndicator


class SwingPlus(USSwingIndicator):
    """Highest high, lowest low, or high-to-low range over the last N candles."""

    indicator_name = "SWING_PLUS"
    description = "Swing high, swing low or swing range over the last N candles"
    version = "1.0"
    output_type = "value"

    parameters = [
        Input("Symbol Type", options=["Spot", "RSP"], default="Spot"),
        Number("Candles", default=20, minimum=1, maximum=500, whole_number=True),
        Input("Price Swing", options=["High", "Low", "Range"], default="High"),
        Input("Window", options=["Previous", "Current"], default="Previous"),
        Input("Timeframe", options=["3m", "15m", "30m", "1d"], default="3m"),
    ]

    def calculate(self):
        candles = self.candles(
            symbol_type=self.parameter("Symbol Type"),
            timeframe=self.parameter("Timeframe"),
        )
        count = self.parameter("Candles")
        price_swing = self.parameter("Price Swing")
        skip_forming_candle = self.parameter("Window") == "Previous"

        highs = candles["high"]
        lows = candles["low"]
        if skip_forming_candle:
            highs = highs.shift(1)
            lows = lows.shift(1)

        swing_high = highs.rolling(count).max()
        swing_low = lows.rolling(count).min()

        self.debug_value("Swing high", swing_high)
        self.debug_value("Swing low", swing_low)

        if price_swing == "High":
            return swing_high
        if price_swing == "Low":
            return swing_low
        return swing_high - swing_low
