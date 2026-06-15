"""
Bokeh interactive chart module for stocktrade.
Generates candlestick + ADX chart with interactive tools (zoom, pan, crosshair, hover).
Uses json_item for embedding in Flask JSON responses.
"""

import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.layouts import column
from bokeh.models import (
    ColumnDataSource,
    CrosshairTool,
    HoverTool,
    Span,
    NumeralTickFormatter,
    Range1d,
    FixedTicker,
)

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
    "ref_line": "#555555",
    "legend_text": "#eae1d4",
}


def _make_base_figure(**kwargs):
    defaults = dict(
        background_fill_color=COLORS["bg"],
        border_fill_color=COLORS["bg"],
        outline_line_color=COLORS["border"],
        toolbar_location="above",
        toolbar_sticky=False,
        tools="pan,box_zoom,wheel_zoom,reset,save",
        active_scroll="wheel_zoom",
    )
    defaults.update(kwargs)
    p = figure(**defaults)
    p.xgrid.grid_line_color = COLORS["grid"]
    p.ygrid.grid_line_color = COLORS["grid"]
    p.xgrid.grid_line_alpha = 0.5
    p.ygrid.grid_line_alpha = 0.5
    p.axis.major_label_text_font_size = "10px"
    p.axis.major_label_text_color = COLORS["text"]
    p.axis.axis_line_color = COLORS["border"]
    p.axis.major_tick_line_color = COLORS["border"]
    p.axis.minor_tick_line_color = COLORS["border"]
    p.title.text_color = COLORS["text"]
    p.title.text_font_size = "14px"
    p.title.text_font_style = "bold"
    return p


def _candlestick_figure(p, df):
    up_mask = df["Close"] >= df["Open"]
    down_mask = ~up_mask

    df_up = df[up_mask]
    df_down = df[down_mask]

    if not df_up.empty:
        mid_up = (df_up["Open"] + df_up["Close"]) / 2
        height_up = (df_up["Close"] - df_up["Open"]).clip(lower=0.001)
        src_up = ColumnDataSource(data=dict(
            idx=df_up["idx"].values, high=df_up["High"].values,
            low=df_up["Low"].values, mid=mid_up.values, height=height_up.values,
        ))
        p.segment("idx", "high", "idx", "low", source=src_up, color=COLORS["up"], line_width=1)
        p.rect("idx", "mid", 0.7, "height", source=src_up, fill_color=COLORS["up"], line_color=COLORS["up"], line_width=0.5)

    if not df_down.empty:
        mid_down = (df_down["Open"] + df_down["Close"]) / 2
        height_down = (df_down["Open"] - df_down["Close"]).clip(lower=0.001)
        src_down = ColumnDataSource(data=dict(
            idx=df_down["idx"].values, high=df_down["High"].values,
            low=df_down["Low"].values, mid=mid_down.values, height=height_down.values,
        ))
        p.segment("idx", "high", "idx", "low", source=src_down, color=COLORS["down"], line_width=1)
        p.rect("idx", "mid", 0.7, "height", source=src_down, fill_color=COLORS["down"], line_color=COLORS["down"], line_width=0.5)
    return p


def _sl_line(p, df, sl_series):
    sl_data = pd.DataFrame({"idx": df["idx"].values, "sl": sl_series.values}).dropna()
    if not sl_data.empty:
        src_sl = ColumnDataSource(sl_data)
        sl_line = p.line("idx", "sl", source=src_sl, color=COLORS["sl"], line_width=2, line_dash="dashed", legend_label="Stop Loss (SL)")
        sl_line.level = "overlay"
    return p


def _adx_figure(p, df, adx_series, pdi_series, mdi_series):
    adx_data = pd.DataFrame({
        "idx": df["idx"].values, "adx": adx_series.values,
        "pdi": pdi_series.values, "mdi": mdi_series.values,
    }).dropna()
    if adx_data.empty:
        return p
    src = ColumnDataSource(adx_data)
    p.line("idx", "adx", source=src, color=COLORS["adx"], line_width=2, legend_label="ADX")
    p.line("idx", "pdi", source=src, color=COLORS["pdi"], line_width=1.5, line_dash="dashed", legend_label="+DI")
    p.line("idx", "mdi", source=src, color=COLORS["mdi"], line_width=1.5, line_dash="dashed", legend_label="-DI")
    for level, lw, alpha in [(25, 1, 0.7), (20, 0.8, 0.5)]:
        span = Span(location=level, dimension="width", line_color=COLORS["ref_line"],
                    line_width=lw, line_dash="dotted", line_alpha=alpha)
        p.renderers.append(span)
    p.y_range = Range1d(0, 60)
    p.yaxis.ticker = [0, 10, 20, 25, 30, 40, 50, 60]
    return p


