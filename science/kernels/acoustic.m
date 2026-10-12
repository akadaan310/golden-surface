% Independent GNU Octave acoustic kernels. No Python execution or signal toolbox.
args=argv(); out=args{1};
c=343.0; fs=96000.0; fc=18000.0; bandwidth=6000.0; duration=.004;
p=[.10;.15;.23]; v=[.01;-.02;.06];
t=(0:1919)'/fs;
chirp_fn=@(u) ((u>=0)&(u<=duration)).*sin(pi*u/duration).^2.*exp(2*pi*1i*((fc-bandwidth/2)*u+bandwidth/(2*duration)*u.^2));
tx=chirp_fn(t); current=p'+t*v'; distance=sqrt(sum(current.^2,2));
received=.04./distance.^2.*chirp_fn(t-2*distance/c);
csvwrite(fullfile(out,'octave-echo.csv'),[real(received),imag(received)]);
% Independent full convolution definition of matched filter.
correlation=conv(received,flipud(conj(tx)));
lags=(ceil(2*.03/c*fs):floor(2*.8/c*fs))';
values=abs(correlation(length(t)+lags));
[~,peak]=max(values); y0=values(peak-1);y1=values(peak);y2=values(peak+1);
delta=min(.5,max(-.5,.5*(y0-y2)/(y0-2*y1+y2)));
range=(lags(peak)+delta)/fs*c/2;
coherence=values(peak)/(norm(received)*norm(tx));
ttone=(0:2399)'/fs; distance=sqrt(sum((p'+ttone*v').^2,2));
phase=unwrap(angle(exp(-2*pi*1i*fc*(2*distance)/c)));
centered=ttone-mean(ttone); slope=sum(centered.*(phase-mean(phase)))/sum(centered.^2);
fd=slope/(2*pi);
displacement=-angle(exp(-2*pi*1i*fc*(2*.401)/c)*conj(exp(-2*pi*1i*fc*(2*.4)/c)))*c/(4*pi*fc);
anchors=[0 0 0;.4 0 0;0 .4 0;0 0 .4]; jac=zeros(4,3);
for i=1:4
 d=p-anchors(i,:)';jac(i,:)=d'/norm(d);
end
statejac=[jac zeros(4,3);zeros(4,3) jac];
result=[2*norm(p);2*p/norm(p);range;coherence;fd;-fd*c/(2*fc);displacement;rank(jac);rank(statejac)];
csvwrite(fullfile(out,'octave-scalars.csv'),result);
printf('Independent Octave kernels complete: %d samples, %d scalar outputs.\n',length(received),length(result));
