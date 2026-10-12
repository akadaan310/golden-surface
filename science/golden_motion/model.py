"""Complex analytic acoustic signals in SI units, never physical acquisition.

The quasi-static moving-scatterer approximation evaluates bistatic path length at
receive time. It neglects scatterer displacement during flight (v/c << 1),
transducer response, diffraction, AGC, clock offset, and target deformation.
"""
from dataclasses import dataclass
import numpy as np
from scipy.signal import correlate, correlation_lags


@dataclass(frozen=True)
class AcousticConfig:
    sample_rate_hz: float = 96000
    sound_speed_m_s: float = 343.0
    carrier_hz: float = 18000.0
    bandwidth_hz: float = 6000.0
    pulse_duration_s: float = .004
    receive_duration_s: float = .02
    noise_std: float = .015
    speaker_m: tuple = (0., 0., 0.)
    microphone_m: tuple = (0., 0., 0.)
    leakage_gain: float = 0.
    clock_offset_s: float = 0.
    clock_rate_error: float = 0.
    min_range_m: float = .03
    max_range_m: float = .8

    def __post_init__(self):
        scalars = [self.sample_rate_hz, self.sound_speed_m_s, self.carrier_hz,
                   self.bandwidth_hz, self.pulse_duration_s, self.receive_duration_s,
                   self.noise_std, self.leakage_gain, self.clock_offset_s, self.clock_rate_error,
                   self.min_range_m, self.max_range_m]
        if not np.isfinite(scalars).all():
            raise ValueError('configuration must be finite')
        if (self.sound_speed_m_s <= 0 or self.pulse_duration_s <= 0 or
            self.receive_duration_s <= self.pulse_duration_s or self.noise_std < 0 or
            self.carrier_hz <= self.bandwidth_hz/2 or self.bandwidth_hz <= 0 or
            self.sample_rate_hz <= 2*(self.carrier_hz+self.bandwidth_hz/2) or
            not 0 <= self.min_range_m < self.max_range_m or abs(self.clock_rate_error)>.01):
            raise ValueError('invalid acoustic configuration')
        _vector(self.speaker_m); _vector(self.microphone_m)


@dataclass
class Signal:
    time_s: np.ndarray
    received: np.ndarray
    transmitted: np.ndarray
    path_length_m: np.ndarray
    source: str = 'synthetic'


def _vector(value):
    value = np.asarray(value, dtype=float)
    if value.shape != (3,) or not np.isfinite(value).all():
        raise ValueError('expected finite three-dimensional vector')
    return value


def bistatic_path(position, speaker, microphone):
    p, s, m = _vector(position), _vector(speaker), _vector(microphone)
    a, b = p-s, p-m
    da, db = np.linalg.norm(a), np.linalg.norm(b)
    if min(da, db) <= 1e-8:
        raise ValueError('scatterer cannot coincide with transducer')
    return float(da+db), a/da+b/db


def _chirp(time_s, cfg):
    u = np.asarray(time_s)
    inside = (u >= 0) & (u <= cfg.pulse_duration_s)
    envelope = np.where(inside, np.sin(np.pi*u/cfg.pulse_duration_s)**2, 0.)
    phase = 2*np.pi*((cfg.carrier_hz-cfg.bandwidth_hz/2)*u +
                     cfg.bandwidth_hz/(2*cfg.pulse_duration_s)*u*u)
    return envelope*np.exp(1j*phase)


def _trajectory_paths(position, velocity, time_s, cfg):
    p, v = _vector(position), _vector(velocity)
    bistatic_path(p,cfg.speaker_m,cfg.microphone_m)
    trajectory = p[None,:] + time_s[:,None]*v[None,:]
    a = np.linalg.norm(trajectory-np.asarray(cfg.speaker_m), axis=1)
    b = np.linalg.norm(trajectory-np.asarray(cfg.microphone_m), axis=1)
    return a+b, .04/np.maximum(a*b, 1e-10)