def _setup_xaxis(p, df, show_labels=True):
    step = max(1, len(df) // 25)
    tick_indices = list(range(0, len(df), step))
    if len(df) > 0 and tick_indices[-1] != len(df) - 1:
        tick_indices.append(len(df) - 1)
    tick_labels = {}
    for i in tick_indices:
        if i < len(df):
            tick_labels[i] = df.index[i].strftime("%Y-%m-%d") if isinstance(df.index, pd.DatetimeIndex) else str(df.index[i])
    p.xaxis.ticker = FixedTicker(ticks=tick_indices)
    p.xaxis.major_label_overrides = tick_labels
    p.xaxis.major_label_orientation = 0.785
    p.xaxis.visible = show_labels


def _main_hover(p, df):
    src = ColumnDataSource(data=dict(
        idx=df["idx"].values,
        date_str=[d.strftime("%Y-%m-%d") for d in df.index],
        Open=df["Open"].values, High=df["High"].values,
        Low=df["Low"].values, Close=df["Close"].values,
        Volume=df["Volume"].values if "Volume" in df.columns else np.zeros(len(df)),
    ))
    circ = p.scatter("idx", "Close", source=src, size=1, color=COLORS["bg"], alpha=0.0)
    circ.level = "underlay"
    hover = HoverTool(
        renderers=[circ],
        tooltips=[
            ("Date", "@date_str"),
            ("Open", "$@{Open}{0,0.00}"),
            ("High", "$@{High}{0,0.00}"),
            ("Low", "$@{Low}{0,0.00}"),
            ("Close", "$@{Close}{0,0.00}"),
            ("Volume", "@{Volume}{0,0}"),
        ],
    )
    p.add_tools(hover)
    return p


def generate_chart(ticker, df_plot, sl_series, adx_series, pdi_series, mdi_series):
    """
    Generate a full interactive Bokeh chart layout.

    Returns
    -------
    dict
        {"script": str, "div": str} — Bokeh components for HTML embedding.
    """
    df = df_plot.copy()
    df["idx"] = np.arange(len(df))

    p1 = _make_base_figure(
        height=420,
        sizing_mode="stretch_width",
        y_axis_location="right",
        title=f"Analisis Saham {ticker}",
        x_range=Range1d(-0.5, len(df) - 0.5),
    )
    p1.yaxis.formatter = NumeralTickFormatter(format="$0,0.00")
    p1.yaxis.axis_label = "Price"
    p1.yaxis.axis_label_text_color = COLORS["text"]

    _candlestick_figure(p1, df)
    _sl_line(p1, df, sl_series)
    _setup_xaxis(p1, df, show_labels=False)
    _main_hover(p1, df)
    p1.add_tools(CrosshairTool(line_color="#666666", line_alpha=0.4))

    p2 = _make_base_figure(height=160, sizing_mode="stretch_width", y_axis_location="right", x_range=p1.x_range)
    p2.yaxis.formatter = NumeralTickFormatter(format="0.0")
    p2.yaxis.axis_label = "ADX"
    p2.yaxis.axis_label_text_color = COLORS["text"]
    p2.xaxis.axis_label = ""

    _adx_figure(p2, df, adx_series, pdi_series, mdi_series)
    _setup_xaxis(p2, df, show_labels=True)

    hover_adx = HoverTool(
        tooltips=[("Date", "$x{%Y-%m-%d}"), ("Value", "$y{0.0}")],
        formatters={"$x": "datetime"},
        mode="mouse",
    )
    p2.add_tools(hover_adx)

    for fig in [p1, p2]:
        fig.legend.location = "top_left"
        fig.legend.label_text_color = COLORS["legend_text"]
        fig.legend.label_text_font_size = "10px"
        fig.legend.background_fill_color = COLORS["bg"]
        fig.legend.background_fill_alpha = 0.8
        fig.legend.border_line_color = COLORS["border"]
        fig.legend.border_line_alpha = 0.5
        fig.legend.click_policy = "hide"

    layout = column(p1, p2, sizing_mode="stretch_width", spacing=0)
    script, div = components(layout)
    # Strip <script> tags — we inject via JS dynamically
    script_body = script.replace("<script>", "").replace("</script>", "").strip()
    return {"script": script_body, "div": div}
