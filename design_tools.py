"""Preliminary uniform-flow channel sizing and SI/US conversion helpers.

These are calculation aids, NOT a complete channel/culvert/profile design standard.
"""
from __future__ import annotations
from math import isfinite
from open_channel_program_fixed import RectangularChannel, Manning

METRES_PER_FOOT = 0.3048
CUBIC_METRES_PER_CUBIC_FOOT = METRES_PER_FOOT ** 3


def convert_length(value: float, to: str) -> float:
    """Convert length: to='ft' means m->ft; to='m' means ft->m."""
    value = float(value)
    if not isfinite(value):
        raise ValueError('Length must be finite.')
    if to == 'ft':
        return value / METRES_PER_FOOT
    if to == 'm':
        return value * METRES_PER_FOOT
    raise ValueError("Target unit must be 'm' or 'ft'.")


def convert_discharge(value: float, to: str) -> float:
    """Convert flow: to='cfs' means m3/s->ft3/s; to='cms' means reverse."""
    value = float(value)
    if not isfinite(value):
        raise ValueError('Discharge must be finite.')
    if to == 'cfs':
        return value / CUBIC_METRES_PER_CUBIC_FOOT
    if to == 'cms':
        return value * CUBIC_METRES_PER_CUBIC_FOOT
    raise ValueError("Target unit must be 'cms' or 'cfs'.")


def preliminary_rectangular_design(discharge: float, width: float, roughness: float,
                                   slope: float, freeboard: float = 0.3) -> dict:
    """Compute uniform normal depth and required wall height for specified width.

    Does not check erosion, sediment, lining stability, transitions, floods,
    structural requirements, or local design codes.
    """
    vals = (discharge, width, roughness, slope)
    if any(not isfinite(float(v)) or float(v) <= 0 for v in vals):
        raise ValueError('Discharge, width, roughness and slope must be positive and finite.')
    if not isfinite(float(freeboard)) or freeboard < 0:
        raise ValueError('Freeboard must be nonnegative and finite.')
    channel = RectangularChannel(b=float(width))
    y = Manning.normal_depth(channel, float(discharge), float(roughness), float(slope))
    area = channel.area(y)
    return {'normal_depth_m': y, 'mean_velocity_m_s': float(discharge)/area,
            'freeboard_m': float(freeboard), 'minimum_wall_height_m': y + float(freeboard)}
