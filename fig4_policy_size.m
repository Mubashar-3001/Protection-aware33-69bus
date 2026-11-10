%% Fig. 4 - Mean primary clearing time against the number of setting groups
% Reads data/fig4_policy_size.csv and writes figures/fig4_policy_size.{fig,pdf,png}.

%% ---------------- USER SETTINGS ----------------
legendText = {'best K-group policy (exhaustive)', 'physical rule', 'clustering', 'own settings per state (K = 35)'};
xLabel     = 'number of setting groups K';
yLabel     = 'mean primary clearing time (ms)';
panelTitle = {'IEEE 33-bus (fixed design: %.1f ms)', 'IEEE 69-bus (fixed design: %.1f ms)'};   % %.1f = fixed design
colBest    = [42 120 214]/255;    % blue
colRule    = [235 104 52]/255;    % orange
colClus    = [27 175 122]/255;    % green
colPS      = [82 81 78]/255;      % grey
fontName   = 'Times New Roman';
fontSize   = 8;
figSize    = [7.0 2.8];           % inches
%% -----------------------------------------------

here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
T = readtable(fullfile(here, 'data', 'fig4_policy_size.csv'), 'TextType', 'string');
outDir = fullfile(here, 'figures'); if ~exist(outDir, 'dir'), mkdir(outDir); end

fig = figure('Units', 'inches', 'Position', [1 1 figSize], 'Color', 'w', 'Name', 'Fig. 4 policy size');
tl = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
feeders = [33 69];
for k = 1:2
    ax = nexttile(tl); hold(ax, 'on');
    D = T(T.feeder == feeders(k), :);
    fixed = D.mean_t_ms(D.kind == "fixed");
    B = sortrows(D(D.kind == "best", :), 'K');
    R = D(D.kind == "rule", :); C = D(D.kind == "cluster", :); ps = D.mean_t_ms(D.kind == "per_state");
    hB = plot(ax, B.K, B.mean_t_ms, '-o', 'Color', colBest, 'MarkerFaceColor', colBest, 'MarkerSize', 4, 'LineWidth', 1.4);
    hR = plot(ax, R.K, R.mean_t_ms, 's', 'Color', colRule, 'MarkerFaceColor', 'w', 'MarkerSize', 5, 'LineWidth', 1.2);
    hC = plot(ax, C.K, C.mean_t_ms, '^', 'Color', colClus, 'MarkerFaceColor', 'w', 'MarkerSize', 5, 'LineWidth', 1.2);
    hP = plot(ax, [-0.6 9.6], [ps ps], '--', 'Color', colPS, 'LineWidth', 0.9);
    xlim(ax, [-0.6 9.6]); grid(ax, 'on'); ax.XGrid = 'off'; box(ax, 'off');
    xlabel(ax, xLabel); if k == 1, ylabel(ax, yLabel); end
    title(ax, sprintf(panelTitle{k}, fixed), 'FontWeight', 'normal', 'HorizontalAlignment', 'left', ...
        'Units', 'normalized', 'Position', [0 1.0 0]);
    set(ax, 'FontName', fontName, 'FontSize', fontSize, 'TickDir', 'out', 'GridColor', [0.89 0.89 0.87], 'GridAlpha', 1);
end
lg = legend(ax, [hB hR hC hP], legendText, 'Orientation', 'horizontal', 'Box', 'off', ...
            'FontName', fontName, 'FontSize', fontSize - 1);
lg.Layout.Tile = 'south';

savefig(fig, fullfile(outDir, 'fig4_policy_size.fig'));
exportgraphics(fig, fullfile(outDir, 'fig4_policy_size.pdf'), 'ContentType', 'vector');
exportgraphics(fig, fullfile(outDir, 'fig4_policy_size.png'), 'Resolution', 300);
