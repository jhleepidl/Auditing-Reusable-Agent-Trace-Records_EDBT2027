"""Write compact CSVs from verified checkpoint rows and scoped replay metrics."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any
from release_io import Inputs, load, write as write_json

ARM_NAMES = {'type_order':'Type + order','v4_control':'Constructor',
             'full_witness':'Captured witness','trusted_pickle':'Trusted pickle',
             'type_sharing':'Type + sharing','sharing_order':'Sharing + order','json_only':'JSON-only','alias_endpoint_types':'Sharing endpoint types'}
POLICY_NAMES = {'old':'Original','topology':'DAG ordering',
                'addressing':'Metadata addressing','combined':'Both'}
STAGE_NAMES = {'development_v2':'Development','confirmation_fresh':'One call',
               'feedback_round1':'First call','feedback_round2':'With diagnostics',
               'review_only_control':'Review only','transfer_v2':'Transfer'}


def csv_file(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:
        raise ValueError('Refusing empty CSV: '+str(path))
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def export(artifact: Inputs, checkpoint: dict[str, Any], output: Path,
           fresh_frontend: Path | None = None) -> dict[str, Any]:
    table_dir=output/'tables'
    checkpoint_rows=[]
    for arm, row in checkpoint['checkpoint_summary'].items():
        checkpoint_rows.append({'reader':ARM_NAMES.get(arm,arm),
                               'programs':checkpoint['checkpoint_programs'],
                               'prefix_values_exact':row['prefix_json_exact'],
                               'suffix_state_exact':row['suffix_state_exact'],
                               'suffix_returns_exact':row['returns_errors_exact'],
                               'suffix_graph_exact':row['suffix_graph_exact']})
    csv_file(table_dir/'checkpoint_recovery.csv',checkpoint_rows)
    csv_file(table_dir/'read_recovery.csv',[
        {'reader':ARM_NAMES.get(arm,arm),'programs':checkpoint['read_denominator'],
         'exact_native_reads':n} for arm,n in checkpoint['read_agreement'].items()])
    csv_file(table_dir/'warm_costs.csv',[
        {'reader':ARM_NAMES.get(arm,arm),'capture_ms':row['median_program_capture_ms'],
         'restore_ms':row['median_program_restore_ms'],
         'serialized_bytes':row['median_serialized_bytes'],
         'gzip_bytes':row['median_gzip_bytes']} for arm,row in checkpoint['cost_summary'].items()])
    if fresh_frontend is None:
        return {'checkpoint_tables':'Recomputed from retained native and restored observations.', 'frontend_tables':'Not executed in --check-only mode.'}
    summary=load(fresh_frontend)
    rows=[]
    for row in summary['summaries']:
        rows.append({'stage':STAGE_NAMES.get(row['stage'],row['stage']),
                     'policy':POLICY_NAMES.get(row['policy'],row['policy']),
                     'model':row['model'],'method':row['method'],'templates':row['tasks'],
                     'valid_retention_pct':round(100*row['task_macro_valid_retention'],6),
                     'false_pass_pct':round(100*row['task_macro_false_pass_rate'],6),
                     'decisive_coverage_pct':round(100*row['task_macro_decisive_coverage'],6),
                     'errors':row['errors_all_cells'],'unknowns':row['unknown_all_cells'],
                     'unknown_reference_promotions':row['unresolved_promoted_all_cells']})
    csv_file(table_dir/'frontend_metrics.csv',rows)
    csv_file(table_dir/'table6_one_call.csv',[r for r in rows if r['stage']=='One call' and r['policy']=='Original' and r['method'] in ('literal','derived')])
    csv_file(table_dir/'table7_review.csv',[r for r in rows if r['stage'] in ('First call','Review only','With diagnostics') and r['policy']=='Original' and r['method'] in ('literal','derived')])
    csv_file(table_dir/'table8_frontend_retention.csv',[
        r for r in rows if r['method']=='derived' and r['stage'] in ('One call','With diagnostics')])
    primary={}
    for row in rows:
        if row['stage']=='One call' and row['method']=='derived':
            primary.setdefault(row['model'],{})[row['policy']]=row['valid_retention_pct']
    return {'checkpoint_tables':'Recomputed from retained native and restored JSON; no fresh execution or timings.',
            'frontend_tables':('Re-executed from frozen candidates.' if fresh_frontend
                               else 'Read from retained metrics; use --cpu to re-execute.'),
            'primary_program_retention_percent':primary}
