% This matlab srcipts shows the acquisition geometry analysis 
% for a land-geometry. The script is based on matrlab code by A. Volker 
% 12-12-2003 

% type the following from the command line to start debugging:

%"dbstop in demo_bart_1", followed by:
%"demo_bart_1", to enter debug mode...

octave_select_graphics_toolkit('qt', 'fltk');

close all; % close all figures 
clear all; % clear workspace 

% Next four lines commented out, Bart
% define path and include DELPHI modules
% DELPHIROOT=getenv('DELPHIROOT');
% pathname=sprintf('path,\''%s/matlab\''',DELPHIROOT)
% eval(['path(',pathname,')'])

% receiver geometry;
% define a single receiver-line around x = 0
xr = (1:120) * 50;	% 6 km spread (minus 50 m)
xr = xr - mean(xr);	% spread around x = 0

% define number of receiver lines in a template, around y = 0
yr = (1:8) * 750;		% 8 lines spaced 150 m
yr = yr-mean(yr);		% spread around y = 0

% convert xr, yr to a meshgrid
[xr,yr] = meshgrid(xr,yr);

% define z-coordinates
zr = zeros(size(xr));

% define the final receiver location array of the template
rr = [xr(:).';yr(:).';zr(:).'];
clear xr yr zr; 

% source geometry
% define the shot line around y = 0
ys = (1:15) * 50;		% one only
ys = ys - mean(ys);	% shot line around y = 0

% define x-coordinates
xs = 0; 

% convert xr, yr to a meshgrid
[xs,ys] = meshgrid(xs,ys); 

% define z-coordinates
zs = zeros(size(xs)); 

% define the final source location array of the template
rs = [xs(:).';ys(:).';zs(:).']; 
clear xs ys zs;

% verbose option 
verbose = 0; 

if verbose > 0
    % lets plot the template layout 
    plot(xs,ys,'r*',xr,yr,'gv') 
    xlabel('x-coordinate [m]') 
    ylabel('y-coordinate [m]') 
    title('template layout'); 
    grid on; 
    axis image 
    disp(['hit any key to continue...']); 
    pause;
    close;
end

% geophone group, no geophone-groups are applied 
rgr = [0;0;0']; 

% source group, no source-groups are applied 
rgs = [0;0;0]; 

% survey area, roll along of template in x and y-rirection
dxt =  250; 
dyt =  150; 

% in-line roll array xt means 'x-of-template'
% xt = (1:20) * dxt;
xt = (1:1) * dxt;
xt = xt - mean(xt); 

% x-line roll array yt means 'x-of-template', Bart; he forgot to multiply with dyt;
% yt=(1:4);          % original
yt = (1:1) * dyt;    % modified
yt = yt - mean(yt);

% frequency 
freq = 40; 

% velocity 
cp = 4000; 

% target point(s), where the beam(s) is(are) evaluated
%r1 = [-100;200;2000];
r1 = [0;0;2000];

% define grid in which the beams/functions are computed    
x = -800 : 12.5 : 800; 
y = x;

% write the results to the current directory 
fnam = 'demo_bart_3';
posno = 1;
result_file = [fnam, num2str(posno)];

disp(['Output filename: ', result_file, '.mat']);

z = r1(3,1); % get depth from target point

% copied from acq_analysis_3d_ft.m

% +++++++++++++++++++++++++++++++++++++++++++++++++++++ %

% ray-parameters 

% set up x-slowness array with Npx steps from -1/c to 1/c
Npx = 128; 
px  = -1./cp : 2./(cp.*(Npx-1)) : 1./cp;

% set up y-slowness array with Npy steps from -1/c to 1/c 
Npy = 128; 
py  = -1./cp : 2./(cp.*(Npy-1)) : 1./cp;

% Radon transform 
L1 = exp(i*2*pi*freq * x' * px); 
L2 = exp(i*2*pi*freq * py' * y); 
 
% template roll along 
[Xt,Yt] = meshgrid(xt,yt); 

% find receivers that are being rolled out
% m = find(rr(1,:) >= min(rr(1,:)) & rr(1,:) < (min(rr(1,:)) + dxt)); 
m = find( rr(1,:) < (min(rr(1,:)) + dxt) ); 
rr_min = rr(:,m);

% find receivers that are being rolled in
% m = find(rr(1,:) > (max(rr(1,:)) - dxt) & rr(1,:) <= max(rr(1,:))); 
m = find(rr(1,:) > (max(rr(1,:)) - dxt) ); 
rr_max = rr(:,m);

%figure(1); 
if verbose == 1 
   hndl = plot(Xt,Yt,'r.'); 
   set(hndl,'markersize',20); 
   xlabel('x [m]'); 
   ylabel('y [m]'); 
   hold on; 
   grid 
   title(['shooting templates of ',fnam,num2str(posno)]); 
   drawnow; 
end 

nyt   = length(yt);       % no of rolls in y-direction
for l = 1:nyt             % iterate over rolls in y-direction
   tic       
	%	if verbose == 1 
	disp(['Rollstep ', num2str(l),' of ', num2str(nyt), ' started']); 
	% end 
    
   % beam at beginning of each swath 
   k = 1;
   
   rt=[xt(k); yt(l); 0]; 
   
   [x,y,f,Bs_s,Br_s,I_s,px,py,AVP_s] = acq_rolltempl_pp(rs, rr, rgs, rgr, rt, r1, x, y, z, freq, cp, 0);  
   
   if l == 1 && k == 1       % 
      % total result 
      Bs_t  = squeeze(Bs_s); 
      Br_t  = squeeze(Br_s); 
      I_t   = squeeze(I_s); 
      AVP_t = squeeze(AVP_s); 
   end             

   if l > 1 && k == 1 
      % total result 
      Bs_t  = Bs_t  + squeeze(Bs_s); 
      Br_t  = Br_t  + squeeze(Br_s); 
      I_t   = I_t   + squeeze(I_s); 
      AVP_t = AVP_t + squeeze(AVP_s); 
   end
   
   % show progress graphically... 
   if verbose == 1 
      %figure(1); 
      hndl = plot(xt(k),yt(l),'g.');       
      set(hndl,'markersize',20); 
      drawnow; 
   end 
   
   nxt   = length(xt);        % no of rolls in x-direction
   for k = 2 : nxt            % iterate over rolls in x-direction

      rt = [xt(k-1); yt(l); 0];

      [x,y,f,Br] = acq_ftbeam_homogen(rs+rt*ones(1,size(rs,2)), rr_min + rt * ones(1, size(rr_min,2)), rgs,rgr,r1,x,y,z,freq,cp,2,0,1);

      Br_s = squeeze(Br_s) - Br.';

      rt   = [xt(k);yt(l);0];

      [x,y,f,Bs] = acq_ftbeam_homogen(rs+rt*ones(1,size(rs,2)), rr_max + rt * ones(1, size(rr_max,2)), rgs,rgr,r1,x,y,z,freq,cp,1,0,1);
      [x,y,f,Br] = acq_ftbeam_homogen(rs+rt*ones(1,size(rs,2)), rr_max + rt * ones(1, size(rr_max,2)), rgs,rgr,r1,x,y,z,freq,cp,2,0,1);

      Bs_s = Bs.';
      Br_s = squeeze(Br_s)+Br.';

      % focal functions per template
      I_s   = Bs_s .* Br_s;
      AVP_s = ((conj(L2) * Bs_s.' * conj(L1)).* (L2 * Br_s.' * L1)).';

      % total result
      Bs_t = squeeze(Bs_t)  + Bs_s;
      Br_t = squeeze(Br_t)  + Br_s;
      I_t  = squeeze(I_t)   + I_s;
      AVP_t= squeeze(AVP_t) + AVP_s;

      % show progress graphically...
      if verbose == 1
         %figure(1);
         hndl=plot(xt(k),yt(l),'g.');
         set(hndl,'markersize',20);
         drawnow;
      end
   end
   t = toc; disp(['Rollstep ', num2str(l), ' took ', num2str(t),' s ']);
end    

if verbose==1 
   hold off; 
end    

clear *_s I Bs Br AVP

save([result_file, '.mat']); % save result, add number to end of filename to identify different target pos. 



% display the results 
acq_disp_analysis_result(result_file); 

disp('Plots are open. Press Enter in the terminal to close them.');
pause;
close all hidden;
close all force;
delete(findall(0, 'type', 'figure'));
drawnow();
