%% Fig. 2 - Largest single hub each bus can host (IEEE 33- and 69-bus)
% Reads data/fig2_hosting.csv and writes figures/fig2_hosting.{fig,pdf,png}.
% Edit the USER SETTINGS block to change legends, labels or colours, then run.

%% ---------------- USER SETTINGS ----------------
legendText = {'charge at light load only', ...        % bars
              'charge at any time', ...               % horizontal ticks
              'rating used (all hubs together)'};     % diamonds
xLabel     = 'bus';
yLabel     = 'single-hub hosting limit (MW)';
panelTitle = {'IEEE 33-bus', 'IEEE 69-bus'};
colBars    = [42 120 214]/255;    % blue
colTicks   = [235 104 52]/255;    % orange
colHubs    = [27 175 122]/255;    % green
fontName   = 'Times New Roman';
fontSize   = 8;
figSize    = [7.0 2.5];           % inches (width, height)
%% -----------------------------------------------

here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
T = readtable(fullfile(here, 'data', 'fig2_hosting.csv'), 'TextType', 'string');
outDir = fullfile(here, 'figures'); if ~exist(outDir, 'dir'), mkdir(outDir); end

fig = figure('Units', 'inches', 'Position', [1 1 figSize], 'Color', 'w', 'Name', 'Fig. 2 hosting');
tl = tiledlayout(fig, 1, 29, 'TileSpacing', 'compact', 'Padding', 'compact');
feeders = [33 69]; spans = {[1 10], [1 19]}; starts = [1 11];
for k = 1:2
    ax = nexttile(tl, starts(k), spans{k}); hold(ax, 'on');
    D = T(T.feeder == feeders(k), :);
    hB = bar(ax, D.bus, D.limit_light_only_MW, 0.72, 'FaceColor', colBars, 'EdgeColor', 'none');
    hT = plot(ax, D.bus, D.limit_any_time_MW, '_', 'Color', colTicks, 'MarkerSize', 5, 'LineWidth', 1.3);
    hub = D(~isnan(D.hub_rating_MW), :);
    hH = plot(ax, hub.bus, hub.hub_rating_MW, 'd', 'MarkerSize', 4.5, 'MarkerFaceColor', colHubs, ...
              'MarkerEdgeColor', 'k', 'LineWidth', 0.5);
    for j = 1:height(hub)
        text(ax, hub.bus(j), hub.hub_rating_MW(j) + 0.25, sprintf('H%d: %.2f', hub.bus(j), hub.hub_rating_MW(j)), ...
             'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontName', fontName, ...
             'FontSize', fontSize - 2, 'BackgroundColor', 'w', 'Margin', 0.5);
    end
    xlim(ax, [1, max(D.bus) + 1]); grid(ax, 'on'); ax.XGrid = 'off'; box(ax, 'off');
    xlabel(ax, xLabel); title(ax, panelTitle{k}, 'FontWeight', 'normal', 'HorizontalAlignment', 'left', ...
        'Units', 'normalized', 'Position', [0 1.0 0]);
    if k == 1, ylabel(ax, yLabel); end
    set(ax, 'FontName', fontName, 'FontSize', fontSize, 'TickDir', 'out', 'GridColor', [0.89 0.89 0.87], 'GridAlpha', 1);
end
lg = legend(ax, [hB hT hH], legendText, 'Orientation', 'horizontal', 'Box', 'off', ...
            'FontName', fontName, 'FontSize', fontSize - 1);
lg.Layout.Tile = 'north';

savefig(fig, fullfile(outDir, 'fig2_hosting.fig'));
exportgraphics(fig, fullfile(outDir, 'fig2_hosting.pdf'), 'ContentType', 'vector');
exportgraphics(fig, fullfile(outDir, 'fig2_hosting.png'), 'Resolution', 300);
