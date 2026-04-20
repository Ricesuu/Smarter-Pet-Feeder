"""
historicalRules.py — Advanced Automation Rules (Task 3 Advanced Criteria)

Uses historical sensor data stored in the database to make intelligent
decisions, rather than simple threshold-based rules.

Current rule:
  calcIdealPortion(pet_id, cat_weight_sim)
    → Queries the last 5 feedings for this pet from feed_log.
    → If ≥ 3 historical portions exist, returns their rolling average.
    → Otherwise uses a body-weight-based fallback formula.
    → Result drives the FEED,<grams> command to the Arduino.
"""

from database.db import calcIdealPortion

__all__ = ['calcIdealPortion']
