"""Read-only portable byte and CPU verification; never reads model/reference data."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    reports=[]
    for directory,filename in [(HERE.parent/'derivation','RUNTIME_V1_FREEZE.json'),(HERE,'RUNTIME_V2_FREEZE.json')]:
        freeze=json.loads((directory/filename).read_text())
        for name,expected in freeze['files'].items():
            actual=hashlib.sha256((directory/name).read_bytes()).hexdigest()
            reports.append({'file':str((directory/name).relative_to(HERE.parent)), 'pass':actual==expected})
    run=subprocess.run([sys.executable,'-m','unittest','-q','test_runtime'],cwd=HERE,capture_output=True,text=True)
    report={'passed':all(r['pass'] for r in reports) and run.returncode==0,
            'file_hash_checks':len(reports),'file_hash_failures':[r for r in reports if not r['pass']],
            'CPU_tests_pass':run.returncode==0,'CPU_output':run.stdout+run.stderr,
            'model_outputs_or_private_reference_read':False,'writes':False}
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
