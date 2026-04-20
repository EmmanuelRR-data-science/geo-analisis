"""Chart generation for PDF reports using matplotlib."""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def generate_ratings_chart(competitors: list[Any]) -> bytes | None:
    """Generate a horizontal bar chart of competitor ratings."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        ratings = [(c.name[:25], c.google_rating) for c in competitors if c.google_rating is not None]
        if len(ratings) < 2:
            return None

        # Sort by rating
        ratings.sort(key=lambda x: x[1])
        names, values = zip(*ratings[-15:])  # Top 15

        fig, ax = plt.subplots(figsize=(7, max(2.5, len(names) * 0.35)))
        colors = ['#ef4444' if v < 3.0 else '#f59e0b' if v < 4.0 else '#22c55e' for v in values]
        bars = ax.barh(range(len(names)), values, color=colors, height=0.6)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlim(0, 5)
        ax.set_xlabel('Rating', fontsize=8)
        ax.set_title('Ratings de Competidores', fontsize=10, fontweight='bold', color='#2c3e50')
        ax.axvline(x=3.5, color='#94a3b8', linestyle='--', linewidth=0.8, alpha=0.7)

        for bar, val in zip(bars, values):
            ax.text(val + 0.05, bar.get_y() + bar.get_height()/2, f'{val:.1f}', va='center', fontsize=7, color='#374151')

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning("Could not generate ratings chart: %s", e)
        return None


def generate_price_chart(competitors: list[Any]) -> bytes | None:
    """Generate a pie chart of price level distribution."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        prices = [c.google_price_level for c in competitors if c.google_price_level is not None]
        if len(prices) < 2:
            return None

        labels_map = {0: 'Gratis', 1: 'Económico ($)', 2: 'Moderado ($$)', 3: 'Caro ($$$)', 4: 'Muy caro ($$$$)'}
        counts = {}
        for p in prices:
            label = labels_map.get(p, f'Nivel {p}')
            counts[label] = counts.get(label, 0) + 1

        labels = list(counts.keys())
        values = list(counts.values())
        colors = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#7c3aed'][:len(labels)]

        fig, ax = plt.subplots(figsize=(5, 3.5))
        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.0f%%', colors=colors, startangle=90, textprops={'fontsize': 8})
        for t in autotexts:
            t.set_fontsize(8)
            t.set_fontweight('bold')
        ax.set_title('Distribución de Precios', fontsize=10, fontweight='bold', color='#2c3e50')

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning("Could not generate price chart: %s", e)
        return None


def extract_top_complaints(competitors: list[Any], n: int = 5) -> list[dict]:
    """Extract top N low-rated reviews from competitors as common complaints.

    Returns list of dicts with keys: business_name, text, rating.
    """
    low_reviews = []
    for c in competitors:
        if not c.google_reviews:
            continue
        for rev in c.google_reviews:
            if rev.rating <= 3:
                low_reviews.append({
                    "business_name": c.name[:30],
                    "text": rev.text[:150],
                    "rating": rev.rating,
                })

    # Sort by rating (lowest first), then take top N
    low_reviews.sort(key=lambda x: x["rating"])
    return low_reviews[:n]


def extract_schedule_data(competitors: list[Any]) -> list[dict] | None:
    """Extract schedule data as a list of dicts for table rendering.

    Returns list of: {"day": str, "open": int, "closed": int, "total": int, "open_pct": float}
    Returns None if insufficient data (< 2 competitors with hours).
    """
    days_order = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    days_aliases = {
        'lunes': 0, 'monday': 0,
        'martes': 1, 'tuesday': 1,
        'miércoles': 2, 'miercoles': 2, 'wednesday': 2,
        'jueves': 3, 'thursday': 3,
        'viernes': 4, 'friday': 4,
        'sábado': 5, 'sabado': 5, 'saturday': 5,
        'domingo': 6, 'sunday': 6,
    }

    day_counts = [0] * 7
    total_with_hours = 0

    for c in competitors:
        if not c.google_hours:
            continue
        total_with_hours += 1
        for h in c.google_hours:
            h_lower = h.lower().strip()
            for alias, idx in days_aliases.items():
                if h_lower.startswith(alias):
                    if 'cerrado' not in h_lower and 'closed' not in h_lower:
                        day_counts[idx] += 1
                    break

    if total_with_hours < 2:
        return None

    result = []
    for i, day in enumerate(days_order):
        open_count = day_counts[i]
        closed_count = total_with_hours - open_count
        open_pct = round(open_count / total_with_hours * 100, 1) if total_with_hours > 0 else 0
        result.append({
            "day": day,
            "open": open_count,
            "closed": closed_count,
            "total": total_with_hours,
            "open_pct": open_pct,
        })
    return result


