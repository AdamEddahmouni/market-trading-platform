function imp_matlab_parity_smoke(package_dir, output_path)
%IMP_MATLAB_PARITY_SMOKE Governed parity statistics for Research Export v1 (no labels in features).
    handoff_path = fullfile(package_dir, 'matlab_handoff_manifest.json');
    if ~isfile(handoff_path)
        error('MATLAB_HANDOFF_MANIFEST_MISSING');
    end
    handoff = jsondecode(fileread(handoff_path));
    export_id = string(handoff.export_id);

    feature_path = fullfile(package_dir, 'feature_snapshots.json');
    outcome_path = fullfile(package_dir, 'realized_outcomes.json');
    features = jsondecode(fileread(feature_path));
    outcomes = jsondecode(fileread(outcome_path));

    close_sum = 0.0;
    close_count = 0;
    for i = 1:numel(features)
        values = features(i).feature_values;
        if isfield(values, 'bar_close')
            close_sum = close_sum + imp_json_scalar(values.bar_close);
            close_count = close_count + 1;
        end
    end

    forward_sum = 0.0;
    forward_count = 0;
    macro_actual_sum = 0.0;
    macro_count = 0;
    for i = 1:numel(outcomes)
        if isfield(outcomes(i), 'forward_return') && ~isempty(outcomes(i).forward_return)
            forward_sum = forward_sum + imp_json_scalar(outcomes(i).forward_return);
            forward_count = forward_count + 1;
        end
        if isfield(outcomes(i), 'actual') && ~isempty(outcomes(i).actual)
            macro_actual_sum = macro_actual_sum + imp_json_scalar(outcomes(i).actual);
            macro_count = macro_count + 1;
        end
    end

    manifest_path = fullfile(package_dir, 'research_export_manifest.json');
    manifest = jsondecode(fileread(manifest_path));
    meta = manifest.metadata;

    stats = struct( ...
        'feature_row_count', numel(features), ...
        'outcome_row_count', numel(outcomes), ...
        'bar_close_sum', close_sum, ...
        'bar_close_count', close_count, ...
        'forward_return_sum', forward_sum, ...
        'forward_return_count', forward_count, ...
        'macro_actual_sum', macro_actual_sum, ...
        'macro_actual_count', macro_count);

    result = struct();
    result.schema_version = 'matlab_research_result/1.0.0';
    result.matlab_result_contract = 'research_export_v1_matlab_result/1.0.0';
    result.export_id = char(export_id);
    result.hypothesis_id = strcat(string(manifest.experiment_id), ':', string(manifest.export_profile));
    result.experiment_id = char(string(manifest.experiment_id));
    result.analysis_type = 'parity_reference_statistics';
    result.input_manifest_hash = char(string(manifest.manifest_hash));
    result.input_source_sha256 = char(string(manifest.source_sha256));
    result.dataset_lineage = struct( ...
        'export_id', char(export_id), ...
        'manifest_hash', char(string(manifest.manifest_hash)), ...
        'source_sha256', char(string(manifest.source_sha256)), ...
        'dataset_hash', '', ...
        'experiment_id', char(string(manifest.experiment_id)), ...
        'export_profile', char(string(manifest.export_profile)));
    result.parameters = struct( ...
        'analysis_source', 'matlab_smoke', ...
        'code_identity', 'research/matlab/smoke/imp_matlab_parity_smoke.m', ...
        'decision_time_feature_fields', {{'feature_values.bar_close'}}, ...
        'label_fields_excluded_from_features', {{'forward_return', 'actual', 'label_available_time_ns'}}, ...
        'pit_operator_status', char(string(meta.pit_status)), ...
        'evidence_class', char(string(meta.evidence_class)));
    result.result_values = struct( ...
        'reference_statistics', stats, ...
        'parity_contract', 'research_export_v1_matlab_parity/1.0.0');
    result.uncertainty = struct('status', 'NOT_COMPUTED', 'reason', 'DETERMINISTIC_PARITY_SMOKE');
    result.diagnostics = struct( ...
        'feature_row_count', numel(features), ...
        'outcome_row_count', numel(outcomes), ...
        'lookahead_guard', 'LABEL_FIELDS_NOT_IN_FEATURE_SNAPSHOTS');
    result.runtime = struct( ...
        'matlab_release', char(version('-release')), ...
        'matlab_root', char(matlabroot), ...
        'toolbox_manifest_recorded', false);
    result.generated_at = char(datetime('now', 'TimeZone', 'UTC', 'Format', "yyyy-MM-dd'T'HH:mm:ss'Z'"));
    result.authority_class = 'EVIDENCE_NOT_PREDICTION';
    result.pit_class = 'NON_EMPIRICAL_FIXTURE_OPERATOR_PENDING';

    json_text = jsonencode(result);
    fid = fopen(output_path, 'w');
    if fid < 0
        error('MATLAB_RESULT_WRITE_FAILED');
    end
    fwrite(fid, json_text, 'char');
    fclose(fid);
end

function value = imp_json_scalar(value)
    if ischar(value) || isstring(value)
        value = str2double(value);
    else
        value = double(value);
    end
end
