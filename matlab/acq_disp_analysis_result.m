% Display results from acquisition analysis 
% 
% 
% input fnam : filename of output file from acq_analysis_3d_ft.m 
% 
% usage : acq_disp_analysis_result(fnam) 
% 
% see also : acq_analysis_3d_ft
%-------------------------------------------------------------------------------------------------- 
 
function acq_disp_analysis_result(fnam) 
 
% by A. Volker 
% 21-02-01 
 
if nargin < 1 || isempty(fnam)
    mat_files = dir('*.mat');
    if isempty(mat_files)
        disp('Error: can not find any .mat result files in the current folder');
        return
    end

    [~, latest_idx] = max([mat_files.datenum]);
    file_to_load = mat_files(latest_idx).name;
    disp(['Using latest result file: ', file_to_load]);
elseif exist([fnam,'.mat']) == 2
    file_to_load = [fnam, '.mat'];
elseif exist(fnam) == 2
    file_to_load = fnam;
else
    disp(['Error: can not find file']); 
    return 
end 

load(file_to_load); 

overview_fig = create_overview_figure();

if exist('rr', 'var') == 1 && exist('rs', 'var') == 1 && exist('Xt', 'var') == 1 && exist('Yt', 'var') == 1
    roll_count = numel(Xt);
    rr_all = zeros(size(rr, 2) * roll_count, 2);
    rs_all = zeros(size(rs, 2) * roll_count, 2);

    for roll_idx = 1:roll_count
        rec_range = (roll_idx - 1) * size(rr, 2) + (1:size(rr, 2));
        src_range = (roll_idx - 1) * size(rs, 2) + (1:size(rs, 2));

        rr_all(rec_range, :) = [rr(1, :).'+Xt(roll_idx), rr(2, :).'+Yt(roll_idx)];
        rs_all(src_range, :) = [rs(1, :).'+Xt(roll_idx), rs(2, :).'+Yt(roll_idx)];
    end

    rr_all = unique(rr_all, 'rows');
    rs_all = unique(rs_all, 'rows');

    select_plot_slot(overview_fig, 1);
    plot(rs_all(:,1), rs_all(:,2), 'r.');
    xlabel('x-coordinate [m]');
    ylabel('y-coordinate [m]');
    title('Top view of all source locations');
    grid on;
    axis image;
    drawnow;

    select_plot_slot(overview_fig, 2);
    plot(rr_all(:,1), rr_all(:,2), 'b.');
    xlabel('x-coordinate [m]');
    ylabel('y-coordinate [m]');
    title('Top view of all receiver locations');
    grid on;
    axis image;
    drawnow;

    select_plot_slot(overview_fig, 3);
    plot(rr_all(:,1), rr_all(:,2), 'b.', rs_all(:,1), rs_all(:,2), 'r.');
    hold on;
    if exist('r1', 'var') == 1 && numel(r1) >= 2
        beam_eval_radius = 50;
        theta = linspace(0, 2 * pi, 73);
        fill(r1(1) + beam_eval_radius * cos(theta), ...
            r1(2) + beam_eval_radius * sin(theta), ...
            'g', 'facealpha', 0.35, 'edgecolor', 'g', 'linewidth', 1.0);
        plot(r1(1), r1(2), 'g+', 'markersize', 8, 'linewidth', 1.5);
    end
    hold off;
    xlabel('x-coordinate [m]');
    ylabel('y-coordinate [m]');
    title('Top view of all source and receiver locations');
    grid on;
    axis image;
    drawnow;
end
 
if exist('f') == 1 && exist('freq') == 0
    freq=f;     
end 
 
if exist('f') == 0 && exist('freq') == 0
   freq=input('frequency = '); 
   f=freq; 
end 
 
