"""Handlers for the BiGGr front page and statistics page."""

from biggr_models.handlers import utils
from biggr_models.queries.summary_queries import (
    get_summary_counts,
    get_summary_history,
)


def build_model_chart(points, width=720, height=320, pad_left=64, pad=32):
    """Turn [{"date": ..., "count": ...}, ...] into SVG geometry for one line.

    Returns None when there are fewer than two points, so the template can show
    the cold-start message instead of an axis with nothing on it.

    The y axis starts at zero: scaling to the minimum would turn a small
    absolute change into a dramatic climb, which is the kind of misleading
    chart this page exists to avoid.
    """
    if not points or len(points) < 2:
        return None

    counts = [p["count"] for p in points]
    dates = [p["date"] for p in points]

    plot_w = width - pad_left - pad
    plot_h = height - 2 * pad

    top = _nice_ceiling(max(counts))
    span = (dates[-1] - dates[0]).total_seconds() or 1

    def x_of(date):
        return pad_left + plot_w * (date - dates[0]).total_seconds() / span

    def y_of(count):
        return pad + plot_h * (1 - count / top)

    coords = [(x_of(d), y_of(c)) for d, c in zip(dates, counts)]

    return {
        "width": width,
        "height": height,
        "plot_left": pad_left,
        "plot_right": pad_left + plot_w,
        "plot_top": pad,
        "plot_bottom": pad + plot_h,
        "polyline": " ".join(f"{x:.1f},{y:.1f}" for x, y in coords),
        # A filled area under the line reads as "accumulated total" far more
        # clearly than a bare stroke.
        "area": "{} {} {}".format(
            f"{coords[0][0]:.1f},{pad + plot_h:.1f}",
            " ".join(f"{x:.1f},{y:.1f}" for x, y in coords),
            f"{coords[-1][0]:.1f},{pad + plot_h:.1f}",
        ),
        "dots": [
            {"x": x, "y": y, "count": c, "date": d}
            for (x, y), c, d in zip(coords, counts, dates)
        ],
        "y_ticks": [
            {"value": v, "y": y_of(v)} for v in _tick_values(top)
        ],
        "x_ticks": [
            {"label": dates[0].strftime("%b %Y"), "x": x_of(dates[0])},
            {"label": dates[-1].strftime("%b %Y"), "x": x_of(dates[-1])},
        ],
        "first": {"count": counts[0], "date": dates[0]},
        "last": {"count": counts[-1], "date": dates[-1]},
        "added": counts[-1] - counts[0],
    }


def _nice_ceiling(value, divisions=4):
    """Round up to an axis maximum that divides into readable ticks.

    Rounds the tick *step* rather than the maximum, so the ticks land on round
    numbers while the top stays close to the data: 4881 gives 1250-steps and a
    top of 5000, not 8000, which would leave the line hugging the floor.
    """
    if value <= 0:
        return divisions
    # Try every round step across the plausible magnitudes and keep the
    # smallest top that still covers the data, so the line fills the plot.
    candidates = []
    magnitude = 1
    while magnitude <= max(value, 1):
        for multiple in (1, 1.25, 2, 2.5, 5):
            step = magnitude * multiple
            top = step * divisions
            # Keep only steps that give whole-number tick labels.
            if top >= value and float(step).is_integer():
                candidates.append(int(top))
        magnitude *= 10
    return min(candidates) if candidates else int(value)


def _tick_values(top, count=4):
    """Evenly spaced y-axis values from 0 to top, inclusive."""
    step = top / count
    return [int(round(step * i)) for i in range(count + 1)]


class HomeHandler(utils.BaseHandler):
    """Front page, with precomputed entity counts on the cards."""

    template = utils.env.get_template("index.html")

    def get(self):
        counts = utils.do_safe_query(get_summary_counts)
        # Wrap in a dict so the result stays truthy even when no counts are
        # available; return_result skips the context entirely on a falsy result.
        self.return_result({"counts": counts})


class StatisticsHandler(utils.BaseHandler):
    """Database growth over time."""

    template = utils.env.get_template("statistics.html")

    def get(self):
        history = utils.do_safe_query(get_summary_history)
        model_points = history.get("models", [])
        self.return_result(
            {
                "history": history,
                "model_points": model_points,
                "chart": build_model_chart(model_points),
                "breadcrumbs": [("Home", "/"), ("Statistics", "/statistics")],
            }
        )
