"""Post-exposure scope/shape audit, not a relabelled R20 effectiveness result."""
from collections import Counter
from common21 import BASE, ROOT, load, rows, write, write_rows, sha
def inspect(c,t):
    ann=c.get('annotation') or {};preds=ann.get('state_predicates',[]);facts=ann.get('answer_facts',[])
    allowed=[]
    for o in t['obligations']:
        if o['kind']=='state':
            target=o['target'];allowed.append(target.get('path') or target.get('path_prefix'))
    flags=[]
    if not t['supported'] and (preds or facts): flags.append('constructs_outside_selected_scope')
    if t['supported']:
        outside=[p.get('path') for p in preds if not any(p.get('path','')==v or p.get('path','').startswith(v+'/') for v in allowed)]
        if outside:flags.append('contains_paths_outside_selected_scope_profile')
    else:outside=[p.get('path') for p in preds]
    bad_selector=sum(not isinstance(v,dict) or 'field' not in v or 'value' not in v for p in preds for v in p.get('selector',[]))
    if bad_selector:flags.append('legacy_selector_shape_incompatible')
    support=Counter(type(p.get('support')).__name__ for p in preds)
    exact_support=sum(isinstance(p.get('support'),dict) and all(k in p['support'] for k in ['request_quote','source_paths','derivation','necessity']) for p in preds)
    if facts:flags.append('scalar_query_facts_do_not_preserve_property_role_polarity')
    return {'candidate_key':[c[k] for k in ['task_key','method','model','seed']], 'public_scope_sha256':t['scope_sha256'],'selected_scope_supported':t['supported'],'state_predicates':len(preds),'outside_profile_paths':outside,'bad_selector_items':bad_selector,'support_shape_counts':dict(support),'support_four_field_objects':exact_support,'query_facts':len(facts),'diagnostic_flags':flags,'interpretation':'profile/shape screening only; no claim of semantic equivalence, no dropping failed predicates or relabelling inherited outcomes'}
def main():
    src=BASE/'e2/prospective_v2_candidates/candidates.jsonl';scope=ROOT/'e2/reference_author/scope_history/common_scopes_v1.json'
    if not scope.exists():scope=ROOT/'e2/reference_author/common_scopes.json'
    ts={t['task_key']:t for t in load(scope)['tasks']};cands=rows(src);out=[inspect(c,ts[c['task_key']]) for c in cands]
    diag=rows(BASE/'e2/prospective_v2_test_predictions/diagnostics.jsonl')
    errors=[d for d in diag if d['gate']=='hybrid' and d['engine']=='v2' and 'error' in d]
    summary={'designation':'post-exposure inherited scope and representation diagnostics; not revised construction effectiveness','candidate_count':len(out),'flags':dict(Counter(f for r in out for f in r['diagnostic_flags'])),'primary_hybrid_v2_error_cells':len(errors),'unique_error_candidate_count':len({tuple(d['candidate_key']) for d in errors}),'error_messages':dict(Counter(d['error'] for d in errors)),'inherited_candidates_sha256':sha(src),'common_scope_sha256':sha(scope),'semantic_gold_loaded':False,'inherited_results_mutated':False}
    dest=ROOT/'e2/inherited_audit';dest.mkdir(exist_ok=False);write_rows(dest/'candidate_diagnostics.jsonl',out);write(dest/'SUMMARY.json',summary);print(summary)
if __name__=='__main__':main()
