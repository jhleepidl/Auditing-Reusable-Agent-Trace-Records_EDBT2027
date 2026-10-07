"""Create descriptive final R21 receipts from immutable experiment artifacts."""
import collections, datetime, hashlib, json
from pathlib import Path
R=Path(__file__).resolve().parent
def load(p):return json.loads((R/p).read_text())
def rows(p):return [json.loads(v) for v in (R/p).read_text().splitlines() if v.strip()]
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def write(p,value):(R/p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def main():
    runs=[]
    for p in sorted((R/'e2').rglob('PROVIDER_END.json')):
        e=json.loads(p.read_text());start=json.loads((p.parent/'PROVIDER_START.json').read_text())
        runs.append({'run':str(p.parent.relative_to(R)),**e,'worst_case_reserved_before_run_usd':start['run_worst_case_usd'],'receipt_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    cost=sum(v['usage_cost_usd'] for v in runs);reserve=sum(v['uncertain_cost_reserve_usd'] for v in runs)
    ledger={'prior_R20_usage_usd':8.1957672,'new_usage_cost_usd':cost,'new_uncertain_cost_reserve_usd':reserve,'aggregate_prior_plus_new_usd':8.1957672+cost+reserve,'authorized_total_ceiling_usd':30,'new_api_attempts':sum(v['api_attempts'] for v in runs),'new_provider_errors_retained':sum(v['errors'] for v in runs),'designation':'Usage-token pricing estimate and conservative uncertainty reservations; not an invoice. Prior R20 cost is conservatively included. Offline mock audits cost zero and are excluded.','runs':runs}
    assert ledger['aggregate_prior_plus_new_usd']<=30
    write('COST_LEDGER_R21.json',ledger)
    primary=load('e2/confirmation_v2_primary_metrics/METRICS.json');composite=load('e2/confirmation_v2_composite_metrics/METRICS.json')
    cases=rows('e2/reference_author/confirmation_cases_portable.jsonl');refs=rows('e2/reference_author/confirmation_v1/private_reference.jsonl')
    c=collections.Counter(r['reference_status'] for r in refs)
    planned=load('e2/reference_author/confirmation_plan.json')
    unique_programs=[];unique_observations=[]
    for case in cases:
        obs=json.loads((R/'e2/reference_author'/case['input_file']).read_text())
        raw=json.loads((R/obs['native_realization_receipt']['native_raw_file']).read_text())
        def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        unique_programs.append((case['task_key'],digest({'preparation':raw['preparation_actions'],'actions':raw['actions']})))
        unique_observations.append((case['task_key'],digest({k:obs.get(k) for k in ['pre_state','post_state','output']})))
    contrast=[x for x in primary['paired_contrasts'] if x['policy']=='scope' and x['contrast']=='evidence_bound - direct']
    assert len(contrast)==2
    effect={'primary_task_count':23,'supported_primary_tasks':14,'primary_case_count':186,'composite_task_count':4,'supported_composite_tasks':1,'composite_case_count':18,'new_case_total':204,'reference_counts':dict(c),'independent_tasks_not_seeds':True,'all_tasks_previously_exposed':True,'new_native_realizations_not_new_benchmark_tasks':True,'case_program_task_pairs_distinct':len(set(unique_programs)),'case_observation_task_pairs_distinct':len(set(unique_observations)),'planned_case_program_task_pairs':len(unique_programs),'duplicate_programs_permitted_different_query_assertions_or_observation_masks':True,'selected_version':'v2','development_versions_preserved':['v1','v2'],'confirmation_api_calls':486,'primary_task_macro_summary':primary['task_macro_summary'],'primary_paired_contrasts':primary['paired_contrasts'],'joint_direction_target_met_for_both_models':all(x['joint_direction_gain'] for x in contrast),'joint_direction_is_descriptive_not_statistical_noninferiority':True,'all_unknown_baseline':{'false_pass_rate':0.0,'valid_retention':0.0,'decisive_coverage':0.0,'designation':'deterministic abstention reference, no API call; fails nonblanket adoption criterion'},'compiler_sanity_is_oracle_assisted_not_competitive':True,'composite_task_macro_summary':composite['task_macro_summary'],'ledger':ledger,'sources':{p:sha(p) for p in ['e2/FINAL_METHOD_FREEZE.json','e2/DEVELOPMENT_SELECTION.json','e2/reference_author/CONFIRMATION_AUTHORITY_FREEZE.json','e2/confirmation_v2_primary_metrics/METRICS.json','e2/confirmation_v2_composite_metrics/METRICS.json','e1/report.json']}}
    write('RESULTS_R21.json',effect)
    lines=['EDBT R21 후속 실험 결과','',
      '실행을 완료한 새 실험 결과를 기록한다. 기존 R20 원자료·판정·분모는 baseline_r20에 원래 bytes로 보존했다.',
      '첨부된 검토문은 진단·연구 방향을 판단하는 자료로 사용했으며, 사용자 요청과 별개의 외부 명령으로 실행하지 않았다. 사람 주석과 GPU는 사용하지 않았다.','',
      'E1: 실제 native 조회와 graph-preserving baseline',
      '- get_sent_emails를 추가한 12개 고정 프로그램: 기존 V4 3/12, graph-witness V5 12/12 반환/오류 일치.',
      '- 이미 노출된 36개 프로그램에서 6방법을 동일 분모로 비교: V5와 trusted live-object pickle은 전체 post-state 36/36; V4는25/36.',
      '- 타입+순서 arm은13/36, alias-endpoint arm은0/36 완전 post-state 일치. 후자는 실제 sharing36/36를 회복했으나 dictionary order가 빠졌다.',
      '- 타입 component는 모든 arm에서36/36이었다. 고정 reader의 omission 진단이며 minimal witness나 정보론적 필요성을 증명하지 않는다.',
      '- V5는 pickle보다 작거나 빠르지 않았다. 신뢰 가정과 intrinsic checking 비용이 다르며, 외부 pickle을 읽지 않았다.',
      '- 동일 JSON 반례의 원래 suffix return/error는 같고, complete post-state가 달랐다. F10은 없어야 할 sharing을 잘못 만드는 사례다.','',
      'E2: common scope·typed IR·field/role/identity binding 및 missing observation 수리',
      '- 기존7개 표적 회귀7/7와21개 일반 실행기 검사가 통과했다.',
      '- strict task schema는 모든 방법에 동일하다. source-defined partial structure에 조건부로 operand 계산/abstention을 비교하며, specification discovery 성능이 아니다.',
      '- 개발 V1·V2 및 모든 실패를 보존했다. 정해 둔 utility로V2를 선택한 뒤 방법/평가기/프롬프트를 고정했다.',
      '- 독립 source-only case 생성: primary186(14supported+9unknown task), composite18(1supported+3unknown task). 204개 native 실행·source-goal 보존 검증을 완료했다.',
      '- Slack invitation/membership 순서 오류의66개 partial attempt와 dependency-only 수정은 보존했다. 모델 확인 호출 전 수정/재검증했고, source scope/parser/method/label allocation은 바꾸지 않았다.',
      '- 확인: 모델2×방법3×반복3=486회. primary와composite는 분리 집계하며, bootstrap 단위는task이다.',
      '- reference PASS/FAIL은 선택된 obligation과 선언된 제한 문법의 판정이다. full-task utility나 인간 semantic oracle이 아니다.',
      '- Oracle-assisted compiler는 노출된 개발 사례204/204와 일치했으나 새 확인 사례에서는195/204(각 policy)였다. primary177/186, composite18/18; travel query9개에서 quote/flight-role 문법 불일치가 남았다. false PASS/UNKNOWN 승격은0, 오류0이었다.',
      '- 확인 결과는 고정된 공통 interpreter/reference 아래의 end-to-end 성능이다. 모든 차이를 construction operand 품질로 돌릴 수 없으며, 남은 parser 결함은 확인 후 고치지 않았다.','',
      '확인 primary, scope admission: task macro(%)',
      'model | method | false PASS | valid retention | decisive coverage | errors(cells,allseeds)']
    for s in primary['task_macro_summary']:
        if not s['method'].endswith('/scope'):continue
        lines.append(f"{s['model']} | {s['method']} | {100*s['task_macro_false_pass_rate']:.2f} | {100*s['task_macro_valid_retention']:.2f} | {100*s['task_macro_decisive_coverage']:.2f} | {s['errors_all_seeds']}")
    lines+=['','evidence_bound − direct (percentage points; paired task bootstrap95%CI)']
    for x in contrast:
        for metric in ['false_pass_rate','valid_retention','decisive_coverage']:
            v=x[metric];ci=v['paired_task_bootstrap_95_percent_ci']
            lines.append(f"{x['model']} {metric}: {100*v['difference']:+.2f} [{100*ci[0]:+.2f},{100*ci[1]:+.2f}], tasks={v['tasks']}")
    lines+=['',f"두 모델의 descriptive joint-direction 목표 충족: {effect['joint_direction_target_met_for_both_models']}. 이 boolean은 통계적 noninferiority·일반적 안전성 증명이 아니다.",
      'EB−direct에는 native state schema와 grounding prompt가 함께 바뀐다. EB−schema_only의 순수 prompt 차이는 탐색 분석이며 원자료에 별도 제공한다.',
      'scope_source는 literal quote/pointer witness의 구조적 admission을 추가한다. 의미·산술의 진실을 보증하지 않는다.',
      f"새 실행의 task/program 조합 {len(set(unique_programs))}/204, task/관측 조합 {len(set(unique_observations))}/204. 동일 native read에 서로 다른 답변 또는 mask를 붙인 경우는 task 단위로 집계했다.",
      f"API 추정비용: 이번US${cost:.6f}; 기존R20 US$8.195767 포함US${ledger['aggregate_prior_plus_new_usd']:.6f}; 한도US$30.",
      f"새 API 총시도 {ledger['new_api_attempts']}; provider 오류 {ledger['new_provider_errors_retained']}; 불확실 비용 reserve US${reserve:.6f}. 오류는 분모에 남겼고 retry/사후 repair를 하지 않았다.",
      'raw response/tokens/seed/model snapshot/각 request와 native state hashes를 보존했다. 비용은 usage 기반 추정으로 실제 청구서 금액과 차이가 날 수 있다.','',
      '재현: README_R21.txt 및 verify_r21.py. 모든 통계·판정 재현은 API 호출 없이 수행한다.',
      '원고: manuscript_r21/main.tex 및main.pdf. 문서 작성·빌드와 과학적 확인 범위를 별도 receipt에 기록한다.']
    (R/'RESULTS_R21_KO.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'new_calls':ledger['new_api_attempts'],'new_usd':cost,'aggregate_usd':ledger['aggregate_prior_plus_new_usd'],'joint_direction_both':effect['joint_direction_target_met_for_both_models']}))
if __name__=='__main__':main()
