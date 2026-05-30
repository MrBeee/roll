"""
% roll along of basic template for pp-data
%
% input : rs : source coordinate vector
% rr : receiver coordinate vector
% rgs: source array ( rgs=[0;0;0], means no array )
% rgr: receiver array ( rgr=[0;0;0], means no array )
% rt : roll along
% r1 : focal point position vector
% x : array of x-coordinates for which the beam is computed
% y : array of y-coordinates for which the beam is computed
% z : depth at which the beam is evaluated (around the focal point)
% f : frequency (only one freq. component)
% cp : velocity in the medium
% tot: (0/1) if tot =1, the results per template are returned else the sum
% of the separate results is returned
% Np : number of points in the Radon domain [Npx,Npy],(optional) default=128
%
% ouput: x : array of x-coordinates for which the beam is computed
% y : array of y-coordinates for which the beam is computed
% f : array of frequencies frequencies
% Bs : source beam (i,x,y), source beam for each template position
% Br : receiver beam (i,x,y), receiver beam for each template position
% I : resolution function (i,x,y)
% px : slowness in x-direction
% py : slowness in y-direction
% AVP: AVP-function
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

   Bs = zeros(size(rt,2), length( x), length( y)); % source beam
   Br = zeros(size(rt,2), length( x), length( y)); % receiver beam
   I = zeros(size(rt,2), length( x), length( y)); % resolution function
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
      I (l,:,:) = (Bs1.*Br1).';
      AVP(l,:,:) = ((conj(L2)*Bs1*conj(L1)).*(L2*Br1*L1)).';
   end

else % tot == 0

   Bs = zeros(1, length( x), length( y)); % source beam
   Br = zeros(1, length( x), length( y)); % receiver beam
   I = zeros(1, length( x), length( y)); % resolution function
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
      I (1,:,:) = (squeeze( I(1,:,:)).' + Bs1 .* Br1).';
      AVP(1,:,:) = (squeeze(AVP(1,:,:)).' + (conj(L2) * Bs1 * conj(L1)) .* (L2 * Br1 * L1)).';
   end

end

"""

# Python code here:

import numpy as np
from acq_ftbeam_homogen import \
    acq_ftbeam_homogen  # assumes your first function is in this module


def acq_rolltempl_pp(rs, rr, rgs, rgr, rt, r1, x, y, z, f, cp, tot, Np=None):
    """
    Python translation of MATLAB acq_rolltempl_pp.m
    """

    # -----------------------------
    # Handle Np default
    # -----------------------------
    if Np is None:
        Npx = 128
        Npy = 128
    else:
        Npx = int(Np[0])
        Npy = int(Np[1])

    # -----------------------------
    # Ensure x, y are row vectors
    # -----------------------------
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()

    # -----------------------------
    # Slowness axes
    # -----------------------------
    px = np.linspace(-1.0/cp, 1.0/cp, Npx)
    py = np.linspace(-1.0/cp, 1.0/cp, Npy)

    # -----------------------------
    # Radon transform kernels
    # L1 = exp(i*2*pi*f * x' * px)
    # L2 = exp(i*2*pi*f * py' * y)
    # -----------------------------
    w = 2 * np.pi * f

    L1 = np.exp(1j * w * np.outer(x, px))    # (Nx, Npx)
    L2 = np.exp(1j * w * np.outer(py, y))    # (Npy, Ny)

    # -----------------------------
    # Allocate output arrays
    # -----------------------------
    ntemp = rt.shape[1]
    Nx = len(x)
    Ny = len(y)

    if tot == 1:
        Bs = np.zeros((ntemp, Nx, Ny), dtype=complex)
        Br = np.zeros((ntemp, Nx, Ny), dtype=complex)
        I = np.zeros((ntemp, Nx, Ny), dtype=complex)
        AVP = np.zeros((ntemp, Npx, Npy), dtype=complex)
    else:
        Bs = np.zeros((1, Nx, Ny), dtype=complex)
        Br = np.zeros((1, Nx, Ny), dtype=complex)
        I = np.zeros((1, Nx, Ny), dtype=complex)
        AVP = np.zeros((1, Npx, Npy), dtype=complex)

    # -----------------------------
    # Main loop over template positions
    # -----------------------------
    for l in range(ntemp):

        # Progress message (MATLAB printed every 10)
        if (l % 10) == 0:
            print(f"{100 * (l+1)/ntemp:.1f} % complete")

        # Shift sources & receivers
        rs1 = rs + rt[:, l].reshape(3, 1)
        rr1 = rr + rt[:, l].reshape(3, 1)

        # Compute beams
        _, _, _, Bs1 = acq_ftbeam_homogen(rs1, rr1, rgs, rgr, r1, x, y, z, f, cp, 1, 0, 1)
        _, _, _, Br1 = acq_ftbeam_homogen(rs1, rr1, rgs, rgr, r1, x, y, z, f, cp, 2, 0, 1)

        # Bs1, Br1 are (Ny, Nx) in your translated function → transpose to (Nx, Ny)
        Bs1 = Bs1.T
        Br1 = Br1.T

        # -----------------------------
        # tot == 1 → store each template separately
        # -----------------------------
        if tot == 1:
            Bs[l, :, :] = Bs1
            Br[l, :, :] = Br1
            I[l, :, :] = Bs1 * Br1

            # AVP = ((conj(L2)*Bs1*conj(L1)) .* (L2*Br1*L1)).'
            term1 = (np.conj(L2) @ Bs1 @ np.conj(L1))
            term2 = (L2 @ Br1 @ L1)
            AVP[l, :, :] = (term1 * term2).T

        # -----------------------------
        # tot == 0 → accumulate sum
        # -----------------------------
        else:
            Bs[0, :, :] += Bs1
            Br[0, :, :] += Br1
            I[0, :, :] += Bs1 * Br1

            term1 = (np.conj(L2) @ Bs1 @ np.conj(L1))
            term2 = (L2 @ Br1 @ L1)
            AVP[0, :, :] += (term1 * term2).T

    return x, y, f, Bs, Br, I, px, py, AVP
