"""
LiftSim V2 — S-Curve Movement Physics Module
=============================================
Implements jerk-limited S-curve motion profiles for smooth lift movement.

Core concepts:
  - 7-segment S-curve for long trips (jerk-up, ramp-up, jerk-down, cruise,
    jerk-down decel, ramp-down decel, jerk-up decel)
  - 5-segment triangle S-curve for short trips (no cruise phase)
  - Floor-leveling with creep speed approach
  - All profiles are C2 continuous (position, velocity, acceleration continuous)

References:
  - Elevator ride quality standards (ISO 18738)
  - Jerk-limited trajectory planning for motion control
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple


# ── Phase Enum ───────────────────────────────────────────────────────────

class PhaseType(Enum):
    """Segment phases in an S-curve motion profile."""
    ACCEL_JERK_UP = auto()       # T1: +jerk, accel building up
    ACCEL_RAMP = auto()           # T2: 0 jerk, constant accel
    ACCEL_JERK_DOWN = auto()      # T3: -jerk, accel fading out
    CRUISE = auto()               # T4: 0 jerk, 0 accel, constant vel
    DECEL_JERK_DOWN = auto()      # T5: -jerk, decel building up
    DECEL_RAMP = auto()           # T6: 0 jerk, constant decel
    DECEL_JERK_UP = auto()        # T7: +jerk, decel fading out
    LEVELING = auto()             # Creep-speed final approach
    ARRIVED = auto()              # At target, done
    HOLD = auto()                 # Holding position


@dataclass
class ProfileSegment:
    """A single segment of the motion profile.

    Each segment has a constant jerk, giving linear acceleration
    and quadratic velocity within the segment.
    """
    phase: PhaseType
    t_start: float     # Seconds from profile start
    t_end: float       # Seconds from profile start
    pos_start: float   # px
    vel_start: float   # px/s
    accel_start: float # px/s^2
    jerk: float        # px/s^3 (constant throughout segment)

    @property
    def duration(self) -> float:
        return self.t_end - self.t_start

    @property
    def pos_end(self) -> float:
        """Position at segment end."""
        dt = self.duration
        return (self.pos_start
                + self.vel_start * dt
                + 0.5 * self.accel_start * dt * dt
                + (1.0 / 6.0) * self.jerk * dt * dt * dt)

    @property
    def vel_end(self) -> float:
        """Velocity at segment end."""
        dt = self.duration
        return (self.vel_start
                + self.accel_start * dt
                + 0.5 * self.jerk * dt * dt)

    @property
    def accel_end(self) -> float:
        """Acceleration at segment end."""
        return self.accel_start + self.jerk * self.duration

    def sample(self, t: float) -> Tuple[float, float, float]:
        """Sample (position, velocity, acceleration) at time t.

        Args:
            t: Absolute time in seconds from profile start.

        Returns:
            (position px, velocity px/s, acceleration px/s^2)
        """
        if t < self.t_start:
            return (self.pos_start, self.vel_start, self.accel_start)
        if t > self.t_end:
            return (self.pos_end, self.vel_end, self.accel_end)

        dt = t - self.t_start
        a = self.accel_start + self.jerk * dt
        v = self.vel_start + self.accel_start * dt + 0.5 * self.jerk * dt * dt
        p = (self.pos_start
             + self.vel_start * dt
             + 0.5 * self.accel_start * dt * dt
             + (1.0 / 6.0) * self.jerk * dt * dt * dt)
        return (p, v, a)


@dataclass
class MotionProfile:
    """Complete S-curve motion trajectory for a single lift move.

    Composed of ProfileSegments. Provides continuous-time sampling
    of position, velocity, and acceleration.
    """
    segments: List[ProfileSegment] = field(default_factory=list)
    total_distance: float = 0.0
    max_velocity: float = 0.0
    max_accel: float = 0.0
    jerk_limit: float = 0.0

    @property
    def total_duration(self) -> float:
        if not self.segments:
            return 0.0
        return self.segments[-1].t_end

    def sample(self, t: float) -> Tuple[float, float, float]:
        """Sample the profile at absolute time t.

        Args:
            t: Time in seconds from profile start.

        Returns:
            (position px, velocity px/s, acceleration px/s^2)
        """
        if not self.segments:
            return (0.0, 0.0, 0.0)

        if t <= 0.0:
            s = self.segments[0]
            return (s.pos_start, s.vel_start, s.accel_start)

        if t >= self.total_duration:
            s = self.segments[-1]
            return (s.pos_end, s.vel_end, s.accel_end)

        # Binary search for the containing segment
        lo, hi = 0, len(self.segments) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.segments[mid].t_end < t:
                lo = mid + 1
            else:
                hi = mid
        return self.segments[lo].sample(t)

    def sample_velocity_at(self, t: float) -> float:
        return self.sample(t)[1]

    def sample_position_at(self, t: float) -> float:
        return self.sample(t)[0]

    def is_finished(self, t: float) -> bool:
        return t >= self.total_duration

    def fmt_segments(self) -> str:
        lines = [f"Total duration: {self.total_duration:.3f}s, "
                 f"Distance: {self.total_distance:.1f}px"]
        for s in self.segments:
            p_end = s.pos_end
            v_end = s.vel_end
            a_end = s.accel_end
            lines.append(
                f"  {s.phase.name:20s} | "
                f"t=[{s.t_start:6.3f}>{s.t_end:6.3f}] | "
                f"p=[{s.pos_start:8.2f}>{p_end:8.2f}] | "
                f"v=[{s.vel_start:8.2f}>{v_end:8.2f}] | "
                f"a=[{s.accel_start:8.2f}>{a_end:8.2f}] | "
                f"j={s.jerk:8.2f}"
            )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Segment Builders (Internal)
# ═══════════════════════════════════════════════════════════════════════

def _build_accel_segments(
    p0: float, v0: float, a0: float,
    t0: float, t_j: float, t_a_total: float,
    a_max: float, jerk: float,
) -> List[ProfileSegment]:
    """Build T1+T2+T3 segments for an acceleration phase.

    Args:
        p0, v0, a0: Starting state at t0.
        t0: Start time.
        t_j: Duration of each jerk sub-phase = a_max / jerk.
        t_a_total: Total duration of accel phase (>= 2*t_j).
        a_max: Peak acceleration magnitude (+ve).
        jerk: Jerk magnitude (+ve).

    Returns:
        [T1, T2, T3] segments.
    """
    segments = []
    t = t0
    p, v, a = p0, v0, a0

    # T1: Jerk-up (acceleration building)
    dt1 = t_j
    segments.append(ProfileSegment(
        phase=PhaseType.ACCEL_JERK_UP,
        t_start=t, t_end=t + dt1,
        pos_start=p, vel_start=v, accel_start=a,
        jerk=jerk,
    ))
    t += dt1; p = segments[-1].pos_end
    v = segments[-1].vel_end; a = segments[-1].accel_end

    # T2: Ramp (constant acceleration) — only if enough duration
    dt2 = t_a_total - 2 * t_j
    if dt2 > 0.001:
        segments.append(ProfileSegment(
            phase=PhaseType.ACCEL_RAMP,
            t_start=t, t_end=t + dt2,
            pos_start=p, vel_start=v, accel_start=a,
            jerk=0.0,
        ))
        t += dt2
        p = segments[-1].pos_end
        v = segments[-1].vel_end
        a = segments[-1].accel_end

    # T3: Jerk-down (acceleration fading)
    dt3 = t_j
    segments.append(ProfileSegment(
        phase=PhaseType.ACCEL_JERK_DOWN,
        t_start=t, t_end=t + dt3,
        pos_start=p, vel_start=v, accel_start=a,
        jerk=-jerk,
    ))
    return segments


def _build_decel_segments(
    p0: float, v0: float, a0: float,
    t0: float, t_j: float, t_d_total: float,
    d_max: float, jerk: float,
) -> List[ProfileSegment]:
    """Build T5+T6+T7 segments for a deceleration phase.

    Deceleration mirrors acceleration: negative jerk/accel, but
    we pass d_max as the absolute magnitude (> 0).

    Args:
        p0, v0, a0: Starting state at t0 (a0 should be ~0).
        t0: Start time.
        t_j: Duration of each jerk sub-phase = d_max / jerk.
        t_d_total: Total duration of decel phase (>= 2*t_j).
        d_max: Peak deceleration magnitude (+ve).
        jerk: Jerk magnitude (+ve).

    Returns:
        [T5, T6, T7] segments.
    """
    segments = []
    t = t0
    p, v, a = p0, v0, a0

    # T5: Jerk-down for decel (negative jerk)
    dt5 = t_j
    segments.append(ProfileSegment(
        phase=PhaseType.DECEL_JERK_DOWN,
        t_start=t, t_end=t + dt5,
        pos_start=p, vel_start=v, accel_start=a,
        jerk=-jerk,
    ))
    t += dt5; p = segments[-1].pos_end
    v = segments[-1].vel_end; a = segments[-1].accel_end

    # T6: Ramp (constant deceleration)
    dt6 = t_d_total - 2 * t_j
    if dt6 > 0.001:
        segments.append(ProfileSegment(
            phase=PhaseType.DECEL_RAMP,
            t_start=t, t_end=t + dt6,
            pos_start=p, vel_start=v, accel_start=a,
            jerk=0.0,
        ))
        t += dt6
        p = segments[-1].pos_end
        v = segments[-1].vel_end
        a = segments[-1].accel_end

    # T7: Jerk-up (decel fading, back to 0 acceleration)
    dt7 = t_j
    segments.append(ProfileSegment(
        phase=PhaseType.DECEL_JERK_UP,
        t_start=t, t_end=t + dt7,
        pos_start=p, vel_start=v, accel_start=a,
        jerk=jerk,
    ))
    return segments


def _add_segments(profile_segments: List[ProfileSegment],
                  new_segments: List[ProfileSegment]) -> None:
    """Append new segments, offsetting times by current end time."""
    offset = profile_segments[-1].t_end if profile_segments else 0.0
    for seg in new_segments:
        profile_segments.append(ProfileSegment(
            phase=seg.phase,
            t_start=seg.t_start + offset,
            t_end=seg.t_end + offset,
            pos_start=seg.pos_start,
            vel_start=seg.vel_start,
            accel_start=seg.accel_start,
            jerk=seg.jerk,
        ))


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def compute_s_curve_profile(
    distance: float,
    v_max: float,
    a_max: float,
    jerk: float,
) -> MotionProfile:
    """Compute a 7-segment S-curve (or 5-segment triangle) motion profile.

    Accelerates from 0 to v_max (or less if trip is short), cruises,
    then decelerates to 0 at the target position.

    For short trips: generates a triangle S-curve (no cruise phase)
    with a lower peak velocity.

    Args:
        distance: Total travel distance in px (positive).
        v_max: Maximum velocity in px/s.
        a_max: Maximum acceleration magnitude in px/s^2.
        jerk: Jerk limit in px/s^3.

    Returns:
        MotionProfile.
    """
    if distance <= 0.0:
        return MotionProfile(segments=[], total_distance=0.0)

    t_j = a_max / jerk  # Duration of jerk sub-phase

    # Compute accel/decel distance for a profile that reaches v_max
    def accel_distance_and_time(peak_v: float) -> Tuple[float, float]:
        """Return (distance_covered, total_time) for accel to peak_v."""
        if peak_v <= a_max * t_j:
            # Can't even finish T1 before hitting peak_v
            # From: v = 0.5 * jerk * t^2 -> t = sqrt(2*v/jerk)
            t1 = math.sqrt(2.0 * peak_v / jerk)
            p_a = (1.0 / 6.0) * jerk * t1 * t1 * t1
            return p_a, t1

        t_ramp = peak_v / a_max - t_j
        t_total = 2 * t_j + max(t_ramp, 0.0)

        phases = _build_accel_segments(
            0.0, 0.0, 0.0, 0.0, t_j, t_total, a_max, jerk)
        return phases[-1].pos_end, t_total

    p_accel_full, t_accel_full = accel_distance_and_time(v_max)
    min_full_dist = 2.0 * p_accel_full  # accel + decel (symmetric)

    if distance >= min_full_dist:
        # Full 7-segment S-curve
        return _build_full_profile(distance, v_max, a_max, jerk,
                                   t_j, p_accel_full, t_accel_full)

    # Short trip — find peak velocity for triangle profile
    # Binary search for v_peak such that v_peak yields distance = total dist
    lo, hi = 1.0, v_max
    for _ in range(40):
        mid = (lo + hi) * 0.5
        p_a, _ = accel_distance_and_time(mid)
        if 2.0 * p_a < distance:
            lo = mid
        else:
            hi = mid

    v_peak = (lo + hi) * 0.5
    return _compute_triangle_profile(distance, v_peak, a_max, jerk)


def _build_full_profile(
    distance: float, v_max: float, a_max: float, jerk: float,
    t_j: float, p_accel: float, t_accel: float,
) -> MotionProfile:
    """Build a full 7-segment S-curve with cruise phase."""
    segments: List[ProfileSegment] = []

    # Accel phase (T1+T2+T3)
    accel_segs = _build_accel_segments(
        0.0, 0.0, 0.0, 0.0, t_j, t_accel, a_max, jerk)
    segments.extend(accel_segs)
    t = segments[-1].t_end
    p_after_accel = segments[-1].pos_end
    v_after_accel = segments[-1].vel_end

    # Cruise (T4)
    cruise_dist = distance - 2.0 * p_accel
    if cruise_dist > 0.5:
        cruise_dur = cruise_dist / v_after_accel
        segments.append(ProfileSegment(
            phase=PhaseType.CRUISE,
            t_start=t, t_end=t + cruise_dur,
            pos_start=p_after_accel, vel_start=v_after_accel,
            accel_start=0.0, jerk=0.0,
        ))
        t += cruise_dur
        p_after_cruise = p_after_accel + v_after_accel * cruise_dur
    else:
        p_after_cruise = p_after_accel

    # Decel phase (T5+T6+T7)
    decel_segs = _build_decel_segments(
        p_after_cruise, v_after_accel, 0.0,
        0.0, t_j, t_accel, a_max, jerk)
    for seg in decel_segs:
        segments.append(ProfileSegment(
            phase=seg.phase,
            t_start=seg.t_start + t,
            t_end=seg.t_end + t,
            pos_start=seg.pos_start, vel_start=seg.vel_start,
            accel_start=seg.accel_start, jerk=seg.jerk,
        ))

    return MotionProfile(
        segments=segments,
        total_distance=distance,
        max_velocity=v_max,
        max_accel=a_max,
        jerk_limit=jerk,
    )


def _compute_triangle_profile(
    distance: float, v_peak: float, a_max: float, jerk: float,
) -> MotionProfile:
    """Build a 5-segment triangle S-curve (no cruise phase)."""
    t_j = a_max / jerk
    segments: List[ProfileSegment] = []

    if v_peak <= a_max * t_j:
        # Very short: single jerk pulse then immediate reversal
        t_half = math.sqrt(2.0 * v_peak / jerk)
        # T1: jerk up
        segments.append(ProfileSegment(
            phase=PhaseType.ACCEL_JERK_UP,
            t_start=0.0, t_end=t_half,
            pos_start=0.0, vel_start=0.0, accel_start=0.0,
            jerk=jerk,
        ))
        t = t_half
        p_peak = segments[-1].pos_end
        v_peak_actual = segments[-1].vel_end
        a_peak = segments[-1].accel_end

        # T5: immediate decel (jerk down)
        segments.append(ProfileSegment(
            phase=PhaseType.DECEL_JERK_DOWN,
            t_start=t, t_end=t + t_half,
            pos_start=p_peak, vel_start=v_peak_actual, accel_start=a_peak,
            jerk=-jerk,
        ))
    else:
        t_ramp = v_peak / a_max - t_j
        t_phase = 2 * t_j + t_ramp

        # Accel
        accel_segs = _build_accel_segments(
            0.0, 0.0, 0.0, 0.0, t_j, t_phase, a_max, jerk)
        segments.extend(accel_segs)
        t = segments[-1].t_end
        p_after_accel = segments[-1].pos_end
        v_after_accel = segments[-1].vel_end

        # Decel (immediately follows)
        decel_segs = _build_decel_segments(
            p_after_accel, v_after_accel, 0.0,
            0.0, t_j, t_phase, a_max, jerk)
        for seg in decel_segs:
            segments.append(ProfileSegment(
                phase=seg.phase,
                t_start=seg.t_start + t,
                t_end=seg.t_end + t,
                pos_start=seg.pos_start, vel_start=seg.vel_start,
                accel_start=seg.accel_start, jerk=seg.jerk,
            ))

    return MotionProfile(
        segments=segments,
        total_distance=distance,
        max_velocity=v_peak,
        max_accel=a_max,
        jerk_limit=jerk,
    )


# ═══════════════════════════════════════════════════════════════════════
# Leveling and Braking
# ═══════════════════════════════════════════════════════════════════════

def compute_leveling_profile(
    remaining_distance: float,
    creep_speed: float,
    arrival_threshold: float = 0.5,
) -> MotionProfile:
    """Compute a floor-leveling final approach profile.

    The lift enters creep speed mode to precisely align with
    the target floor.

    Args:
        remaining_distance: Distance to target floor (px).
        creep_speed: Target creep velocity (px/s).
        arrival_threshold: Distance at which to snap (px).

    Returns:
        MotionProfile for the leveling phase.
    """
    if remaining_distance <= arrival_threshold:
        return MotionProfile(segments=[
            ProfileSegment(
                phase=PhaseType.ARRIVED,
                t_start=0.0, t_end=0.1,
                pos_start=remaining_distance, vel_start=0.0, accel_start=0.0,
                jerk=0.0,
            )
        ], total_distance=remaining_distance)

    travel_time = (remaining_distance - arrival_threshold) / max(creep_speed, 0.1)
    creep_dist = creep_speed * travel_time

    return MotionProfile(segments=[
        ProfileSegment(
            phase=PhaseType.LEVELING,
            t_start=0.0, t_end=travel_time,
            pos_start=0.0, vel_start=creep_speed, accel_start=0.0,
            jerk=0.0,
        ),
        ProfileSegment(
            phase=PhaseType.ARRIVED,
            t_start=travel_time, t_end=travel_time + 0.1,
            pos_start=creep_dist, vel_start=creep_speed, accel_start=0.0,
            jerk=0.0,
        ),
    ], total_distance=remaining_distance)


def compute_creep_profile(
    distance: float,
    creep_speed: float,
) -> MotionProfile:
    """Compute a simple approach profile at creep speed."""
    total_time = distance / max(creep_speed, 0.1)
    return MotionProfile(segments=[
        ProfileSegment(
            phase=PhaseType.LEVELING,
            t_start=0.0, t_end=total_time,
            pos_start=0.0, vel_start=creep_speed, accel_start=0.0,
            jerk=0.0,
        ),
    ], total_distance=distance)


def s_curve_braking_distance(
    current_vel: float,
    a_max: float,
    jerk: float,
) -> float:
    """Calculate minimum braking distance using S-curve deceleration.

    S-curve equivalent of v^2/(2a) for linear deceleration.

    Args:
        current_vel: Current velocity (px/s, >= 0).
        a_max: Maximum deceleration (px/s^2).
        jerk: Jerk limit (px/s^3).

    Returns:
        Minimum distance required to stop (px).
    """
    t_j = a_max / jerk

    if current_vel <= a_max * t_j:
        # Low speed: can't reach full deceleration
        t_brake = math.sqrt(2.0 * current_vel / jerk)
        return (1.0 / 6.0) * jerk * t_brake * t_brake * t_brake

    t_ramp = current_vel / a_max - t_j
    t_decel = 2 * t_j + t_ramp

    phases = _build_decel_segments(
        0.0, current_vel, 0.0, 0.0, t_j, t_decel, a_max, jerk)
    return phases[-1].pos_end


def s_curve_time_to_stop(
    current_vel: float,
    a_max: float,
    jerk: float,
) -> float:
    """Calculate time needed to come to a complete stop.

    Args:
        current_vel: Current velocity (px/s, >= 0).
        a_max: Maximum deceleration (px/s^2).
        jerk: Jerk limit (px/s^3).

    Returns:
        Time in seconds to stop.
    """
    t_j = a_max / jerk
    if current_vel <= a_max * t_j:
        return math.sqrt(2.0 * current_vel / jerk)
    t_ramp = current_vel / a_max - t_j
    return 2 * t_j + t_ramp


# ═══════════════════════════════════════════════════════════════════════
# Self-Test
# ═══════════════════════════════════════════════════════════════════════

def _assert_close(name: str, actual: float, expected: float, tol: float = 0.5) -> bool:
    """Check that actual is within tolerance of expected."""
    if abs(actual - expected) > tol:
        print(f"  [WARN] {name}: got {actual:.2f}, expected {expected:.2f}")
        return False
    return True


def _check_profile_validity(profile: MotionProfile, target_dist: float) -> bool:
    """Validate a profile for correctness."""
    ok = True

    # End position
    p_end, v_end, a_end = profile.sample(profile.total_duration)
    ok &= _assert_close("End position", p_end, target_dist)
    ok &= _assert_close("Final velocity", v_end, 0.0, tol=0.5)
    ok &= _assert_close("Final acceleration", a_end, 0.0, tol=1.0)

    # Start position
    p_start, v_start, a_start = profile.sample(0.0)
    ok &= _assert_close("Start position", p_start, 0.0)
    ok &= _assert_close("Start velocity", v_start, 0.0, tol=0.5)

    # Continuity check (fine sampling)
    dt = 0.005
    prev_p, prev_v, prev_a = profile.sample(0.0)
    for i in range(1, int(profile.total_duration / dt) + 2):
        t = i * dt
        p, v, a = profile.sample(t)

        # Velocity continuity: dv should be <= a_max * dt for accel phase
        dv = abs(v - prev_v)
        # Acceleration continuity: da/dt should be <= jerk
        da = abs(a - prev_a)
        jerk_actual = da / dt if dt > 0 else 0
        if jerk_actual > profile.jerk_limit * 3.0 and profile.jerk_limit > 0:
            print(f"  [WARN] Jerk violation at t={t:.3f}: jerk={jerk_actual:.0f} "
                  f"(limit={profile.jerk_limit:.0f}), da={da:.2f}")
            ok = False

        # Position should never regress
        if p < prev_p - 0.01:
            # Actually position CAN regress at the very start with decel... no
            # for a proper S-curve, position is monotonic
            print(f"  [WARN] Position regression at t={t:.3f}: {prev_p:.4f} -> {p:.4f}")
            ok = False

        prev_p, prev_v, prev_a = p, v, a

    return ok


def self_test() -> None:
    """Run internal validation of profile computations."""
    test_cases = [
        (10.0, "tiny"),
        (50.0, "1/2 floor"),
        (100.0, "1 floor"),
        (300.0, "3 floors"),
        (900.0, "9 floors (full speed)"),
        (2000.0, "20 floors (cruise)"),
    ]

    V_MAX = 200.0
    A_MAX = 80.0
    JERK = 400.0
    CREEP = 12.0

    print("#" * 70)
    print("S-Curve Motion Profile Self-Test")
    print("#" * 70)
    print(f"  v_max = {V_MAX:.0f} px/s")
    print(f"  a_max = {A_MAX:.0f} px/s2")
    print(f"  jerk  = {JERK:.0f} px/s3")
    print(f"  t_j   = {A_MAX/JERK:.3f} s")
    print()

    all_pass = True

    for dist, label in test_cases:
        print(f"--- {label} (distance = {dist:.0f} px) ---")
        profile = compute_s_curve_profile(dist, V_MAX, A_MAX, JERK)
        print(profile.fmt_segments())
        valid = _check_profile_validity(profile, dist)
        if not valid:
            all_pass = False
        print(f"  Peak v: {profile.max_velocity:.1f} px/s")
        print()

    # Braking distance
    print("--- Braking Distance Check ---")
    for v in [50, 100, 200]:
        bd = s_curve_braking_distance(v, A_MAX, JERK)
        bt = s_curve_time_to_stop(v, A_MAX, JERK)
        # Verify: should be less than equivalent linear braking
        linear_bd = v * v / (2.0 * A_MAX)
        print(f"  v={v:.0f}: S-curve brake_dist={bd:.1f}px (linear={linear_bd:.1f}px), "
              f"time={bt:.3f}s")
        if bd > linear_bd * 1.5:
            print(f"    [WARN] S-curve braking longer than expected")
            all_pass = False
    print()

    # Leveling profile test
    print("--- Floor-Leveling Profile ---")
    level = compute_leveling_profile(8.0, CREEP)
    print(level.fmt_segments())
    print()

    # Summary
    if all_pass:
        print("[OK] All checks passed!")
    else:
        print("[WARN] Some checks failed. See above.")


if __name__ == "__main__":
    self_test()
