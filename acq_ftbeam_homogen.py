"""
% beam computation by fourier transformation (homogeneous medium)
%
%
% input: rs : source coordinate vector
% rr : receiver coordinate vector
% rgs: source array ( rgs=[0;0;0], means no array )
% rgr: receiver array ( rgr=[0;0;0], means no array )
% r1 : focal point position vector
% x : array of x-coordinates for which the beam is computed
% y : array of y-coordinates for which the beam is computed
% z : depth at which the beam is evaluated (around the focal point)
% f : array of frequencies
% c : velocity in the medium
% btype : beam type (1 source beam /2 receiver beam)
% sc : scale (0/1) scale receiver beam with distance of source-target and vice versa
% normally no scaling is used (sc = 0)
% opt: real(0) of complex(1) output of the data (default = real (0))
% s : optional, wavelet in frequency domain, array with same size as f
%
% [x,y,f,B]=acq_ftbeam_homogen(rs,rr,rgs,rgr,r1,x,y,z,f,c,btype,sc,opt,s);
%
% ouput: x : array of x-coordinates for which the beam is computed
% y : array of y-coordinates for which the beam is computed
% f : array of frequencies
% B : beam (f,x,y)
%
%--------------------------------------------------------------------------------------------------

% by A. Volker
% 06-10-99

function [x,y,f,B]=acq_ftbeam_homogen(rs,rr,rgs,rgr,r1,x,y,z,f,c,btype,sc,opt,s);

if nargin<13
   disp(['ouput data is real']);
   opt=0;
end

if nargin < 14
   s = ones(size(f)); % creates a N x N array of all ones
else
   if size(s) ~= size(f),
      disp(['Error: size of wavelet "s" should be the same as the frequency axis']);
      return;
   end
end

% test if source arrays are applied
if size(rgs,2) == 1 && rgs(1,1) == 0 && rgs(2,1) == 0 && rgs(3,1) == 0 % Bart, modified last & was missing
   sourcearray = 0;
else
   sourcearray = 1;
end

% test if source arrays are applied
if size(rgr,2) == 1 && rgr(1,1) == 0 && rgr(2,1) == 0 && rgr(3,1) == 0 % Bart, modified last & was missing
   receiverarray = 0;
else
   receiverarray = 1;
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

% define
src = 1;
rec = 2;

xs = rs(1,:);
ys = rs(2,:);
zs = rs(3,:);
lxs = length(xs);

xr = rr(1,:);
yr = rr(2,:);
zr = rr(3,:);
lxr = length(xr);

if sourcearray == 1
   xgs = rgs(1,:);
   ygs = rgs(2,:);
   zgs = rgs(3,:);
   lxgs = length(xgs);
end

if receiverarray == 1
   xgr = rgr(1,:);
   ygr = rgr(2,:);
   zgr = rgr(3,:);
   lxgr = length(xgr);
end

x1 = r1(1,:);
y1 = r1(2,:);
z1 = r1(3,:);

Rs = sqrt( (xs - x1).^2 + (ys - y1).^2 + (zs - z1).^2 );
Rr = sqrt( (xr - x1).^2 + (yr - y1).^2 + (zr - z1).^2 );

p = 1.0 / c;

% compute src slowness
psx = p * (xs-x1) ./ Rs;
psy = p * (ys-y1) ./ Rs;
psz = p * ( z-z1) ./ Rs;

% compute rec slowness
prx = p * (xr-x1) ./ Rr;
pry = p * (yr-y1) ./ Rr;
prz = p * ( z-z1) ./ Rr;

% Jacobian of the transformation
Js = (zs - z1) .^ 2 ./ Rs .^ 4;
Jr = (zr - z1) .^ 2 ./ Rr .^ 4;

f_len = length(f);
x_len = length(x);
y_len = length(y);

B = zeros(f_len, y_len, x_len);

% scale factor "Het touwtje van Leo"
if sc == 0,
   scale = ones(1, length(f)) ./ (4 * pi .^ 2);
else
   switch(btype)
   case(src)
      scale = sum(Jr) ./ (4*pi .^ 2) .* ones(1,length(f));
   case(rec)
      scale = sum(Js) ./ (4*pi .^ 2) .* ones(1,length(f));
   end
end

switch(btype)

case(src)
   for l = 1:length(f) % loop over frequencies
      w = 2 * pi * f(l); % wavenumber
      x_px = exp(i.* w.* x' * psx);
      py_y = exp(i.* w.* psy' * y);

      if sourcearray == 1

          for ll = 1 : length(psx)
            % xgs and ygs are the x & y source pattern locations
            Ssg(ll) = sum( exp(i .* w .* psx(ll) .* xgs) .* exp(i .* w .* ygs .* psy(ll)) );
          end

          Ssg = diag(Ssg) ./ length(xgs);

          if z1 ~= z
              W1 = psx.'.^2 * ones(1,length(psy));
              W2 = ones(length(psx),1) * psy.^2;
              Wt = exp(i*w*sqrt(1./c.^2 - W1 - W2).* (z1-z));
              Ssg = Ssg .* Wt;
         end

         % source beam
         B(l,:,:) = (s(l).*(scale(l)*(ones(length(x),1)*(Js.*(p.*w).^2)).* x_px) * Ssg * py_y).';
      else
         if z1 ~= z
            W1 = psx.'.^2 * ones(1,length(psy));
            W2 = ones(length(psx),1) * psy.^2;

            Wt = exp(i*w*sqrt( 1./c.^2 - W1 - W2).* (z1 - z) ); % phase rotation due to z1 != z
% Wt = exp(i*w*sqrt( 1./c.^2 - psx.'.^2*ones(1,length(psy)) - ones(length(psx),1)*psy.^2 ).*(z1 - z));

            B(l,:,:) = s(l).*(scale(l)*(ones(length(x),1)*(Js.*(p.*w).^2)).*(exp(i.*w.*x'*psx)) * Wt * (exp(i.*w.*psy'*y))).';
         else
            Wf = scale(l).* s(l); % all frequency scaling here
            Ws = Js.*(p.*w).^2; % all spatial scaling here
            Wt = Ws.* Wf; % combine all scaling factors
            Wt = diag(Wt); % needs to fit 'in the middle' of multiplication
                                        % therefore create a diagonal matrix from row

            B(l,:,:) = (x_px * Wt * py_y).';
% B(l,:,:) = (s(l).*(scale(l)*(ones(length(x),1)*(Js.*(p.*w).^2)).*(exp(i.*w.*x'*psx)))*( exp(i.*w.*psy'*y))).';
         end
      end
   end

case(rec)
   for l = 1:length(f) % loop over frequencies
      w = 2*pi*f(l); % wavenumber
      x_px = exp(i.* w.* x' * prx);
      py_y = exp(i.* w.* pry' * y);

      if receiverarray == 1
         % geophone array response at the present wavenumber

         % componenents.
         for ll = 1:length(prx)
            Srg(ll) = sum(exp(i.*w.*prx(ll).*xgr).*exp(i.*w.*ygr.*pry(ll)));
         end

         Srg = diag(Srg)./length(xgr);

         if z1 ~= z,
            % beam NOT evaluated at target depth
            W = exp(i*w*sqrt(1./c.^2-prx.'.^2*ones(1,length(pry))-ones(length(prx),1)*pry.^2).*(z1-z));
            Srg = Srg.* W;
         end

         % receiver beam
         B(l,:,:) = s(l).*(scale(l) * (ones(length(x),1)*(Jr.*(p.*w).^2)).* x_px * Srg * py_y).';
% B(l,:,:) = s(l).*(scale(l) * (ones(length(x),1)*(Jr.*(p.*w).^2)).*(exp(i.*w.*x'*pr1))*Srg*(exp(i.*w.*pr2'*y))).';
     else
         % receiver beam
         if z1 ~= z
            % beam NOT evaluated at target depth
            W1 = prx.'.^2 * ones(1,length(pry));
            W2 = ones(length(prx),1) * pry.^2;

            Wt = exp(i*w * sqrt(1./c.^2 - W1 - W2) .* (z1 - z) ); % phase rotation due to z1 != z
% Wt = exp(i* w* sqrt(1./c.^2 - prx.'.^2 * ones(1, length(pry)) - ones(length(prx), 1) * pry.^2).* (z1 - z) );
            B(l,:,:) = (s(l).*(scale(l) * (ones(length(x),1)*(Jr.*(p.*w).^2)).* (exp(i.*w.*x'*prx) ) )* Wt *(exp(i.*w.*pry'*y)) ).';
         else
% B(l,:,:) = (s(l).*(scale(l) * (ones(length(x),1)*(Jr.*(p.*w).^2)).* (exp(i.*w.*x'*prx) ) ) * (exp(i.*w.*pry'*y)) ).';

% a = scale(l);
% b = ones(length(x), 1);
% c = Jr.*(p.*w).^2;
% d = exp(i.* w.* x' * prx);
% e = exp(i.* w.* pry' * y);
% B(l,:,:) = (s(l).* (a * (b * c) .*d) * e ).';

            Wf = scale(l).* s(l); % frequency scaling here
            Ws = Jr.*(p.*w).^2; % spatial scaling here
            Wt = Ws.* Wf; % combine both scaling factors to obtain total scaling
            Wt = diag(Wt); % has to fit 'in the middle' of matrix multiplication
                                        % therefore create a diagonal matrix from row

            B(l,:,:) = (x_px * Wt * py_y).';
         end
      end
  end
end

if opt == 0,
   B = real(squeeze(B)); % use only real part since one is only interested at t=0 sec.
else
   B = squeeze(B);
end
"""

