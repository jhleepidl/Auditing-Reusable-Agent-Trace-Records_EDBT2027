"""Split frozen confirmation scores by registered task phase; no relabeling."""
import argparse
from pathlib import Path
from common21 import rows, load, write_rows, write, sha

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    refs=rows(a.reference); preds=rows(a.predictions)
    receipt=load(a.predictions.parent/'RECEIPT.json')
    assert not a.out.exists()
    all_ids={r['case_id'] for r in refs}
    assert len(all_ids)==len(refs) and {r['case_id'] for r in preds}==all_ids
    assert {r['phase'] for r in refs}=={'test','composite'}
    a.out.mkdir(parents=True)
    for phase,name in [('test','primary'),('composite','composite')]:
        gold=[r for r in refs if r['phase']==phase]
        ids={r['case_id'] for r in gold}
        predictions=[r for r in preds if r['case_id'] in ids]
        assert len(predictions)==len(gold)*len(receipt['planned_grid'])
        folder=a.out/name
        write_rows(folder/'reference.jsonl',gold)
        write_rows(folder/'predictions.jsonl',predictions)
        write(folder/'RECEIPT.json',receipt|{
            'designation':'primary confirmation' if phase=='test' else 'separate exploratory composite confirmation',
            'registered_phase':phase,'case_count':len(gold),'prediction_cells':len(predictions),
            'source_reference_sha256':sha(a.reference),
            'source_predictions_sha256':sha(a.predictions),
            'splitter_sha256':sha(__file__), 'labels_changed':False,
        })
    print({'primary_cases':sum(r['phase']=='test' for r in refs),
           'composite_cases':sum(r['phase']=='composite' for r in refs)})

if __name__=='__main__': main()
