# Scientific substrate and interaction semantics

The generalized model is `y_m(t) = F_m(x(t), e(t), u_m(t), θ_m) + ε_m(t)`.
Each executable experiment declares its forward model, sampling, geometry,
reflector model, estimator and negative controls. A numerical model can be
internally consistent and still disagree with the physical phone.

In discrete time, `x[n+1] = f(x[n], u[n]) + w[n]` and
`y_m[n] = h_m(x[n], e[n], θ_m) + v_m[n]`. Local identifiability depends on
the measurement Jacobian. For Gaussian observations, information is
`Jᵀ Σ⁻¹ J`; a singular matrix does not provide finite position bounds in
unobservable directions. Delay at one speaker/microphone yields a bistatic
path-length constraint; phase wraps and Doppler only describe path variation.
Single-link RSSI is coarsely quantized strength, not complex CSI or depth.

An implicit surface is `S={x:φ(x)=0}` and its interior is
`Z={x:φ(x)≤0}`. Sphere zones use `φ(x)=||x−c||−r`. Where position is absent,
zones are intervals of an explicitly named measurement. Membership estimates
are quality heuristics until physical confidence calibration is measured.

## Coordinate and clock contract

| Frame | Units | Available information |
| --- | --- | --- |
| `phone-local-m` | m, m/s | Synthetic/reference geometry; measured XYZ only with independent supporting calibration |
| `camera-image-normalized` | fraction of image width/height | Image-plane hand location; no measured depth |
| `measurement-space` | `relative.unit` | Named scalar feature; no inferred 3D hand coordinates |

Events use Unix epoch milliseconds. Replay records original timestamps and
source; rendered playback time is a separate transport clock. Cross-device
timestamps require clock alignment before latency claims. A timestamp and a
relay sequence do not prove synchronized sensor clocks. Position uncertainty
is marginal standard deviation, not covariance; scalar uncertainty uses the
feature's stated unit. Confidence is bounded [0,1] and denotes input quality,
not a validated probability of correct action unless a calibration experiment
explicitly establishes that result.

Intent gates selection, scrolling and manipulation; dwell, dead bands,
hysteresis and cooldown suppress repeated actions. Sensor dropout releases
interaction state. Motion presence remains motion presence if direction or
surface membership cannot be resolved.

## IVR and VIR

IVR (Immersive Virtual Reality) and VIR (Virtual Immersive Reality) remain
provisional project terms. Operationally, physical/reference measurements
map to a controlled virtual scene through a declared frame transform and
observable degrees of freedom. “IVR through VIR” describes a physical-to-virtual
interaction mapping; “VIR through IVR” describes virtual feedback guiding a
physical interaction region. These labels do not establish different physics
or a six-degree-of-freedom sensor. The object/avatar demonstration is independent
of any game SDK; GTA VI is only a possible future integration target.
