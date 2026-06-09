"""
Re-exports chi-squared significance test from simulation.comparator.
Kept as a separate module so experimentation code does not depend on simulation.
"""
from simulation.comparator import chi_squared_p_value, interpret_p_value

__all__ = ["chi_squared_p_value", "interpret_p_value"]