def simulate_echo(position, velocity, cfg=None, *, seed=0, reflections=(), hand_present=True):
    cfg = cfg or AcousticConfig()
    t = np.arange(round(cfg.receive_duration_s*cfg.sample_rate_hz))/cfg.sample_rate_hz
    path, amplitude = _trajectory_paths(position, velocity, t, cfg)
    tx = _chirp(t, cfg)
    received = np.zeros_like(tx)
    if hand_present:
        for extra, gain in [(0.,1.), *reflections]:
            if not np.isfinite([extra,gain]).all() or extra < 0:
                raise ValueError('reflections require finite nonnegative excess path')
            u = t*(1+cfg.clock_rate_error)-(path+extra)/cfg.sound_speed_m_s-cfg.clock_offset_s
            received += gain*amplitude*_chirp(u,cfg)
    baseline = np.linalg.norm(np.asarray(cfg.speaker_m)-np.asarray(cfg.microphone_m))
    received += cfg.leakage_gain*_chirp(t*(1+cfg.clock_rate_error)-baseline/cfg.sound_speed_m_s,cfg)
    rng = np.random.default_rng(seed)
    received += cfg.noise_std/np.sqrt(2)*(rng.normal(size=len(t))+1j*rng.normal(size=len(t)))
    return Signal(t,received,tx,path)


def _validate_signal(signal):
    arrays=[np.asarray(signal.time_s),np.asarray(signal.received),np.asarray(signal.transmitted),np.asarray(signal.path_length_m)]
    if (any(a.ndim!=1 for a in arrays) or len(arrays[0])<3 or
        any(a.shape!=arrays[0].shape or not np.isfinite(a).all() for a in arrays) or
        not np.all(np.diff(arrays[0])>0)):
        raise ValueError('signal samples must be finite, matching and time ordered')


def estimate_delay(signal, cfg=None, *, background=None):
    """Strongest matched-filter peak; returns scalar equivalent half-path only.

    A strong reflected path may win. Confidence is normalized signal correlation,
    a heuristic rather than a calibrated probability. Clock offset is assumed 0.
    """
    cfg = cfg or AcousticConfig()
    _validate_signal(signal)
    received=signal.received
    if background is not None:
        recorded=background.received if isinstance(background,Signal) else np.asarray(background)
        if recorded.shape!=received.shape or not np.isfinite(recorded).all():
            raise ValueError('background must match finite receive samples')
        received=received-recorded
    corr = correlate(received, signal.transmitted, mode='full', method='fft')
    lags = correlation_lags(len(signal.received),len(signal.transmitted))
    valid = (lags >= 2*cfg.min_range_m/cfg.sound_speed_m_s*cfg.sample_rate_hz) & (lags <= 2*cfg.max_range_m/cfg.sound_speed_m_s*cfg.sample_rate_hz)
    indices = np.flatnonzero(valid)
    if not len(indices):
        raise ValueError('empty delay search')
    peak = int(indices[np.argmax(np.abs(corr[indices]))])
    magnitude = np.abs(corr)
    delta = 0.
    if 0 < peak < len(corr)-1:
        y0,y1,y2 = magnitude[peak-1:peak+2]
        denominator = y0-2*y1+y2
        if abs(denominator) > 1e-20:
            delta = float(np.clip(.5*(y0-y2)/denominator,-.5,.5))
    delay = (lags[peak]+delta)/cfg.sample_rate_hz
    norm = np.linalg.norm(received)*np.linalg.norm(signal.transmitted)
    coherence = float(magnitude[peak]/norm) if norm > 1e-20 else 0.
    return {'valid': coherence >= .3, 'delay_s':float(delay),
            'range_m':float(delay*cfg.sound_speed_m_s/2),
            'confidence':float(np.clip(coherence,0,1)),
            'coordinate_frame':'measurement-space','measurement_kind':'equivalent-half-path',
            'bandwidth_resolution_m':float(cfg.sound_speed_m_s/(2*cfg.bandwidth_hz)),
            'background_subtracted':background is not None,
            'peak_index':int(lags[peak])}


def simulate_tone(position, velocity, cfg=None, *, seed=0, duration_s=.12, hand_present=True, reflections=()):
    cfg = cfg or AcousticConfig()
    if not 0 < duration_s <= 1:
        raise ValueError('tone duration must be in (0,1] seconds')
    t = np.arange(round(duration_s*cfg.sample_rate_hz))/cfg.sample_rate_hz
    path, amplitude = _trajectory_paths(position,velocity,t,cfg)
    tx = np.exp(2j*np.pi*cfg.carrier_hz*t)
    received = np.zeros_like(tx)
    if hand_present:
        for extra,gain in [(0.,1.),*reflections]:
            received += gain*amplitude*np.exp(2j*np.pi*cfg.carrier_hz*(t*(1+cfg.clock_rate_error)-(path+extra)/cfg.sound_speed_m_s-cfg.clock_offset_s))
    rng = np.random.default_rng(seed)
    received += cfg.noise_std/np.sqrt(2)*(rng.normal(size=len(t))+1j*rng.normal(size=len(t)))
    return Signal(t,received,tx,path)


