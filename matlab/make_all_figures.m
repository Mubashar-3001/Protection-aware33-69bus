%% Rebuild Figs. 2-6 of the paper in MATLAB from the CSV files in data/.
% Each fig*.m script starts with a USER SETTINGS block (legend text, axis labels,
% colours, font, size). Edit it and rerun the script; the figure is saved to
% figures/ as .fig (editable in MATLAB), .pdf (vector) and .png (300 dpi).
% The CSV files are exported by src/export_data.py from the results of the
% Python study, so they always match the numbers in the manuscript.
% Fig. 1 (one-line diagrams) is not a data plot: see ../diagrams (draw.io, Graphviz).
here = fileparts(mfilename('fullpath')); if isempty(here) || ~isfolder(fullfile(here, 'data')), here = pwd; end
scripts = {'fig2_hosting', 'fig3_impact', 'fig4_policy_size', 'fig5_gain_risk', 'fig6_boundary'};
for k = 1:numel(scripts)
    fprintf('running %s ...\n', scripts{k});
    runIsolated(fullfile(here, [scripts{k} '.m']));
end
fprintf('done: figures written to %s\n', fullfile(here, 'figures'));

function runIsolated(scriptPath)
% runs one figure script in its own workspace
run(scriptPath);
end