def generate_schedule_opportunity_chart(competitors: list[Any]) -> bytes | None:
    """Generate a bar chart showing competitors open by day of week.

    Bar height = number of competitors open that day.
    Darker blue = more competition. Annotation shows closed/total at bar top.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        schedule_data = extract_schedule_data(competitors)
        if schedule_data is None:
            return None

        days = [d["day"] for d in schedule_data]
        open_counts = [d["open"] for d in schedule_data]
        total = schedule_data[0]["total"]
        max_open = max(open_counts) if max(open_counts) > 0 else 1

        fig, ax = plt.subplots(figsize=(7, 3.5))

        # Blue bars with intensity based on how many are open (darker = more competition)
        colors = []
        for count in open_counts:
            intensity = count / max_open  # 0..1
            # Interpolate from light blue (#93c5fd) to dark blue (#1e3a5f)
            r = int(0x93 + (0x1e - 0x93) * intensity)
            g = int(0xc5 + (0x3a - 0xc5) * intensity)
            b = int(0xfd + (0x5f - 0xfd) * intensity)
            colors.append(f'#{r:02x}{g:02x}{b:02x}')

        bars = ax.bar(range(7), open_counts, color=colors, width=0.7, edgecolor='white', linewidth=0.5)

        ax.set_xticks(range(7))
        ax.set_xticklabels(days, fontsize=8, rotation=0)
        ax.set_ylabel('Competidores abiertos', fontsize=8)
        ax.set_ylim(0, total + max(1, total * 0.25))
        ax.set_title('Competidores Abiertos por Día de la Semana', fontsize=10, fontweight='bold', color='#2c3e50')

        # Annotations on bars: closed/total at top, open count inside bar
        for bar, row in zip(bars, schedule_data):
            # Open count inside the bar
            if row["open"] > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                        str(row["open"]), ha='center', va='center',
                        fontsize=9, fontweight='bold', color='white')
            # closed/total annotation above bar
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                    f'{row["closed"]} cerrados / {row["total"]} total',
                    ha='center', va='bottom', fontsize=6.5, color='#374151')

        # Legend
        ax.text(0.02, 0.95, 'Más competidores abiertos = más competencia ese día',
                transform=ax.transAxes, fontsize=7, color='#1e3a5f', va='top', style='italic')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning("Could not generate schedule chart: %s", e)
        return None


def generate_foot_traffic_chart(zone_traffic_profile: dict) -> bytes | None:
    """Generate a bar chart showing average foot traffic by day of week."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        days_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        matrix = zone_traffic_profile.get('hourly_matrix', {})
        if not matrix:
            return None

        day_avgs = []
        for day in days_order:
            hours = matrix.get(day, [0] * 24)
            non_zero = [h for h in hours if h > 0]
            avg = sum(non_zero) / len(non_zero) if non_zero else 0
            day_avgs.append(round(avg, 1))

        if max(day_avgs) == 0:
            return None

        fig, ax = plt.subplots(figsize=(7, 3.5))
        max_avg = max(day_avgs) if max(day_avgs) > 0 else 1
        colors = []
        for avg in day_avgs:
            intensity = avg / max_avg
            if intensity >= 0.7:
                colors.append('#ef4444')
            elif intensity >= 0.4:
                colors.append('#f59e0b')
            else:
                colors.append('#22c55e')

        bars = ax.bar(range(7), day_avgs, color=colors, width=0.7, edgecolor='white', linewidth=0.5)
        ax.set_xticks(range(7))
        ax.set_xticklabels(days_es, fontsize=8)
        ax.set_ylabel('Afluencia promedio (%)', fontsize=8)
        ax.set_ylim(0, max(day_avgs) * 1.2)
        ax.set_title('Tráfico Peatonal Promedio por Día', fontsize=10, fontweight='bold', color='#2c3e50')

        for bar, avg in zip(bars, day_avgs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{avg:.0f}%', ha='center', va='bottom', fontsize=8, fontweight='bold', color='#374151')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning("Could not generate foot traffic chart: %s", e)
        return None
