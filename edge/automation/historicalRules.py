"""
historicalRules.py — Advanced Automation Rules

Re-exports calcIdealPortion from database.db so feedingSession.py can
import from the automation package. The full implementation lives in db.py.

Rule: calcIdealPortion(pet_id, cat_weight_sim)
  Determines how many grams to dispense for the next feeding session.

  Weight resolution (priority order):
    1. Average of last 5 weight_kg_at_feed entries in feed_log (requires >= 3)
    2. pets.weight_kg — most recent single recorded weight
    3. ADC fallback — rough estimate from live potentiometer value

  Portion calculation:
    - No ideal weight set:
        portion = avg_weight x food_per_kg

    - ideal_weight_kg set on pet profile:
        base    = ideal_weight_kg x food_per_kg
        trend   = clamp(ideal_weight_kg / avg_weight, 0.75, 1.25)
        portion = base x trend
        (overweight -> trend < 1 -> less food; underweight -> trend > 1 -> more food)

  Final result is clamped to [20, 150] grams.
  Result is sent to the Arduino as: FEED,<grams>
"""

from database.db import calcIdealPortion

__all__ = ['calcIdealPortion']