def estimate_doppler(signal, cfg=None):
    cfg = cfg or AcousticConfig()
    _validate_signal(signal)
    baseband = signal.received*np.conjugate(signal.transmitted)
    phase = np.unwrap(np.angle(baseband))
    slope, intercept = np.polyfit(signal.time_s,phase,1)
    residual = phase-(slope*signal.time_s+intercept)
    fd = float(slope/(2*np.pi))
    return {'frequency_hz':fd,'radial_velocity_m_s':float(-fd*cfg.sound_speed_m_s/(2*cfg.carrier_hz)),
            'phase_residual_rad':float(np.std(residual)),'valid':bool(np.std(residual)<.5),
            'confidence':float(np.exp(-np.std(residual))),
            'coordinate_frame':'measurement-space'}


def phase_displacement(previous, current, cfg=None):
    cfg = cfg or AcousticConfig()
    if not np.isfinite([previous,current]).all() or min(abs(previous),abs(current))<1e-12:
        raise ValueError('phase requires finite nonzero complex samples')
    return float(-np.angle(current*np.conjugate(previous))*cfg.sound_speed_m_s/(4*np.pi*cfg.carrier_hz))


def observability(position, speakers, microphones, velocity=(0.,0.,0.)):
    """Local numerical rank for half-path and half-path derivative measurements."""
    p,v = _vector(position),_vector(velocity)
    speakers,microphones = np.asarray(speakers,dtype=float),np.asarray(microphones,dtype=float)
    if speakers.shape != microphones.shape or speakers.ndim != 2 or speakers.shape[1] != 3:
        raise ValueError('transducer arrays must have matching N x 3 shape')
    def measurements(state):
        ranges=[]; rates=[]
        for s,m in zip(speakers,microphones):
            length,grad=bistatic_path(state[:3],s,m)
            ranges.append(length/2); rates.append(float(grad@state[3:]/2))
        return np.r_[ranges,rates]
    state=np.r_[p,v]; h=1e-6
    jac=np.column_stack([(measurements(state+np.eye(6)[i]*h)-measurements(state-np.eye(6)[i]*h))/(2*h) for i in range(6)])
    pos=jac[:len(speakers),:3]
    sv=np.linalg.svd(jac,compute_uv=False)
    return {'position_rank':int(np.linalg.matrix_rank(pos,tol=1e-7)),
            'state_rank':int(np.linalg.matrix_rank(jac,tol=1e-7)),
            'state_dimension':6,'singular_values':sv.tolist(),
            'jacobian':jac.tolist(),'local_only':True}


def filter_range_velocity(ranges, velocities, dt, range_std=.002, velocity_std=.002):
    """Linear constant-velocity Kalman filter in scalar measurement space."""
    ranges=np.asarray(ranges,dtype=float); velocities=np.asarray(velocities,dtype=float)
    if len(ranges)!=len(velocities) or not len(ranges) or not np.isfinite(np.r_[ranges,velocities,dt,range_std,velocity_std]).all() or min(dt,range_std,velocity_std)<=0:
        raise ValueError('invalid state filter input')
    x=np.array([ranges[0],velocities[0]]); cov=np.diag([range_std**2,velocity_std**2])
    transition=np.array([[1.,dt],[0.,1.]])
    process=.08**2*np.array([[dt**4/4,dt**3/2],[dt**3/2,dt**2]])
    measurement=np.diag([range_std**2,velocity_std**2]); output=[x.copy()]
    for r,v in zip(ranges[1:],velocities[1:]):
        x=transition@x; cov=transition@cov@transition.T+process
        gain=cov@np.linalg.inv(cov+measurement)
        x=x+gain@(np.array([r,v])-x)
        cov=(np.eye(2)-gain)@cov
        output.append(x.copy())
    return np.asarray(output)
