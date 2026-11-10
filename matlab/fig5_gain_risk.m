%% Fig. 5 - Gain against risk for the adaptive policies
% Reads data/fig5_gain_risk.csv and writes figures/fig5_gain_risk.{fig,pdf,png}.

%% ---------------- USER SETTINGS ----------------
legendText = {'IEEE 33-bus', 'IEEE 69-bus'};
xLabel     = 'reduction of mean clearing time vs. fixed (%)';
yLabel     = {'expected lost energy per', 'wrong-group event (MWh)'};
pointLabel = true;                % label the 33-bus points with the policy name
col        = [42 120 214]/255;    % blue
fontName   = 'Times New Roman';
fontSize   = 8;
figSize    = [3.5 2.6];           % inches
%% -----------------------------------------------

here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
T = readtable(fullfile(here, 'data', 'fig5_gain_risk.csv'), 'TextType', 'string');
outDir = fullfile(here, 'figures'); if ~exist(outDir, 'dir'), mkdir(outDir); end

fig = figure('Units', 'inches', 'Position', [1 1 figSize], 'Color', 'w', 'Name', 'Fig. 5 gain vs risk');
ax = axes(fig); hold(ax, 'on');
A = T(T.feeder == 33, :); B = T(T.feeder == 69, :);
h33 = plot(ax, A.gain_pct, A.lost_energy_MWh, 'o', 'MarkerSize', 5, 'MarkerFaceColor', col, 'MarkerEdgeColor', col);
h69 = plot(ax, B.gain_pct, B.lost_energy_MWh, 's', 'MarkerSize', 5, 'MarkerFaceColor', 'w', 'MarkerEdgeColor', col, 'LineWidth', 1.2);
if pointLabel
    % offsets (x, y) in data units, chosen as in the published figure
    off = containers.Map({'best K=2', 'best K=4', 'TOD', 'CHG', 'EXP', 'own per state'}, ...
                         {[0.06 -0.15], [0.06 0.06], [-0.06 0.12], [0.06 0.10], [0.08 0.06], [-0.08 -0.18]});
    for j = 1:height(A)
        o = off(char(A.label(j)));
        if o(1) < 0, ha = 'right'; else, ha = 'left'; end
        text(ax, A.gain_pct(j) + o(1), A.lost_energy_MWh(j) + o(2), A.label(j), 'HorizontalAlignment', ha, ...
             'FontName', fontName, 'FontSize', fontSize - 2, 'Color', [82 81 78]/255);
    end
end
grid(ax, 'on'); ax.XGrid = 'off'; box(ax, 'off');
xlabel(ax, xLabel); ylabel(ax, yLabel);
set(ax, 'FontName', fontName, 'FontSize', fontSize, 'TickDir', 'out', 'GridColor', [0.89 0.89 0.87], 'GridAlpha', 1);
legend(ax, [h33 h69], legendText, 'Location', 'southeast', 'Box', 'off', 'FontName', fontName, 'FontSize', fontSize - 1);

savefig(fig, fullfile(outDir, 'fig5_gain_risk.fig'));
exportgraphics(fig, fullfile(outDir, 'fig5_gain_risk.pdf'), 'ContentType', 'vector');
exportgraphics(fig, fullfile(outDir, 'fig5_gain_risk.png'), 'Resolution', 300);
