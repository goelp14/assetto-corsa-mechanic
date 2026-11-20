"""ctypes layouts for ACC shared memory (v1.8.12-style, open-source field order)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import c_float, c_int32, c_wchar

# Named mapping objects (Windows file mapping tags).
ACC_PHYSICS_MAP = "Local\\acpmf_physics"
ACC_GRAPHICS_MAP = "Local\\acpmf_graphics"
ACC_STATIC_MAP = "Local\\acpmf_static"

WCHAR = c_wchar


class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("gas", c_float),
        ("brake", c_float),
        ("fuel", c_float),
        ("gear", c_int32),
        ("rpms", c_int32),
        ("steerAngle", c_float),
        ("speedKmh", c_float),
        ("velocity", c_float * 3),
        ("accG", c_float * 3),
        ("wheelSlip", c_float * 4),
        ("wheelLoad", c_float * 4),
        ("wheelsPressure", c_float * 4),
        ("wheelAngularSpeed", c_float * 4),
        ("tyreWear", c_float * 4),
        ("tyreDirtyLevel", c_float * 4),
        ("tyreCoreTemperature", c_float * 4),
        ("camberRAD", c_float * 4),
        ("suspensionTravel", c_float * 4),
        ("drs", c_float),
        ("tc", c_float),
        ("heading", c_float),
        ("pitch", c_float),
        ("roll", c_float),
        ("cgHeight", c_float),
        ("carDamage", c_float * 5),
        ("numberOfTyresOut", c_int32),
        ("pitLimiterOn", c_int32),
        ("abs", c_float),
        ("kersCharge", c_float),
        ("kersInput", c_float),
        ("autoShifterOn", c_int32),
        ("rideHeight", c_float * 2),
        ("turboBoost", c_float),
        ("ballast", c_float),
        ("airDensity", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localAngularVel", c_float * 3),
        ("finalFF", c_float),
        ("performanceMeter", c_float),
        ("engineBrake", c_int32),
        ("ersRecoveryLevel", c_int32),
        ("ersPowerLevel", c_int32),
        ("ersHeatCharging", c_int32),
        ("ersIsCharging", c_int32),
        ("kersCurrentKJ", c_float),
        ("drsAvailable", c_int32),
        ("drsEnabled", c_int32),
        ("brakeTemp", c_float * 4),
        ("clutch", c_float),
        ("tyreTempI", c_float * 4),
        ("tyreTempM", c_float * 4),
        ("tyreTempO", c_float * 4),
        ("isAIControlled", c_int32),
        ("tyreContactPoint", c_float * 4 * 3),
        ("tyreContactNormal", c_float * 4 * 3),
        ("tyreContactHeading", c_float * 4 * 3),
        ("brakeBias", c_float),
        ("localVelocity", c_float * 3),
        ("P2PActivations", c_int32),
        ("P2PStatus", c_int32),
        ("currentMaxRpm", c_int32),
        ("mz", c_float * 4),
        ("fx", c_float * 4),
        ("fy", c_float * 4),
        ("slipRatio", c_float * 4),
        ("slipAngle", c_float * 4),
        ("tcinAction", c_int32),
        ("absInAction", c_int32),
        ("suspensionDamage", c_float * 4),
        ("tyreTemp", c_float * 4),
        ("waterTemp", c_float),
        ("brakePressure", c_float * 4),
        ("frontBrakeCompound", c_int32),
        ("rearBrakeCompound", c_int32),
        ("padLife", c_float * 4),
        ("discLife", c_float * 4),
        ("ignitionOn", c_int32),
        ("starterEngineOn", c_int32),
        ("isEngineRunning", c_int32),
        ("kerbVibration", c_float),
        ("slipVibrations", c_float),
        ("gVibrations", c_float),
        ("absVibrations", c_float),
    ]


class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("status", c_int32),
        ("session", c_int32),
        ("currentTime", WCHAR * 15),
        ("lastTime", WCHAR * 15),
        ("bestTime", WCHAR * 15),
        ("split", WCHAR * 15),
        ("completedLaps", c_int32),
        ("position", c_int32),
        ("iCurrentTime", c_int32),
        ("iLastTime", c_int32),
        ("iBestTime", c_int32),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isInPit", c_int32),
        ("currentSectorIndex", c_int32),
        ("lastSectorTime", c_int32),
        ("numberOfLaps", c_int32),
        ("tyreCompound", WCHAR * 33),
        ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float),
        ("activeCars", c_int32),
        ("carCoordinates", c_float * 60 * 3),
        ("carID", c_int32 * 60),
        ("playerCarID", c_int32),
        ("penaltyTime", c_float),
        ("flag", c_int32),
        ("penalty", c_int32),
        ("idealLineOn", c_int32),
        ("isInPitLane", c_int32),
        ("surfaceGrip", c_float),
        ("mandatoryPitDone", c_int32),
        ("windSpeed", c_float),
        ("windDirection", c_float),
        ("isSetupMenuVisible", c_int32),
        ("mainDisplayIndex", c_int32),
        ("secondaryDisplayIndex", c_int32),
        ("TC", c_int32),
        ("TCCut", c_int32),
        ("EngineMap", c_int32),
        ("ABS", c_int32),
        ("fuelXLap", c_float),
        ("rainLights", c_int32),
        ("flashingLights", c_int32),
        ("lightsStage", c_int32),
        ("exhaustTemperature", c_float),
        ("wiperLV", c_int32),
        ("DriverStintTotalTimeLeft", c_int32),
        ("DriverStintTimeLeft", c_int32),
        ("rainTyres", c_int32),
        ("sessionIndex", c_int32),
        ("usedFuel", c_float),
        ("deltaLapTime", WCHAR * 15),
        ("iDeltaLapTime", c_int32),
        ("estimatedLapTime", WCHAR * 15),
        ("iEstimatedLapTime", c_int32),
        ("isDeltaPositive", c_int32),
        ("iSplit", c_int32),
        ("isValidLap", c_int32),
        ("fuelEstimatedLaps", c_float),
        ("trackStatus", WCHAR * 33),
        ("missingMandatoryPits", c_int32),
        ("Clock", c_float),
        ("directionLightsLeft", c_int32),
        ("directionLightsRight", c_int32),
        ("GlobalYellow", c_int32),
        ("GlobalYellow1", c_int32),
        ("GlobalYellow2", c_int32),
        ("GlobalYellow3", c_int32),
        ("GlobalWhite", c_int32),
        ("GlobalGreen", c_int32),
        ("GlobalChequered", c_int32),
        ("GlobalRed", c_int32),
        ("mfdTyreSet", c_int32),
        ("mfdFuelToAdd", c_float),
        ("mfdTyrePressureLF", c_float),
        ("mfdTyrePressureRF", c_float),
        ("mfdTyrePressureLR", c_float),
        ("mfdTyrePressureRR", c_float),
        ("trackGripStatus", c_int32),
        ("rainIntensity", c_int32),
        ("rainIntensityIn10min", c_int32),
        ("rainIntensityIn30min", c_int32),
        ("currentTyreSet", c_int32),
        ("strategyTyreSet", c_int32),
        ("gapAhead", c_int32),
        ("gapBehind", c_int32),
    ]


class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", WCHAR * 15),
        ("acVersion", WCHAR * 15),
        ("numberOfSessions", c_int32),
        ("numCars", c_int32),
        ("carModel", WCHAR * 33),
        ("track", WCHAR * 33),
        ("playerName", WCHAR * 33),
        ("playerSurname", WCHAR * 33),
        ("playerNick", WCHAR * 33),
        ("sectorCount", c_int32),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int32),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", c_float * 4),
        ("tyreRadius", c_float * 4),
        ("maxTurboBoost", c_float),
        ("deprecated_1", c_float),
        ("deprecated_2", c_float),
        ("penaltiesEnabled", c_int32),
        ("aidFuelRate", c_float),
        ("aidTireRate", c_float),
        ("aidMechanicalDamage", c_float),
        ("aidAllowTyreBlankets", c_int32),
        ("aidStability", c_float),
        ("aidAutoClutch", c_int32),
        ("aidAutoBlip", c_int32),
        ("hasDRS", c_int32),
        ("hasERS", c_int32),
        ("hasKERS", c_int32),
        ("kersMaxJ", c_float),
        ("engineBrakeSettingsCount", c_int32),
        ("ersPowerControllerCount", c_int32),
        ("trackSPlineLength", c_float),
        ("trackConfiguration", WCHAR * 33),
        ("ersMaxJ", c_float),
        ("isTimedRace", c_int32),
        ("hasExtraLap", c_int32),
        ("carSkin", WCHAR * 33),
        ("reversedGridPositions", c_int32),
        ("PitWindowStart", c_int32),
        ("PitWindowEnd", c_int32),
        ("isOnline", c_int32),
        ("dryTyresName", WCHAR * 33),
        ("wetTyresName", WCHAR * 33),
    ]


def _wchar_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, bytes)):
        return str(value).rstrip("\x00 ").strip()
    try:
        return "".join(value).rstrip("\x00 ").strip()
    except TypeError:
        return str(value)


def open_shared_memory(tag: str, structure: type[ctypes.Structure]):
    """Return a Structure view of a Windows file mapping, or None if unavailable."""
    if sys.platform != "win32":
        return None, None
    import mmap

    size = ctypes.sizeof(structure)
    try:
        buf = mmap.mmap(-1, size, tagname=tag)
    except (OSError, ValueError, BufferError):
        return None, None
    return structure.from_buffer(buf), buf


def read_static_identity(static: SPageFileStatic) -> tuple[str, str]:
    track = _wchar_str(static.track).lower().replace(" ", "_") or "unknown"
    car = _wchar_str(static.carModel).lower().replace(" ", "_") or "unknown"
    return track, car