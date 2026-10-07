"""Independent source-decidability probes; never candidate predictions."""
import copy
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
from source_reference import SOURCE, SCOPES, evaluate
HERE=Path(__file__).resolve().parent


def probes():
    key='travel/user_task_14'; r=SOURCE[key]['rules'][0]['records'][0]
    entity=r['entity']; rating=r['facts']['rating']; total=r['facts']['total']
    correct=f'[{SCOPES[key]["obligations"][0]["binding_role"]}] {entity} — rating {rating} points, total {total} EUR for 7 days'
    cases=[
      ('role_unit_time_exact',correct,'pass','source company/rating/seven-day total match each immutable role; recognized qualifiers'),
      ('currency_dimension',correct.replace(' EUR',' GBP'),'pass','common monetary dimension intentionally does not certify literal currency'),
      ('field_record_order',f'{entity} — total {total} over 7 days, score {rating} points','pass','same source entity and exact fields; bounded aliases and time normalization'),
      ('quoted_wrong_then_correct',f'> {entity} — rating 0 USD\n'+correct,'pass','quoted record is mention-only; affirmative source facts still present'),
      ('negative_assertion',f'Not: {entity} — rating {rating}, total {total}','fail','explicit negative required fact conflicts with affirmative source obligation'),
      ('field_negation',f'{entity} — rating is not {rating}, total {total}','fail','bounded field negation is an asserted contradiction'),
      ('wrong_dimension',correct.replace(' points',' USD'),'fail','rating_points source obligation conflicts with monetary qualifier'),
      ('wrong_duration',correct.replace('7 days','11 days'),'fail','source request duration is seven days; recognized explicit different time conflicts'),
      ('wrong_role_same_values',correct.replace('[la_electric_company]','[la_suv_company]'),'fail','same values on a distinct selection role do not satisfy the source role'),
      ('duplicate_contradiction',correct+f'\n{entity} — rating {rating+0.01}','fail','correct assertion cannot erase explicit conflict on same source-bound property'),
      ('quoted_only','> '+correct,'fail','complete observed quoted record supplies no affirmative asserted facts'),
      ('empty_record',entity+' — ','fail','fully observed complete bounded entity record omits required facts'),
      ('empty_output','','fail','fully observed empty answer omits all affirmative facts'),
      ('unavailable_output',None,'unknown','whole output is unavailable; no absence inferred'),
      ('free_prose',f'I might be considering {entity}; details are uncertain.','unknown','outside finite assertion grammar; no free-prose semantic inference'),
      ('property_alias_in_subject',f'{entity} rating {rating} total {total}','unknown','numeric co-occurrence without bounded field/entity delimiter is outside grammar'),
      ('unknown_qualifier',correct+' according to a recent report','unknown','unrecognized fragment on incomplete target record is outside bounded grammar'),
    ]
    result=[]
    for name,output,expected,justification in cases:
        actual=evaluate(key,{'pre_state':None,'post_state':None,'output':output})['reference_status']
        result.append({'probe':name,'task_key':key,'output':output,'expected_source_status':expected,'actual_source_status':actual,
                       'source_decidable':expected!='unknown','out_of_grammar':name in ['free_prose','property_alias_in_subject','unknown_qualifier'],
                       'source_justification':justification,'passed':actual==expected})
    return result

if __name__=='__main__':
    rows=probes()
    target=HERE/'grammar_probe_results.json'
    if target.exists():raise SystemExit('Probe receipt already exists; no overwrite.')
    target.write_text(json.dumps({'designation':'source-only bounded grammar assurance, not competitive or confirmation data','probes':rows,'count':len(rows),'passed':sum(r['passed'] for r in rows)},indent=2)+'\n')
    print(json.dumps({'probes':len(rows),'passed':sum(r['passed'] for r in rows),'failures':[r['probe'] for r in rows if not r['passed']]}))
