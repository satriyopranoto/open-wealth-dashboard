"""
Bokeh interactive chart module for stocktrade.
Generates candlestick + ADX chart with interactive tools (zoom, pan, crosshair, hover).
Uses json_item for embedding in Flask JSON responses.
"""

import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.embed import json_item
from bokeh.layouts import column
from bokeh.models import (
    ColumnDataSource,
    CrosshairTool,
    HoverTool,
    Span,
    NumeralTickFormatter,
    DatetimeTickFormatter,
    Range1d,
    LinearAxis,
    Legend,
    LegendItem,
)
from bokeh.palettes import Category10


# ── Color scheme (dark theme, matching stocktrade UI) ──────────────
COLORS = {
    "bg": "#1a1612",
    "border": "#2d2a21",
    "text": "#eae1d4",
    "grid": "#2d2a21",
    "up": "#4ade80",
    "down": "#f87171",
    "wick": "#99907c",
    "sl": "#fb923c",
    "adx": "#a78bfa",
    "pdi": "#4ade80",
    "mdi": "#f87171",
    "sma200": "#fbbf24",
    "ref_line": "#555555",
    "legend_text": "#eae1d4",
}


def _make_base_figure(**kwargs):
    """Create a base Bokeh figure with shared dark theme styling."""
    defaults = dict(
        background_fill_color=COLORS["bg"],
        border_fill_color=COLORS["bg"],
        outline_line_color=COLORS["border"],
        toolbar_location="above",
        toolbar_sticky=False,
        tools="pan,box_zoom,wheel_zoom,reset,save",
        active_scroll="wheel_zoom",
        sizing_mode="stretch_width",
    )
    defaults.update(kwargs)
    p = figure(**defaults)
    # Grid styling
    p.xgrid.grid_line_color = COLORS["grid"]
    p.ygrid.grid_line_color = COLORS["grid"]
    p.xgrid.grid_line_alpha = 0.5
    p.ygrid.grid_line_alpha = 0.5
    # Axis styling
    p.axis.axis_label_text_color = COLORS["text"]
    p.axis.axis_label_text_font_size = "10px"
    p.axis.major_label_text_font_size = "10px"
    p.axis.major_label_text_color = COLORS["text"]
    p.axis.axis_line_color = COLORS["border"]
    p.axis.major_tick_line_color = COLORS["border"]
    p.axis.minor_tick_line_color = COLORS["border"]
    # Title
    p.title.text_color = COLORS["text"]
    p.title.text_font_size = "14px"
    p.title.text_font_style = "bold"
    return p


def _candlestick_figure(p, df, sl_series):
    """
    Draw candlestick bars, SL line, and SMA 200 line on figure *p*.
    df should have a numeric 'idx' column for x-axis positioning.
    """
    # Separate up/down bars
    up_mask = df["Close"] >= df["Open"]
    down_mask = ~up_mask

    df_up = df[up_mask]
    df_down = df[down_mask]

    mid_up = (df_up["Open"] + df_up["Close"]) / 2
    height_up = (df_up["Close"] - df_up["Open"]).clip(lower=0.001)  # avoid zero-height

    mid_down = (df_down["Open"] + df_down["Close"]) / 2
    height_down = (df_down["Open"] - df_down["Close"]).clip(lower=0.001)

    src_up = ColumnDataSource(
        data=dict(
            idx=df_up["idx"].values,
            high=df_up["High"].values,
            low=df_up["Low"].values,
            mid=mid_up.values,
            height=height_up.values,
        )
    )
    src_down = ColumnDataSource(
        data=dict(
            idx=df_down["idx"].values,
            high=df_down["High"].values,
            low=df_down["Low"].values,
            mid=mid_down.values,
            height=height_down.values,
        )
    )

    # High-low wicks
    p.segment(
        "idx", "high", "idx", "low",
        source=src_up,
        color=COLORS["up"],
        line_width=1,
    )
    p.segment(
        "idx", "high", "idx", "low",
        source=src_down,
        color=COLORS["down"],
        line_width=1,
    )

    # Body rectangles
    p.rect(
        "idx", "mid", 0.7, "height",
        source=src_up,
        fill_color=COLORS["up"],
        line_color=COLORS["up"],
        line_width=0.5,
    )
    p.rect(
        "idx", "mid", 0.7, "height",
        source=src_down,
        fill_color=COLORS["down"],
        line_color=COLORS["down"],
        line_width=0.5,
    )

    # Stop Loss line
    sl_data = pd.DataFrame({"idx": df["idx"].values, "sl": sl_series.values})
    sl_data = sl_data.dropna()
    if not sl_data.empty:
        src_sl = ColumnDataSource(sl_data)
        sl_line = p.line(
            "idx", "sl",
            source=src_sl,
            color=COLORS["sl"],
            line_width=2,
            line_dash="dashed",
            legend_label="Stop Loss (SL)",
        )
        sl_line.level = "overlay"

    # SMA 200 line
    sma200_values = df["Close"].rolling(200).mean()
    sma200_data = pd.DataFrame({"idx": df["idx"].values, "sma200": sma200_values.values})
    sma200_data = sma200_data.dropna()
    if not sma200_data.empty:
        src_sma200 = ColumnDataSource(sma200_data)
        sma200_line = p.line(
            "idx", "sma200",
            source=src_sma200,
            color=COLORS["sma200"],
            line_width=2,
            legend_label="SMA 200",
        )
        sma200_line.level = "overlay"

    return p


