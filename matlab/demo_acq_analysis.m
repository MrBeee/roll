% This matlab srcipts shows the acquisition geometry analysis 
% for a land-geometry. The geometry consists of ten geophone lines.
% Each line has 140 live channels, with a spacing of 40 m. 
% There is an orthogonal shot-line in the center of the template,
% consisting of 55 shots with a spacing 40 m. 
 
% by A. Volker 
% 09-04-01 
 
close all; % close all figures 
clear all; % clear workspace 
 
% define path and include DELPHI modules
DELPHIROOT=getenv('DELPHIROOT');
if ~isempty(DELPHIROOT)
   matlab_dir = fullfile(DELPHIROOT, 'matlab');
   if exist(matlab_dir, 'dir') == 7
      addpath(matlab_dir);
   end
end

% receiver geometry 
xr=(1:140)*40; xr=xr-mean(xr); % define one receiver-line 
yr=(1:10)*440; yr=yr-mean(yr); % define number of receiver lines in a template 
[xr,yr]=meshgrid(xr,yr); 
zr=zeros(size(xr)); 

% Bart; some important stuff to know:
% ; (=semicolumn) normally makes sure that the result of a command is not displayed on the screen
% ; (=semicolumn) inside array expression (e.g.: array=[1,2,3; 4,5,6; 7,8,9] acts as a row separator
% xr(:).' makes a vector of the xr array. All columns are put behind each other

rr=[xr(:).';yr(:).';zr(:).']; % this makes an array where x,y,z of each receiver are accesible as a column

% source geometry 
ys=(1:55)*40; ys=ys-mean(ys); % define the shot line  
xs=0; 
[xs,ys]=meshgrid(xs,ys); 
zs=zeros(size(xs)); 
rs=[xs(:).';ys(:).';zs(:).'];  % this makes an array where x,y,z of each source are accesible as a column
 
% geophone group, no geophone-groups are applied 
rgr=[0;0;0']; 
    
% source group, no source-groups are applied 
rgs=[0;0;0]; 
 
% survey area, roll along of template 
dxt=560; dyt=2200; 
xt=(1:20)*dxt; xt=xt-mean(xt); % in-line rolls 
yt=(1:4); yt=yt-mean(yt); % x-line rolls 
 
% frequency 
freq=40; 
 
% velocity 
cp=2300; 
 
% target 
x1=-100; % x-coordinate of the target 
y1=200; % y-coordinate of the target 
[x1,y1]=meshgrid(x1,y1); 
z1=2e3*ones(size(x1)); % target depth = 2000 m 
r1=[x1(:).';y1(:).';z1(:).']; 
 
% define grid in which the beams/functions are computed    
x=-800:12.5:800; 
y=x; 
 
% write the results to the current directory 
fnam='demogeom'; 
 
% verbose option 
verbose=0; 
 
for l=1:size(r1,2); 
   z=r1(3,l); 
   acq_analysis_3d_ft(fnam,rs,rr,rgs,rgr,xt,yt,freq,cp,r1(:,l),x,y,z,l,verbose); 
end 
 
% display the results 
acq_disp_analysis_result([fnam,num2str(l)]); 

input('Plots are open. Press Enter in the terminal to close them. ', 's');
close all hidden;
close all force;
delete(findall(0, 'type', 'figure'));
drawnow();
