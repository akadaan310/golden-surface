# Independent Julia complex CSI forward calculation (not generated from Python).
using LinearAlgebra
const c=299792458.0
const fc=5.2e9
const tx=[0.0,0.0,0.0]
for t in [0.0,0.1,0.3], a in 0:1, k in 0:2
 rx=[1.0+a*c/fc/2,0.0,0.0]
 f=fc+(k-1)*312500
 p=[.5,.55+.15*t,.15]
 sp=[1.0,.9,.4]
 h=exp(-2im*pi*f*norm(rx-tx)/c)
 h+=.25*exp(-2im*pi*f*(norm(sp-tx)+norm(sp-rx))/c)
 h+=.55*exp(-2im*pi*f*(norm(p-tx)+norm(p-rx))/c)
 h*=exp(2im*pi*(22*t+(f-fc)*8e-6*t))
 println(join(["CSI",t,a,k,real(h),imag(h)],","))
end
println("RSSI,",10^((-40-(-47.22471989593555))/(10*2.4)))
p=[.5,.5,.2];rx=[1.,0.,0.];j=(p-tx)/norm(p-tx)+(p-rx)/norm(p-rx)
println("RANK,",rank(reshape(j,1,3)))