def _adx_figure(p, df, adx_series, pdi_series, mdi_series):
    """Draw ADX, +DI, -DI indicators on figure *p*."""
    adx_data = pd.DataFrame(
        {
            "idx": df["idx"].values,
            "adx": adx_series.values,
            "pdi": pdi_series.values,
            "mdi": mdi_series.values,
        }
    ).dropna()

    if adx_data.empty:
        return p

    src = ColumnDataSource(adx_data)

    p.line("idx", "adx", source=src, color=COLORS["adx"], line_width=2, legend_label="ADX")
    p.line("idx", "pdi", source=src, color=COLORS["pdi"], line_width=1.5, line_dash="dashed", legend_label="+DI")
    p.line("idx", "mdi", source=src, color=COLORS["mdi"], line_width=1.5, line_dash="dashed", legend_label="-DI")

    # Reference lines
    for level in [25, 20]:
        span = Span(
            location=level,
            dimension="width",
            line_color=COLORS["ref_line"],
            line_width=1 if level == 25 else 0.8,
            line_dash="dotted",
            line_alpha=0.7 if level == 25 else 0.5,
        )
        p.renderers.append(span)

    p.y_range = Range1d(0, 60)
    p.yaxis.ticker = [0, 10, 20, 25, 30, 40, 50, 60]

    return p


def _add_hover(p, tooltips, formatters=None):
    """Add HoverTool to figure."""
    hover = HoverTool(
        tooltips=tooltips,
        formatters=formatters or {},
        mode="mouse",
        point_policy="snap_to_data",
        toggleable=False,
    )
    p.add_tools(hover)
    return p


