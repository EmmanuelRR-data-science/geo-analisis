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


def generate_schedule_opportunity_chart(competitors: list[Any]) -> bytes | None:
    """Generate a heatmap showing opportunity windows by day/hour.

    Analyzes competitor opening hours to find days with less competition.
    Green = high opportunity (few competitors open), Red = low opportunity (many open).
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        # Parse competitor hours into day coverage
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

        # Count how many competitors are open each day
        day_counts = [0] * 7
        total_with_hours = 0

        for c in competitors:
            if not c.google_hours:
                continue
            total_with_hours += 1
            for h in c.google_hours:
                h_lower = h.lower().strip()
                # Try to match day name at the start
                for alias, idx in days_aliases.items():
                    if h_lower.startswith(alias):
                        # Check if it says "closed" or "cerrado"
                        if 'cerrado' not in h_lower and 'closed' not in h_lower:
                            day_counts[idx] += 1
                        break

        if total_with_hours < 2:
            return None

        # Calculate opportunity score (inverse of coverage)
        max_count = max(day_counts) if max(day_counts) > 0 else 1
        opportunity = [round((1 - count / max_count) * 100) for count in day_counts]

        fig, ax = plt.subplots(figsize=(7, 3.5))

        # Create bar chart with gradient colors
        colors = []
        for opp in opportunity:
            if opp >= 70:
                colors.append('#22c55e')  # High opportunity - green
            elif opp >= 40:
                colors.append('#f59e0b')  # Medium - amber
            else:
                colors.append('#ef4444')  # Low opportunity - red

        bars = ax.bar(range(7), opportunity, color=colors, width=0.7, edgecolor='white', linewidth=0.5)

        ax.set_xticks(range(7))
        ax.set_xticklabels(days_order, fontsize=8, rotation=0)
        ax.set_ylabel('Oportunidad (%)', fontsize=8)
        ax.set_ylim(0, 110)
        ax.set_title('Oportunidad por Día de la Semana', fontsize=10, fontweight='bold', color='#2c3e50')

        # Add value labels on bars
        for bar, opp, count in zip(bars, opportunity, day_counts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    f'{opp}%', ha='center', va='bottom', fontsize=8, fontweight='bold', color='#374151')
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()/2,
                    f'{count}/{total_with_hours}', ha='center', va='center', fontsize=7, color='white', fontweight='bold')

        # Add legend
        ax.text(0.02, 0.95, '■ Alta oportunidad (pocos competidores)', transform=ax.transAxes,
                fontsize=7, color='#22c55e', va='top')
        ax.text(0.02, 0.88, '■ Media oportunidad', transform=ax.transAxes,
                fontsize=7, color='#f59e0b', va='top')
        ax.text(0.02, 0.81, '■ Baja oportunidad (muchos competidores)', transform=ax.transAxes,
                fontsize=7, color='#ef4444', va='top')

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
