# Independent Julia acoustic kernels. Standard library only; no Python execution.
using LinearAlgebra, DelimitedFiles
out = ARGS[1]
c=343.0; fs=96000.0; fc=18000.0; bandwidth=6000.0; duration=.004
p=[.10,.15,.23]; v=[.01,-.02,.06]
t=collect(0:1919)./fs
function chirp(u)
    (u<0 || u>duration) && return 0.0+0.0im
    sin(pi*u/duration)^2*exp(2pi*im*((fc-bandwidth/2)*u+bandwidth/(2duration)*u*u))
end
tx=chirp.(t)
received=ComplexF64[]
for instant in t
    current=p+v*instant
    distance=norm(current)
    push!(received,.04/(distance^2)*chirp(instant-2distance/c))
end
writedlm(joinpath(out,"julia-echo.csv"),hcat(real(received),imag(received)),',')
# Direct correlation independently implements positive-delay matched filtering.
lags=collect(ceil(Int,2*.03/c*fs):floor(Int,2*.8/c*fs))
correlation=Float64[]
for lag in lags
    value=0.0+0.0im
    for j in 1:(length(t)-lag)
        value += received[j+lag]*conj(tx[j])
    end
    push!(correlation,abs(value))
end
peak=argmax(correlation)
y0,y1,y2=correlation[peak-1:peak+1]
delta=clamp(.5*(y0-y2)/(y0-2y1+y2),-.5,.5)
range=(lags[peak]+delta)/fs*c/2
coherence=correlation[peak]/(norm(received)*norm(tx))
# Tone phase slope is fitted without any supplied truth velocity value.
ttone=collect(0:2399)./fs
baseband=[exp(-2pi*im*fc*(2norm(p+v*instant))/c) for instant in ttone]
phase=angle.(baseband)
for i in 2:length(phase)
    phase[i]+=2pi*round((phase[i-1]-phase[i])/(2pi))
end
centered=ttone.-sum(ttone)/length(ttone)
slope=dot(centered,phase.-sum(phase)/length(phase))/dot(centered,centered)
fd=slope/(2pi)
displacement=-angle(exp(-2pi*im*fc*(2*.401)/c)*conj(exp(-2pi*im*fc*(2*.4)/c)))*c/(4pi*fc)
# Static array range Jacobian and local state rank.
anchors=[0.0 0.0 0.0; .4 0 0; 0 .4 0; 0 0 .4]
jac=zeros(4,3)
for i in 1:4
    d=p-anchors[i,:]
    jac[i,:]=d/norm(d)
end
statejac=[jac zeros(4,3);zeros(4,3) jac]
result=vcat([2norm(p)],2p/norm(p),[range,coherence,fd,-fd*c/(2fc),displacement,rank(jac),rank(statejac)])
writedlm(joinpath(out,"julia-scalars.csv"),result,',')
println("Independent Julia kernels complete: ",length(received)," samples, ",length(result)," scalar outputs.")
