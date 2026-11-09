# ac_app/lib/telemetry_ingest.py
# Python 3.3 compatible — stdlib only

import math

try:
    import ac
    import acsys
except ImportError:
    ac = None
    acsys = None


class TelemetryFrame(object):
    __slots__ = (
        "t", "spline", "speed_kmh", "throttle", "brake", "steer", "steer_road",
        "velocity", "acc_g", "heading", "roll", "yaw_rate", "yaw_accel",
        "slip", "slip_ratio", "tyre_temp", "tyre_pressure", "susp_travel",
        "susp_ratio", "wheel_load", "camber",
        "pos_x", "pos_y", "pos_z",
        "lap", "sector", "in_pit", "track", "car",
        "track_config", "track_length_m",
        "gear", "rpm", "tyres_out", "ffb", "brake_bias",
        "wheel_speed", "tyre_radius", "tyre_temp_imo", "brake_temp", "ride_height",
    )

    def __init__(self):
        self.t = 0.0
        self.spline = 0.0
        self.speed_kmh = 0.0
        self.throttle = 0.0
        self.brake = 0.0
        self.steer = 0.0
        self.steer_road = 0.0
        self.velocity = (0.0, 0.0, 0.0)
        self.acc_g = (0.0, 0.0, 0.0)
        self.heading = 0.0
        self.roll = 0.0
        self.yaw_rate = 0.0
        self.yaw_accel = 0.0
        self.slip = (0.0, 0.0, 0.0, 0.0)
        self.slip_ratio = (0.0, 0.0, 0.0, 0.0)
        self.tyre_temp = (0.0, 0.0, 0.0, 0.0)
        self.tyre_pressure = (0.0, 0.0, 0.0, 0.0)
        self.susp_travel = (0.0, 0.0, 0.0, 0.0)
        self.susp_ratio = (0.0, 0.0, 0.0, 0.0)
        self.wheel_load = (0.0, 0.0, 0.0, 0.0)
        self.camber = (0.0, 0.0, 0.0, 0.0)
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        self.lap = 0
        self.sector = 0
        self.in_pit = False
        self.track = ""
        self.car = ""
        self.track_config = ""
        self.track_length_m = 0.0
        self.gear = 0
        self.rpm = 0
        self.tyres_out = 0
        self.ffb = 0.0
        self.brake_bias = 0.0
        self.wheel_speed = (0.0, 0.0, 0.0, 0.0)
        self.tyre_radius = (0.0, 0.0, 0.0, 0.0)
        self.tyre_temp_imo = ()
        self.brake_temp = ()
        self.ride_height = ()