% Radon transform 
L1 = exp(i*2*pi*freq*x'*px); 
L2 = exp(i*2*pi*freq*py'*y); 
 

Bs_t  = squeeze(Bs_t).';    % Bs_t  contains Src Beam
Br_t  = squeeze(Br_t).';    % Br_t  contains Rec Beam
I_t   = squeeze(I_t).';     % I_t   contains resolution function
AVP_t = squeeze(AVP_t).';   % AVP_t contains AVP function in radon domain


% Radon transform 
L1     = exp(i*2*pi*f*x'*px); 
L2     = exp(i*2*pi*f*py'*y);

R_Bs_t = L2 * Bs_t * L1;    % R_Bs_t means 'radon transform of Bs_t'
R_Br_t = L2 * Br_t * L1;    % R_Br_t means 'radon transform of Br_t' 

% source beam in xy 
select_plot_slot(overview_fig, 4);
T=real(Bs_t);    
T=T./max(max(abs(T))); 
imagesc(x,y,20*log10(abs(T)),[-60 0]); 
xlabel('x [m]') 
ylabel('y [m]')    
title(['xy-slice of source beam, frequency = ',num2str(freq),' Hz ']); 
colorbar; 
axis image 
drawnow;

% source beam in pxpy 
select_plot_slot(overview_fig, 7);
T = real(R_Bs_t); 
T = T./max(max(abs(T))); 
imagesc(px*1e3,py*1e3,abs(T),[0 1]) 
xlabel('p_x [ms/m]') 
ylabel('p_y [ms/m]') 
title(['Radon transform of source beam, frequency = ',num2str(freq),' Hz ']); 
colorbar;
axis image 
drawnow;
 
% receiver beam in xy 
select_plot_slot(overview_fig, 5);
T = real(Br_t);    
T = T./max(max(abs(T))); 
imagesc(x,y,20*log10(abs(T)),[-60 0]); 
xlabel('x [m]') 
ylabel('y [m]')    
title(['xy-slice of receiver beam, frequency = ',num2str(freq),' Hz ']); 
colorbar; 
axis image       
drawnow;
    
% receiver beam in pxpy 
select_plot_slot(overview_fig, 8);
T = real(R_Br_t); 
T = T./max(max(abs(T))); 
imagesc(px*1e3,py*1e3,abs(T),[0 1]) 
xlabel('p_x [ms/m]') 
ylabel('p_y [ms/m]') 
title(['Radon transform of receiver beam, frequency = ',num2str(freq),' Hz ']); 
colorbar;
axis image    
drawnow;
       
% resolution function in xy 
select_plot_slot(overview_fig, 6);
T = real(I_t);    
T = T./max(max(abs(T))); 
imagesc(x,y,20*log10(abs(real(T))),[-60 0]); 
xlabel('x [m]') 
ylabel('y [m]')       
title(['xy-slice of resolution function, frequency = ',num2str(freq),' Hz ']); 
colorbar; 
axis image 
drawnow;
    
% AVP-function in Radon domain 
select_plot_slot(overview_fig, 9);
T = real(AVP_t); 
T = T./max(max(abs(T))); 
imagesc(px*1e3,py*1e3,abs(T),[0 1]) 
xlabel('p_x [ms/m]') 
ylabel('p_y [ms/m]') 
title(['AVP-function in the Radon domain, frequency = ',num2str(freq),' Hz ']); 
colorbar;
axis image 
drawnow;

disp('Plots are open. Press Enter in the terminal or close the plot window when you are done.');

while ~isempty(kbhit(1))
end

while ishandle(overview_fig)
    drawnow;

    key = kbhit(1);
    if strcmp(key, sprintf('\r')) || strcmp(key, sprintf('\n'))
        break;
    end

    pause(0.1);
end

if ishandle(overview_fig)
    close(overview_fig);
end

end

function select_plot_slot(fig_handle, slot_idx)

figure(fig_handle);
subplot_handle = subplot(3, 3, slot_idx);
set(subplot_handle, 'position', get_plot_slot_position(slot_idx));
set(subplot_handle, 'box', 'on');
cla;

end

function slot_position = get_plot_slot_position(slot_idx)

tile_margin_x = 0.04;
tile_margin_y = 0.05;
tile_gap_x = 0.015;
tile_gap_y = 0.02;
tile_width = (1 - 2 * tile_margin_x - 2 * tile_gap_x) / 3;
tile_height = (1 - 2 * tile_margin_y - 2 * tile_gap_y) / 3;

row_idx = ceil(slot_idx / 3);
col_idx = mod(slot_idx - 1, 3) + 1;

left = tile_margin_x + (col_idx - 1) * (tile_width + tile_gap_x);
bottom = 1 - tile_margin_y - row_idx * tile_height - (row_idx - 1) * tile_gap_y;

slot_position = [left, bottom, tile_width, tile_height];

end

function overview_fig = create_overview_figure()

screen_rect = get_primary_monitor_rect();

overview_width = min(1900, screen_rect(3) - 320);
overview_height = min(1100, screen_rect(4) - 520);
overview_left = screen_rect(1) + max(140, floor((screen_rect(3) - overview_width) / 2));
overview_bottom = screen_rect(2) + 35;

overview_position = [overview_left, overview_bottom, overview_width, overview_height];

overview_fig = figure(1);
clf(overview_fig);
set(overview_fig, 'units', 'pixels');
set(overview_fig, 'numbertitle', 'off');
set(overview_fig, 'name', 'Acquisition Analysis Results');
set(overview_fig, 'resize', 'on');
set(overview_fig, 'windowstyle', 'normal');
set(overview_fig, 'position', overview_position);

draw_overview_grid(overview_fig);

end

function draw_overview_grid(fig_handle)

for slot_idx = 1:9
    annotation(fig_handle, 'rectangle', get_plot_slot_position(slot_idx), ...
        'color', [0.35 0.35 0.35], 'linewidth', 0.75);
end

end

function screen_rect = get_primary_monitor_rect()

screen_rect = get(0, 'ScreenSize');

try
    monitor_positions = get(0, 'MonitorPositions');
    if ~isempty(monitor_positions)
        screen_rect = monitor_positions(1, :);
    end
catch
end

end