def _format_xaxis_date(p, df):
    """Format x-axis (integer index) to show date labels."""
    # Label every ~20 bars
    step = max(1, len(df) // 20)
    tick_indices = list(range(0, len(df), step))
    if tick_indices[-1] != len(df) - 1:
        tick_indices.append(len(df) - 1)

    # Better: use FixedTicker
    from bokeh.models import FixedTicker

    p.xaxis.ticker = FixedTicker(ticks=tick_indices)
    p.xaxis.major_label_overrides = {
        i: str(df.index[i].strftime("%Y-%m-%d"))
        if isinstance(df.index, pd.DatetimeIndex)
        else str(df.index[i])
        for i in tick_indices
    }
    p.xaxis.major_label_orientation = 0.785  # 45 degrees in radians
    # Only show min/border border for bottom subplot
    p.xaxis.visible = False  # hide for top, show for bottom

    # Fix x-axis range with padding
    p.x_range = Range1d(-0.5, len(df) - 0.5)


def generate_chart(ticker, df_plot, sl_series, upper_bb, middle_bb, lower_bb, adx_series, pdi_series, mdi_series):
    """
    Generate a full interactive Bokeh chart layout.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.
    df_plot : pd.DataFrame
        Must contain columns: Open, High, Low, Close (with DatetimeIndex).
    sl_series : pd.Series
        Stop Loss values (aligned with df_plot index).
    upper_bb, middle_bb, lower_bb : pd.Series
        Bollinger Bands values (aligned with df_plot index).
    adx_series, pdi_series, mdi_series : pd.Series
        ADX indicator values.

    Returns
    -------
    dict
        JSON-like dict for `Bokeh.embed.embed_item()` (via json_item).
    """
    df = df_plot.copy()
    df["idx"] = np.arange(len(df))

    # ── Main price figure ─────────────────────────────────────
    p1 = _make_base_figure(
        height=400,
        title=f"Analisis Saham {ticker}",
        x_range=Range1d(-0.5, len(df) - 0.5),
    )
    p1.yaxis.formatter = NumeralTickFormatter(format="$0,0.00")
    p1.yaxis.axis_label_text_color = COLORS["text"]

    _candlestick_figure(p1, df, sl_series)
    _format_xaxis_date(p1, df)

    # ── Bollinger Bands lines ─────────────────────────────────
    bb_source = ColumnDataSource(data=dict(
        idx=df["idx"].values,
        upper=upper_bb.values if hasattr(upper_bb, "values") else upper_bb,
        middle=middle_bb.values if hasattr(middle_bb, "values") else middle_bb,
        lower=lower_bb.values if hasattr(lower_bb, "values") else lower_bb,
    ))

    # Only plot BB bands if data is valid (not all NaN)
    if not np.all(np.isnan(bb_source.data["upper"])):
        # Upper band
        p1.line("idx", "upper", source=bb_source,
                line_color="#9b59b6", line_width=1.0, line_alpha=0.6,
                legend_label="Upper BB")
        # Middle band
        p1.line("idx", "middle", source=bb_source,
                line_color="#e67e22", line_width=1.2, line_alpha=0.7,
                legend_label="Middle BB")
        # Lower band
        p1.line("idx", "lower", source=bb_source,
                line_color="#9b59b6", line_width=1.0, line_alpha=0.6,
                legend_label="Lower BB")

    # Crosshair on main chart
    p1.add_tools(CrosshairTool(line_color="#666666", line_alpha=0.4))

    # Hover tooltip for candlesticks
    hover_tooltips = [
        ("Date", "@date_str"),
        ("Open", "$@{Open}{0,0.00}"),
        ("High", "$@{High}{0,0.00}"),
        ("Low", "$@{Low}{0,0.00}"),
        ("Close", "$@{Close}{0,0.00}"),
        ("Volume", "@{Volume}{0,0}"),
    ]

    # Add date string to source
    date_strs = [d.strftime("%Y-%m-%d") for d in df.index]
    src_combined = ColumnDataSource(
        data=dict(
            idx=df["idx"].values,
            Open=df["Open"].values,
            High=df["High"].values,
            Low=df["Low"].values,
            Close=df["Close"].values,
            Volume=df["Volume"].values if "Volume" in df.columns else np.zeros(len(df)),
            date_str=date_strs,
        )
    )

    # Add invisible circle glyph to enable hover on the main figure
    # (hover works on any glyph, so we add a transparent scatter)
    circ = p1.circle(
        "idx", "Close",
        source=src_combined,
        size=1,
        color=COLORS["bg"],
        alpha=0.0,
        hover_color=COLORS["bg"],
        hover_alpha=0.0,
        legend_label="",
    )
    circ.level = "underlay"

    hover = HoverTool(
        tooltips=hover_tooltips,
        renderers=[circ],
        toggleable=False,
    )
    p1.add_tools(hover)

    # ── ADX subplot ───────────────────────────────────────────
    p2 = _make_base_figure(
        height=160,
        x_range=p1.x_range,
        x_axis_location="below",
    )
    p2.yaxis.formatter = NumeralTickFormatter(format="0.0")
    p2.yaxis.axis_label = "ADX"
    p2.yaxis.axis_label_text_color = COLORS["text"]

    _adx_figure(p2, df, adx_series, pdi_series, mdi_series)
    _format_xaxis_date(p2, df)
    p2.xaxis.visible = True
    p2.xaxis.axis_label = ""
    p2.xaxis.major_label_orientation = 0.785

    # Hover for ADX
    hover_adx = HoverTool(
        tooltips=[
            ("Date", "$x{%Y-%m-%d}"),
            ("ADX", "$y{0.0}"),
        ],
        formatters={"$x": "datetime"},
        mode="mouse",
        toggleable=False,
    )
    p2.add_tools(hover_adx)

    # Legend styling
    for p in [p1, p2]:
        p.legend.location = "top_left"
        p.legend.label_text_color = COLORS["legend_text"]
        p.legend.label_text_font_size = "10px"
        p.legend.background_fill_color = COLORS["bg"]
        p.legend.background_fill_alpha = 0.8
        p.legend.border_line_color = COLORS["border"]
        p.legend.border_line_alpha = 0.5
        p.legend.click_policy = "hide"

    # ── Layout ────────────────────────────────────────────────
    layout = column(
        p1,
        p2,
        sizing_mode="stretch_width",
        spacing=0,
    )

    return json_item(layout, target="bokeh-chart")