class TelemetryIngest(object):
    """Adapter: sim_info + ac API -> TelemetryFrame each tick."""

    # Frame conventions: steer is the normalized input (-1..1, + = right),
    # steer_road the road-wheel angle in radians, acc_g is
    # (longitudinal, lateral, vertical) in g with lateral + in right turns,
    # yaw_rate is rad/s with + = right (heading increases turning right).

    def __init__(self, sim_info):
        self._sim = sim_info
        self._prev_heading = None
        self._prev_yaw_rate = None
        self._prev_t = 0.0
        self._frame = TelemetryFrame()
        self._susp_max = (0.1, 0.1, 0.1, 0.1)
        self._max_road_wheel_rad = math.radians(20.0)

    def set_steer_range(self, max_road_wheel_deg):
        if max_road_wheel_deg and max_road_wheel_deg > 0:
            self._max_road_wheel_rad = math.radians(float(max_road_wheel_deg))

    def sample(self, delta_t):
        p = self._sim.physics
        g = self._sim.graphics
        s = self._sim.static
        f = self._frame

        f.t += delta_t
        if ac is not None and acsys is not None:
            f.spline = ac.getCarState(0, acsys.CS.NormalizedSplinePosition)
        else:
            f.spline = getattr(g, "normalizedCarPosition", 0.0)

        f.speed_kmh = p.speedKmh
        f.throttle = p.gas
        f.brake = p.brake
        f.steer = p.steerAngle
        f.steer_road = p.steerAngle * self._max_road_wheel_rad
        f.velocity = (p.velocity[0], p.velocity[1], p.velocity[2])
        # AC accG is car-local (x lateral, + left; y vertical; z longitudinal).
        f.acc_g = (p.accG[2], -p.accG[0], p.accG[1])
        f.heading = p.heading
        f.roll = p.roll
        f.slip = (p.wheelSlip[0], p.wheelSlip[1], p.wheelSlip[2], p.wheelSlip[3])
        f.slip_ratio = f.slip
        f.wheel_load = (p.wheelLoad[0], p.wheelLoad[1], p.wheelLoad[2], p.wheelLoad[3])
        f.camber = (p.camberRAD[0], p.camberRAD[1], p.camberRAD[2], p.camberRAD[3])
        smax = s.suspensionMaxTravel
        if smax[0] > 0.01:
            self._susp_max = (smax[0], smax[1], smax[2], smax[3])
        f.susp_travel = (
            p.suspensionTravel[0], p.suspensionTravel[1],
            p.suspensionTravel[2], p.suspensionTravel[3],
        )
        f.susp_ratio = tuple(
            p.suspensionTravel[i] / max(self._susp_max[i], 0.001) for i in range(4)
        )
        f.tyre_temp = (
            p.tyreCoreTemperature[0], p.tyreCoreTemperature[1],
            p.tyreCoreTemperature[2], p.tyreCoreTemperature[3],
        )
        f.tyre_pressure = (
            p.wheelsPressure[0], p.wheelsPressure[1],
            p.wheelsPressure[2], p.wheelsPressure[3],
        )
        f.lap = g.completedLaps
        f.sector = g.currentSectorIndex
        f.in_pit = bool(g.isInPit)
        f.track = s.track
        f.car = s.carModel
        f.track_config = getattr(s, "trackConfiguration", "") or ""
        f.track_length_m = float(getattr(s, "trackSPlineLength", 0.0) or 0.0)
        f.gear = int(p.gear)
        f.rpm = int(p.rpms)
        f.tyres_out = int(getattr(p, "numberOfTyresOut", 0) or 0)
        f.ffb = float(getattr(p, "finalFF", 0.0) or 0.0)
        bias = float(getattr(p, "brakeBias", 0.0) or 0.0)
        # Only trust brakeBias if the extended physics page lined up (front share is 0.3-0.9 on any car).
        f.brake_bias = bias if 0.3 < bias < 0.9 else 0.0
        ws = getattr(p, "wheelAngularSpeed", None)
        if ws is not None:
            f.wheel_speed = tuple(float(ws[i]) for i in range(4))
        radius = getattr(s, "tyreRadius", None)
        if radius is not None and 0.15 < radius[0] < 0.6:
            f.tyre_radius = tuple(float(radius[i]) for i in range(4))
        f.tyre_temp_imo = self._tyre_temp_imo(p)
        f.brake_temp = self._ext_quad(p, "brakeTemp", 0.0, 1500.0)
        f.ride_height = self._ext_pair(p, "rideHeight", 0.0, 0.5)
        coords = getattr(g, "carCoordinates", None)
        if coords is not None:
            f.pos_x = float(coords[0])
            f.pos_y = float(coords[1])
            f.pos_z = float(coords[2])

        # CSP's ext_getAngleSpeed() reads 0 in practice, so always differentiate heading.
        if self._prev_heading is not None and delta_t > 1e-4:
            dh = self._wrap_pi(p.heading - self._prev_heading)
            f.yaw_rate = dh / delta_t
        else:
            f.yaw_rate = 0.0

        if self._prev_yaw_rate is not None and delta_t > 0:
            f.yaw_accel = (f.yaw_rate - self._prev_yaw_rate) / delta_t
        else:
            f.yaw_accel = 0.0

        self._prev_heading = p.heading
        self._prev_yaw_rate = f.yaw_rate
        self._prev_t = f.t
        return f

    def is_safe_for_audio(self, frame):
        if frame.in_pit:
            return True
        straight = abs(frame.steer) < 0.08 and frame.throttle > 0.85
        sf_line = frame.spline < 0.02 or frame.spline > 0.98
        slow_exit = frame.speed_kmh < 140 and frame.brake < 0.05 and abs(frame.steer) < 0.12
        return straight or sf_line or slow_exit

    # Extended physics fields only exist on newer AC builds; drop values outside a
    # physical range so a misaligned page records nothing instead of garbage.
    @staticmethod
    def _ext_quad(p, name, lo, hi):
        vals = getattr(p, name, None)
        if vals is None:
            return ()
        out = tuple(float(vals[i]) for i in range(4))
        return out if all(lo <= v <= hi for v in out) and any(out) else ()

    @staticmethod
    def _ext_pair(p, name, lo, hi):
        vals = getattr(p, name, None)
        if vals is None:
            return ()
        out = (float(vals[0]), float(vals[1]))
        return out if all(lo <= v <= hi for v in out) and any(out) else ()

    @staticmethod
    def _tyre_temp_imo(p):
        if getattr(p, "tyreTempI", None) is None:
            return ()
        out = tuple(
            (float(p.tyreTempI[i]), float(p.tyreTempM[i]), float(p.tyreTempO[i])) for i in range(4)
        )
        flat = [v for t in out for v in t]
        return out if all(-20.0 <= v <= 300.0 for v in flat) and any(flat) else ()

    @staticmethod
    def _wrap_pi(angle):
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    @staticmethod
    def frame_from_dict(data):
        """Build a TelemetryFrame from a plain dict (for tests)."""
        f = TelemetryFrame()
        for key in TelemetryFrame.__slots__:
            if key in data:
                setattr(f, key, data[key])
        return f
