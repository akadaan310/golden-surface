% Independent Octave model: geometry -> electrical delay -> complex CSI.
c=299792458; fc=5.2e9; tx=[0,0,0];
for t=[0,.1,.3]
 for a=0:1
  rx=[1+a*c/fc/2,0,0];
  for k=0:2
   f=fc+(k-1)*312500; p=[.5,.55+.15*t,.15];sp=[1,.9,.4];
   h=exp(-2i*pi*f*norm(rx-tx)/c);
   h=h+.25*exp(-2i*pi*f*(norm(sp-tx)+norm(sp-rx))/c);
   h=h+.55*exp(-2i*pi*f*(norm(p-tx)+norm(p-rx))/c);
   h=h*exp(2i*pi*(22*t+(f-fc)*8e-6*t));
   fprintf('CSI,%.17g,%d,%d,%.17g,%.17g\n',t,a,k,real(h),imag(h));
  end
 end
end
fprintf('RSSI,%.17g\n',10^((-40-(-47.22471989593555))/(10*2.4)));
p=[.5,.5,.2];rx=[1,0,0];j=(p-tx)/norm(p-tx)+(p-rx)/norm(p-rx);
fprintf('RANK,%d\n',sum(svd(j)>1e-8));
