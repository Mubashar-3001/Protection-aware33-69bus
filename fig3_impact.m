%% Fig. 3 - Change in relay current relative to the same fault with all hubs off
% Reads data/fig3_impact.csv and writes figures/fig3_impact.{fig,pdf,png}.
% Phase current for 3ph and LL faults, 3I0 for SLG and LLG faults.

%% ---------------- USER SETTINGS ----------------
legendText = {'primary relay (range)', 'backup relay (range)', '\pm95th percentile'};
xLabel     = 'change vs. all hubs off (%)';
panelTitle = {'IEEE 33-bus', 'IEEE 69-bus'};
faultTypes = ["3ph", "LL", "SLG", "LLG"];       % bottom to top
colPrim    = [42 120 214]/255;    % blue
colBack    = [235 104 52]/255;    % orange
colTick    = [11 11 11]/255;      % near black
fontName   = 'Times New Roman';
fontSize   = 8;
figSize    = [7.0 2.4];           % inches
%% -----------------------------------------------

here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
T = readtable(fullfile(here, 'data', 'fig3_impact.csv'), 'TextType', 'string');
outDir = fullfile(here, 'figures'); if ~exist(outDir, 'dir'), mkdir(outDir); end

fig = figure('Units', 'inches', 'Position', [1 1 figSize], 'Color', 'w', 'Name', 'Fig. 3 impact');
tl = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
feeders = [33 69];
for k = 1:2
    ax = nexttile(tl); hold(ax, 'on');
    for i = 1:numel(faultTypes)
        for role = ["primary", "backup"]
            r = T(T.feeder == feeders(k) & T.fault_type == faultTypes(i) & T.role == role, :);
            if role == "primary", y = i - 1 + 0.17; c = colPrim; else, y = i - 1 - 0.17; c = colBack; end
            h = plot(ax, [r.max_decrease_pct r.max_increase_pct], [y y], '-', 'Color', c, 'LineWidth', 2.5);
            if role == "primary", hP = h; else, hBk = h; end
            hT = plot(ax, [-r.p95_abs_pct r.p95_abs_pct], [y y], '|', 'Color', colTick, 'MarkerSize', 6, 'LineWidth', 1.2);
        end
    end
    xline(ax, 0, 'Color', [0.32 0.32 0.31], 'LineWidth', 0.6);
    yticks(ax, 0:numel(faultTypes) - 1); yticklabels(ax, faultTypes); ylim(ax, [-0.6, numel(faultTypes) - 0.4]);
    grid(ax, 'on'); ax.YGrid = 'off'; box(ax, 'off'); xlabel(ax, xLabel);
    title(ax, panelTitle{k}, 'FontWeight', 'normal', 'HorizontalAlignment', 'left', 'Units', 'normalized', 'Position', [0 1.0 0]);
    set(ax, 'FontName', fontName, 'FontSize', fontSize, 'TickDir', 'out', 'GridColor', [0.89 0.89 0.87], 'GridAlpha', 1);
end
lg = legend(ax, [hP hBk hT], legendText, 'Orientation', 'horizontal', 'Box', 'off', ...
            'FontName', fontName, 'FontSize', fontSize - 1);
lg.Layout.Tile = 'south';

savefig(fig, fullfile(outDir, 'fig3_impact.fig'));
exportgraphics(fig, fullfile(outDir, 'fig3_impact.pdf'), 'ContentType', 'vector');
exportgraphics(fig, fullfile(outDir, 'fig3_impact.png'), 'Resolution', 300);