# Python code from CoPilot here :

import numpy as np


def acq_ftbeam_homogen(rs, rr, rgs, rgr, r1, x, y, z, f, c, btype, sc, opt=0, s=None):
    """
    Beam computation by Fourier transformation (homogeneous medium).

    Parameters
    ----------
    rs : array_like, shape (3, Ns)
        Source coordinate vector(s) [x; y; z].
    rr : array_like, shape (3, Nr)
        Receiver coordinate vector(s) [x; y; z].
    rgs : array_like, shape (3, Ngs) or (3,1)
        Source array (rgs = [[0],[0],[0]] means no array).
    rgr : array_like, shape (3, Ngr) or (3,1)
        Receiver array (rgr = [[0],[0],[0]] means no array).
    r1 : array_like, shape (3,)
        Focal point position vector [x1; y1; z1].
    x : array_like, shape (Nx,)
        Array of x-coordinates for which the beam is computed.
    y : array_like, shape (Ny,)
        Array of y-coordinates for which the beam is computed.
    z : float
        Depth at which the beam is evaluated (around the focal point).
    f : array_like, shape (Nf,)
        Array of frequencies.
    c : float
        Velocity in the medium.
    btype : int
        Beam type (1 = source beam, 2 = receiver beam).
    sc : int
        Scale (0/1) scale receiver beam with distance of source-target and vice versa.
        Normally no scaling is used (sc = 0).
    opt : int, optional
        real(0) or complex(1) output of the data (default = real (0)).
    s : array_like, shape (Nf,), optional
        Wavelet in frequency domain, array with same size as f.

    Returns
    -------
    x : ndarray, shape (Nx,)
    y : ndarray, shape (Ny,)
    f : ndarray, shape (Nf,)
    B : ndarray, shape (Nf, Ny, Nx)
        Beam (f, x, y). Real if opt == 0, complex otherwise.
    """

    rs = np.asarray(rs, dtype=float)
    rr = np.asarray(rr, dtype=float)
    rgs = np.asarray(rgs, dtype=float)
    rgr = np.asarray(rgr, dtype=float)
    r1 = np.asarray(r1, dtype=float).reshape(3,)
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    f = np.asarray(f, dtype=float)

    # opt default already handled in signature

    # s default / size check
    if s is None:
        s = np.ones_like(f, dtype=complex)
    else:
        s = np.asarray(s)
        if s.shape != f.shape:
            raise ValueError('Error: size of wavelet "s" should be the same as the frequency axis')

    # test if source arrays are applied
    if rgs.shape[1] == 1 and rgs[0, 0] == 0 and rgs[1, 0] == 0 and rgs[2, 0] == 0:
        sourcearray = 0
    else:
        sourcearray = 1

    # test if receiver arrays are applied
    if rgr.shape[1] == 1 and rgr[0, 0] == 0 and rgr[1, 0] == 0 and rgr[2, 0] == 0:
        receiverarray = 0
    else:
        receiverarray = 1

    # define
    src = 1
    rec = 2

    xs = rs[0, :]
    ys = rs[1, :]
    zs = rs[2, :]
    # lxs = len(xs) # not used

    xr = rr[0, :]
    yr = rr[1, :]
    zr = rr[2, :]
    # lxr = len(xr) # not used

    if sourcearray == 1:
        xgs = rgs[0, :]
        ygs = rgs[1, :]
        # zgs = rgs[2, :]
        # lxgs = len(xgs) # not used

    if receiverarray == 1:
        xgr = rgr[0, :]
        ygr = rgr[1, :]
        # zgr = rgr[2, :]
        # lxgr = len(xgr) # not used

    x1 = r1[0]
    y1 = r1[1]
    z1 = r1[2]

    Rs = np.sqrt((xs - x1) ** 2 + (ys - y1) ** 2 + (zs - z1) ** 2)
    Rr = np.sqrt((xr - x1) ** 2 + (yr - y1) ** 2 + (zr - z1) ** 2)

    p = 1.0 / c

    # compute src slowness
    psx = p * (xs - x1) / Rs
    psy = p * (ys - y1) / Rs
    # psz = p * (z - z1) / Rs     # scalar z

    # compute rec slowness
    prx = p * (xr - x1) / Rr
    pry = p * (yr - y1) / Rr
    # prz = p * (z - z1) / Rr     # scalar z

    # Jacobian of the transformation
    Js = (zs - z1) ** 2 / (Rs ** 4)
    Jr = (zr - z1) ** 2 / (Rr ** 4)

    f_len = len(f)
    x_len = len(x)
    y_len = len(y)

    B = np.zeros((f_len, y_len, x_len), dtype=complex)

    # scale factor "Het touwtje van Leo"
    if sc == 0:
        scale = np.ones(f_len, dtype=float) / (4.0 * np.pi ** 2)
    else:
        if btype == src:
            scale_val = np.sum(Jr) / (4.0 * np.pi ** 2)
        elif btype == rec:
            scale_val = np.sum(Js) / (4.0 * np.pi ** 2)
        else:
            raise ValueError("Unknown beam type")
        scale = scale_val * np.ones(f_len, dtype=float)

    # main switch on beam type
    # Output shape: (Nf, Ny, Nx) to match MATLAB
    if btype == src:
        # source beam
        for l in range(f_len):
            w = 2.0 * np.pi * f[l]

            # x_px: exp(i * w * x' * psx) -> outer(x, psx)
            x_px = np.exp(1j * w * np.outer(x, psx))    # shape (Nx, Ns)

            # py_y: exp(i * w * psy' * y) -> outer(psy, y)
            py_y = np.exp(1j * w * np.outer(psy, y))    # shape (Ns, Ny)

            if sourcearray == 1:
                # source array response
                Ssg = np.zeros_like(psx, dtype=complex)
                for ll in range(len(psx)):
                    Ssg[ll] = np.sum(
                        np.exp(1j * w * psx[ll] * xgs) *
                        np.exp(1j * w * ygs * psy[ll])
                    )
                Ssg = np.diag(Ssg) / len(xgs)    # shape (Ns, Ns)

                if z1 != z:
                    # W1, W2 as in MATLAB
                    W1 = (psx[:, None] ** 2) * np.ones((1, len(psy)))
                    W2 = np.ones((len(psx), 1)) * (psy ** 2)[None, :]
                    Wt = np.exp(
                        1j * w * np.sqrt(1.0 / c ** 2 - W1 - W2) * (z1 - z)
                    )   # shape (Ns, Ns)
                    Ssg = Ssg * Wt

                # source beam
                Ws = Js * (p * w) ** 2   # shape (Ns,)
                # ones(length(x),1)*(Js.*(p.*w).^2) -> repeat row over x
                Wrow = np.ones((x_len, 1)) * Ws[None, :]     # (Nx, Ns)
                tmp = (scale[l] * Wrow) * x_px  # (Nx, Ns)
                B_l = (s[l] * tmp) @ Ssg @ py_y     # (Nx, Ny)
                B[l, :, :] = B_l.T      # (Ny, Nx)

            else:
                if z1 != z:
                    W1 = (psx[:, None] ** 2) * np.ones((1, len(psy)))
                    W2 = np.ones((len(psx), 1)) * (psy ** 2)[None, :]
                    Wt = np.exp(
                        1j * w * np.sqrt(1.0 / c ** 2 - W1 - W2) * (z1 - z)
                    )   # (Ns, Ns)

                    Ws = Js * (p * w) ** 2   # (Ns,)
                    Wrow = np.ones((x_len, 1)) * Ws[None, :]    # (Nx, Ns)
                    tmp = (scale[l] * Wrow) * x_px  # (Nx, Ns)
                    B_l = (s[l] * tmp) @ Wt @ py_y  # (Nx, Ny)
                    B[l, :, :] = B_l.T
                else:
                    # all scaling separated
                    Wf = scale[l] * s[l]    # scalar
                    Ws = Js * (p * w) ** 2  # (Ns,)
                    Wt = Ws * Wf     # (Ns,)
                    Wt_mat = np.diag(Wt)    # (Ns, Ns)
                    B_l = x_px @ Wt_mat @ py_y  # (Nx, Ny)
                    B[l, :, :] = B_l.T

    elif btype == rec:
        # receiver beam
        for l in range(f_len):
            w = 2.0 * np.pi * f[l]

            # x_px: exp(i * w * x' * prx) -> outer(x, prx)
            x_px = np.exp(1j * w * np.outer(x, prx))    # (Nx, Nr)

            # py_y: exp(i * w * pry' * y) -> outer(pry, y)
            py_y = np.exp(1j * w * np.outer(pry, y))     # (Nr, Ny)

            if receiverarray == 1:
                # geophone array response
                Srg = np.zeros_like(prx, dtype=complex)
                for ll in range(len(prx)):
                    Srg[ll] = np.sum(
                        np.exp(1j * w * prx[ll] * xgr) *
                        np.exp(1j * w * ygr * pry[ll])
                    )
                Srg = np.diag(Srg) / len(xgr)    # (Nr, Nr)

                if z1 != z:
                    W = np.exp(
                        1j * w * np.sqrt(
                            1.0 / c ** 2
                            - (prx[:, None] ** 2) * np.ones((1, len(pry)))
                            - np.ones((len(prx), 1)) * (pry ** 2)[None, :]
                        ) * (z1 - z)
                    )   # (Nr, Nr)
                    Srg = Srg * W

                Ws = Jr * (p * w) ** 2   # (Nr,)
                Wrow = np.ones((x_len, 1)) * Ws[None, :]     # (Nx, Nr)
                tmp = (scale[l] * Wrow) * x_px   # (Nx, Nr)
                B_l = (s[l] * tmp) @ Srg @ py_y  # (Nx, Ny)
                B[l, :, :] = B_l.T

            else:
                if z1 != z:
                    W1 = (prx[:, None] ** 2) * np.ones((1, len(pry)))
                    W2 = np.ones((len(prx), 1)) * (pry ** 2)[None, :]
                    Wt = np.exp(
                        1j * w * np.sqrt(1.0 / c ** 2 - W1 - W2) * (z1 - z)
                    )   # (Nr, Nr)

                    Ws = Jr * (p * w) ** 2   # (Nr,)
                    Wrow = np.ones((x_len, 1)) * Ws[None, :]     # (Nx, Nr)
                    tmp = (scale[l] * Wrow) * x_px   # (Nx, Nr)
                    B_l = (s[l] * tmp) @ Wt @ py_y   # (Nx, Ny)
                    B[l, :, :] = B_l.T
                else:
                    Wf = scale[l] * s[l]     # scalar
                    Ws = Jr * (p * w) ** 2   # (Nr,)
                    Wt = Ws * Wf     # (Nr,)
                    Wt_mat = np.diag(Wt)     # (Nr, Nr)
                    B_l = x_px @ Wt_mat @ py_y   # (Nx, Ny)
                    B[l, :, :] = B_l.T
    else:
        raise ValueError("Unknown beam type (btype must be 1=src or 2=rec)")

    # final output: real or complex, and squeeze frequency dimension like MATLAB
    if opt == 0:
        B = np.real(B)
    # Squeeze as in MATLAB
    B = np.squeeze(B)
    return x, y, f, B
