%% Fig. 6 - Hubs scaled beyond the hosting limit (IEEE 33-bus sweep)
% Reads data/fig6_boundary.csv and writes figures/fig6_boundary.{fig,pdf,png}.
% Top: mean primary clearing time of the fixed design, the best two-group policy and own
% settings per state (missing where no such design is fully selective or cannot be graded);
% hollow markers: the fixed design fails to trip some faults. Bottom: smallest remote-backup
% sensitivity factor of the fixed design.

%% ---------------- USER SETTINGS ----------------
legendText = {'fixed design', 'best 2 groups', 'own settings per state', 'k_f = 1.2', 'k_f = 2.0'};
xLabel     = 'hub size / hosting limit';
yLabelTop  = {'mean primary', 'clearing time (ms)'};
yLabelBot  = {'fixed design: min.', 'backup sensitivity'};
panelTitle = 'S_{sc} = %g MVA';
txtFeas    = {'voltage-', 'feasible'};
txtFail    = {'fixed design', 'misses faults'};
txtReq     = 'required 1.2';
colFixed   = [42 120 214]/255;    % blue
colBest2   = [235 104 52]/255;    % orange
colPS      = [27 175 122]/255;    % green
colReq     = [227 73 72]/255;     % red
shadeFeas  = [240 239 236]/255;   % light grey
shadeFail  = [251 227 226]/255;   % light red
fontName   = 'Times New Roman';
fontSize   = 8;
figSize    = [7.0 4.1];           % inches
%% -----------------------------------------------

here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
T = readtable(fullfile(here, 'data', 'fig6_boundary.csv'), 'TextType', 'string');
T = T(T.load_flow_solved == 1, :);
outDir = fullfile(here, 'figures'); if ~exist(outDir, 'dir'), mkdir(outDir); end

ssc = unique(T.ssc_MVA)'; kfs = unique(T.kf)'; styles = {'-', '--'};
mmax = max(T.m);
fig = figure('Units', 'inches', 'Position', [1 1 figSize], 'Color', 'w', 'Name', 'Fig. 6 boundary');
tl = tiledlayout(fig, 2, numel(ssc), 'TileSpacing', 'compact', 'Padding', 'compact');
axTop = gobjects(1, numel(ssc)); axBot = gobjects(1, numel(ssc));
for c = 1:numel(ssc)
    axTop(c) = nexttile(tl, c); axBot(c) = nexttile(tl, numel(ssc) + c);
    a1 = axTop(c); a2 = axBot(c); hold(a1, 'on'); hold(a2, 'on');
    D = T(T.ssc_MVA == ssc(c), :);
    bad = D.m(D.fixed_all_selective == 0);
    for a = [a1 a2]
        yl = [0 1e4];                                % shading drawn tall, then clipped by ylim
        patch(a, [0 1 1 0], [yl(1) yl(1) yl(2) yl(2)], shadeFeas, 'EdgeColor', 'none', 'HandleVisibility', 'off');
        if ~isempty(bad)
            patch(a, [min(bad)-0.25 3.2 3.2 min(bad)-0.25], [yl(1) yl(1) yl(2) yl(2)], shadeFail, ...
                  'EdgeColor', 'none', 'HandleVisibility', 'off');
        end
    end
    for i = 1:numel(kfs)
        E = sortrows(D(D.kf == kfs(i), :), 'm');
        plot(a1, E.m, E.fixed_mean_t_ms, styles{i}, 'Color', colFixed, 'LineWidth', 1.4);
        nb = E.fixed_all_selective == 0;
        plot(a1, E.m(nb), E.fixed_mean_t_ms(nb), 'o', 'MarkerSize', 4, 'MarkerFaceColor', 'w', ...
             'MarkerEdgeColor', colFixed, 'LineWidth', 1.1);
        ok = ~isnan(E.best2_mean_t_ms);
        plot(a1, E.m(ok), E.best2_mean_t_ms(ok), styles{i}, 'Color', colBest2, 'LineWidth', 1.4);
        ok = ~isnan(E.per_state_mean_t_ms);
        plot(a1, E.m(ok), E.per_state_mean_t_ms(ok), styles{i}, 'Color', colPS, 'LineWidth', 1.4, ...
             'Marker', 'o', 'MarkerSize', 2.5, 'MarkerFaceColor', colPS);
        plot(a2, E.m, E.fixed_min_backup_sensitivity, styles{i}, 'Color', colFixed, 'LineWidth', 1.4, ...
             'Marker', 'o', 'MarkerSize', 2.5, 'MarkerFaceColor', colFixed);
    end
    yline(a2, 1.2, '-', 'Color', colReq, 'LineWidth', 0.9);
    title(a1, sprintf(panelTitle, ssc(c)), 'FontWeight', 'normal', 'HorizontalAlignment', 'left', ...
          'Units', 'normalized', 'Position', [0 1.0 0]);
    xlabel(a2, xLabel);
    for a = [a1 a2]
        xlim(a, [0.4, mmax + 0.1]); grid(a, 'on'); a.XGrid = 'off'; box(a, 'off'); a.Layer = 'top';
        set(a, 'FontName', fontName, 'FontSize', fontSize, 'TickDir', 'out', 'GridColor', [0.89 0.89 0.87], 'GridAlpha', 1);
    end
