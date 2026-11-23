"""Hydraulic structures and rapidly varied flow calculations (SI units)."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt, isfinite

G = 9.81

def positive(value, name):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and greater than zero.")
    return value

@dataclass(frozen=True)
class JumpResult:
    upstream_depth: float
    downstream_depth: float
    upstream_froude: float
    downstream_froude: float
    energy_loss: float
    upstream_energy: float
    downstream_energy: float
    classification: str


def rectangular_hydraulic_jump(discharge, width, upstream_depth):
    """Horizontal rectangular channel; hydrostatic pressure, negligible external forces."""
    q = positive(discharge, 'Discharge') / positive(width, 'Channel width')
    y1 = positive(upstream_depth, 'Upstream depth')
    fr1 = q / (y1 * sqrt(G*y1))
    if fr1 <= 1:
        raise ValueError('A hydraulic jump requires supercritical approach flow (Fr₁ > 1).')
    y2 = y1 / 2 * (sqrt(1 + 8*fr1**2) - 1)
    fr2 = q / (y2 * sqrt(G*y2))
    e1 = y1 + q*q/(2*G*y1*y1)
    e2 = y2 + q*q/(2*G*y2*y2)
    loss = (y2-y1)**3/(4*y1*y2)
    label = ('Undular' if fr1 < 1.7 else 'Weak' if fr1 < 2.5 else
             'Oscillating' if fr1 < 4.5 else 'Steady' if fr1 < 9 else 'Strong')
    return JumpResult(y1, y2, fr1, fr2, loss, e1, e2, label)


def sharp_crested_rectangular_weir(head, crest_width, coefficient=0.62, approach_velocity=0):
    """Idealized free-flow sharp-crested rectangular weir, Q=(2/3)Cd b sqrt(2g) H^1.5.
    Coefficient must be selected for the specific installation and head measurement.
    """
    h = positive(head, 'Head above crest')
    b = positive(crest_width, 'Crest width')
    cd = positive(coefficient, 'Discharge coefficient')
    if cd > 1:
        raise ValueError('Discharge coefficient must not exceed 1 for this model.')
    v = float(approach_velocity)
    if not isfinite(v) or v < 0:
        raise ValueError('Approach velocity must be nonnegative and finite.')
    effective_head = h + v*v/(2*G)
    return (2/3)*cd*b*sqrt(2*G)*effective_head**1.5


def v_notch_weir(head, notch_angle_degrees=90, coefficient=0.60):
    """Idealized free-flow thin-plate triangular notch, Q=(8/15)Cd tan(theta/2)sqrt(2g)H^2.5."""
    from math import tan, radians
    h = positive(head, 'Head above notch')
    angle = positive(notch_angle_degrees, 'Notch angle')
    cd = positive(coefficient, 'Discharge coefficient')
    if not 0 < angle < 180:
        raise ValueError('Notch angle must be between 0 and 180 degrees.')
    if cd > 1:
        raise ValueError('Discharge coefficient must not exceed 1 for this model.')
    return (8/15)*cd*tan(radians(angle/2))*sqrt(2*G)*h**2.5


def trapezoidal_weir(head, bottom_width, side_slope, coefficient=0.62):
    """Idealized free-flow trapezoidal notch with symmetric horizontal:vertical side slopes."""
    h = positive(head, 'Head above crest')
    b = positive(bottom_width, 'Bottom width')
    z = float(side_slope)
    cd = positive(coefficient, 'Discharge coefficient')
    if not isfinite(z) or z < 0 or cd > 1:
        raise ValueError('Side slope must be nonnegative and coefficient must be at most 1.')
    return cd*sqrt(2*G)*((2/3)*b*h**1.5+(8/15)*z*h**2.5)
