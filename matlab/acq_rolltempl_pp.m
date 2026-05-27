% roll along of basic template for pp-data
%
% input : rs : source coordinate vector
%         rr : receiver coordinate vector
%         rgs: source array ( rgs=[0;0;0], means no array )
%         rgr: receiver array ( rgr=[0;0;0], means no array )
%         rt : roll along
%         r1 : focal point position vector
%         x  : array of x-coordinates for which the beam is computed
%         y  : array of y-coordinates for which the beam is computed
%         z  : depth at which the beam is evaluated (around the focal point)
%         f  : frequency (only one freq. component)
%         cp : velocity in the medium
%         tot: (0/1) if tot =1, the results per template are returned else the sum
%				 	of the separate results is returned
%         Np : number of points in the Radon domain [Npx,Npy],(optional) default=128
%
% ouput: x  : array of x-coordinates for which the beam is computed
%        y  : array of y-coordinates for which the beam is computed
%        f  : array of frequencies frequencies
%        Bs : source beam (i,x,y), source beam for each template position
%        Br : receiver beam (i,x,y), receiver beam for each template position
%        I  : resolution function (i,x,y)
%        px : slowness in x-direction
%        py : slowness in y-direction
%        AVP: AVP-function
%
%
% usage : [x,y,f,Bs,Br,I,px,py,AVP]=acq_rolltempl_pp(rs,rr,rgs,rgr,rt,r1,x,y,z,f,cp,tot,Np);
%
%
%--------------------------------------------------------------------------------------------------

% by A. Volker
% 22-12-99

function [x, y, f, Bs, Br, I, px, py, AVP] = acq_rolltempl_pp(rs, rr, rgs, rgr, rt, r1, x, y, z, f, cp, tot, Np);


if nargin < 13
   Npx = 128;
   Npy = 128;
else
   Npx = Np(1);
   Npy = Np(2);
end

% check input arrays
if size(x,2) == 1 && length(x) > 1
   disp(['Warning: x should be a row vector']);
   x = x.';
end

if size(y,2) == 1 && length(y) > 1
   disp(['Warning: y should be a row vector']);
   y = y.';
end

px = -1./cp : 2./(cp.*(Npx-1)) : 1./cp;
py = -1./cp : 2./(cp.*(Npy-1)) : 1./cp;

% Radon transform;
L1 = exp(i*2*pi*f * x' * px);
L2 = exp(i*2*pi*f * py' * y);

if tot == 1

   Bs  = zeros(size(rt,2), length( x), length( y)); % source beam
   Br  = zeros(size(rt,2), length( x), length( y)); % receiver beam
   I   = zeros(size(rt,2), length( x), length( y)); % resolution function
   AVP = zeros(size(rt,2), length(px), length(py)); % AVP-function

   lmax = size(rt, 2);
   for l=1:lmax
      if rem(l,10)
          disp([num2str(l./size(rt,2)*100,3),' complete']);
      end

      rs1=rs+rt(:,l)*ones(1,size(rs,2));
      rr1=rr+rt(:,l)*ones(1,size(rr,2));

      [x,y,f,Bs1]=acq_ftbeam_homogen(rs1,rr1,rgs,rgr,r1,x,y,z,f,cp,1,0,1);
      [x,y,f,Br1]=acq_ftbeam_homogen(rs1,rr1,rgs,rgr,r1,x,y,z,f,cp,2,0,1);

      Bs (l,:,:) = Bs1.';
      Br (l,:,:) = Br1.';
      I  (l,:,:) = (Bs1.*Br1).';
      AVP(l,:,:) = ((conj(L2)*Bs1*conj(L1)).*(L2*Br1*L1)).';
   end

else    % tot == 0

   Bs  = zeros(1, length( x), length( y)); % source beam
   Br  = zeros(1, length( x), length( y)); % receiver beam
   I   = zeros(1, length( x), length( y)); % resolution function
   AVP = zeros(1, length(px), length(py)); % AVP-function

   lmax = size(rt, 2);
   for l = 1:lmax
      if rem(l,10)
          disp(['Analysis points ', num2str(l ./ lmax * 100, 3),' % complete']);
      end

      rs1 = rs + rt(:, l) * ones(1, size(rs, 2)); % shift the sources to template position l
      rr1 = rr + rt(:, l) * ones(1, size(rr, 2)); % shift the receivers to template position l

      [x,y,f,Bs1] = acq_ftbeam_homogen(rs1, rr1, rgs, rgr, r1, x, y, z, f, cp, 1, 0, 1);
      [x,y,f,Br1] = acq_ftbeam_homogen(rs1, rr1, rgs, rgr, r1, x, y, z, f, cp, 2, 0, 1);

      Bs (1,:,:) = (squeeze( Bs(1,:,:)).' + Bs1).';
      Br (1,:,:) = (squeeze( Br(1,:,:)).' + Br1).';
      I  (1,:,:) = (squeeze(  I(1,:,:)).' + Bs1 .* Br1).';
      AVP(1,:,:) = (squeeze(AVP(1,:,:)).' + (conj(L2) * Bs1 * conj(L1)) .* (L2 * Br1 * L1)).';
   end

end