end
linkaxes(axTop, 'y'); linkaxes(axBot, 'y'); linkaxes([axTop axBot], 'x');
yt = [min(T.fixed_mean_t_ms) max(T.fixed_mean_t_ms)]; ylim(axTop(1), [yt(1) - 20, yt(2) + 40]);
ys = [min(T.fixed_min_backup_sensitivity) max(T.fixed_min_backup_sensitivity)]; ylim(axBot(1), [ys(1) - 0.1, ys(2) + 0.15]);
for c = 1:numel(ssc)
    a1 = axTop(c); a2 = axBot(c); D = T(T.ssc_MVA == ssc(c), :); bad = D.m(D.fixed_all_selective == 0);
    y1 = ylim(a1);
    text(a1, 0.7, y1(2) - 0.04*diff(y1), txtFeas, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
         'FontName', fontName, 'FontSize', fontSize - 2, 'Color', [82 81 78]/255);
    if ~isempty(bad)
        text(a1, min(bad) + 0.12, y1(1) + 0.06*diff(y1), txtFail, 'HorizontalAlignment', 'center', ...
             'VerticalAlignment', 'bottom', 'FontName', fontName, 'FontSize', fontSize - 2, 'Color', [82 81 78]/255);
    end
    text(a2, 0.45, 1.23, txtReq, 'VerticalAlignment', 'bottom', 'FontName', fontName, 'FontSize', fontSize - 2, ...
         'Color', [82 81 78]/255);
end
ylabel(axTop(1), yLabelTop); ylabel(axBot(1), yLabelBot);
for a = [axTop(2:end) axBot(2:end)], a.YTickLabel = []; end
for a = axTop, a.XTickLabel = []; end
% legend built from proxy lines (not drawn) so that it lists colours and line styles separately
hold(axTop(end), 'on');
p = gobjects(1, 5);
p(1) = plot(axTop(end), NaN, NaN, '-', 'Color', colFixed, 'LineWidth', 1.4);
p(2) = plot(axTop(end), NaN, NaN, '-', 'Color', colBest2, 'LineWidth', 1.4);
p(3) = plot(axTop(end), NaN, NaN, '-', 'Color', colPS, 'LineWidth', 1.4, 'Marker', 'o', 'MarkerSize', 2.5, 'MarkerFaceColor', colPS);
p(4) = plot(axTop(end), NaN, NaN, '-', 'Color', [82 81 78]/255, 'LineWidth', 1.2);
p(5) = plot(axTop(end), NaN, NaN, '--', 'Color', [82 81 78]/255, 'LineWidth', 1.2);
lg = legend(axTop(end), p, legendText, 'Orientation', 'horizontal', 'Box', 'off', 'FontName', fontName, 'FontSize', fontSize - 1);
lg.Layout.Tile = 'north';

savefig(fig, fullfile(outDir, 'fig6_boundary.fig'));
exportgraphics(fig, fullfile(outDir, 'fig6_boundary.pdf'), 'ContentType', 'vector');
exportgraphics(fig, fullfile(outDir, 'fig6_boundary.png'), 'Resolution', 300);
