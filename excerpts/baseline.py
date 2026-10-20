# Excerpt from Salud (not the complete source).
"""Personal baseline: "what is normal for me" and how tonight compares.

Day D is the morning you wake up. The baseline for each signal comes from the
previous main-sleep nights (up to 14) with at least 4 h asleep: the median and the
usual range (10th to 90th percentile; with fewer than 7 nights, min to max).
With fewer than 3 nights nothing is compared: the system reports "calibrating".
"""
from datetime import datetime, timedelta

BASELINE_NIGHTS = 14
MIN_BASELINE = 3
MIN_ASLEEP_MIN = 240          # shorter nights do not count towards the baseline

# signal -> (label, unit, decimals)
SIGNALS = {
    "hr_mean": ("Mean heart rate while asleep", "bpm", 0),
    "hr_min": ("Lowest heart rate", "bpm", 0),
    "hrv": ("HRV", "ms", 0),
    "resp": ("Respiration", "br/min", 1),
    "temp_dev": ("Skin temperature deviation", "degC", 2),
    "spo2": ("Blood oxygen", "%", 1),
    "asleep_min": ("Time asleep", "min", 0),
}


def percentile(xs, p):
    """Linear-interpolated percentile (p in 0..1) of a list of numbers."""
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    i = int(k)
    return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)


def usual(values):
    """Median and usual range of a list; None if there are fewer than MIN_BASELINE values."""
    xs = [v for v in values if v is not None]
    if len(xs) < MIN_BASELINE:
        return None
    if len(xs) >= 7:
        lo, hi = percentile(xs, .1), percentile(xs, .9)
    else:
        lo, hi = min(xs), max(xs)
    return {"median": percentile(xs, .5), "low": lo, "high": hi, "n": len(xs)}


def describe(key, value, base, n_available):
    """One plain-text line: the value and where it sits against the personal baseline."""
    label, unit, dec = SIGNALS[key]
    text = f"{label}: {value:.{dec}f} {unit}"
    if not base:
        return f"{text}. Still calibrating ({n_available} of {MIN_BASELINE} nights needed)."
    span = f"{base['low']:.{dec}f} to {base['high']:.{dec}f}"
    if base["low"] <= value <= base["high"]:
        return f"{text}. Within your usual range ({span})."
    diff = value - base["median"]
    side = "above" if diff > 0 else "below"
    return (f"{text}, {abs(diff):.{dec}f} {side} your median "
            f"({base['median']:.{dec}f}); you usually range {span}.")


def night_report(nights, day):
    """nights: {'YYYY-MM-DD': {signal: value, ..., 'asleep_min': int}} (main sleeps only).

    Returns one line per signal for `day`, comparing it with the previous nights only
    (the night being judged never enters its own baseline).
    """
    tonight = nights.get(day)
    previous = [n for k, n in sorted(nights.items())
                if k < day and (n.get("asleep_min") or 0) >= MIN_ASLEEP_MIN][-BASELINE_NIGHTS:]
    lines = []
    for key in SIGNALS:
        if tonight is None or tonight.get(key) is None:
            continue
        values = [n.get(key) for n in previous]
        n_available = len([v for v in values if v is not None])
        lines.append(describe(key, tonight[key], usual(values), n_available))
    if tonight and (tonight.get("asleep_min") or 0) < MIN_ASLEEP_MIN:
        lines.append("Note: under 4 h asleep; this night is not used for the baseline.")
    return lines


if __name__ == "__main__":
    # Synthetic demo data (not real measurements).
    start = datetime(2000, 1, 1)
    nights = {(start + timedelta(days=i)).strftime("%Y-%m-%d"):
              {"hr_mean": 55 + i % 3, "hrv": 60 + i % 5, "asleep_min": 420} for i in range(10)}
    last = (start + timedelta(days=10)).strftime("%Y-%m-%d")
    nights[last] = {"hr_mean": 66, "hrv": 41, "asleep_min": 400}
    print("\n".join(night_report(nights, last)))
