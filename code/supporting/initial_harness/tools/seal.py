#!/usr/bin/env python3
"""Freeze all files of a specified study directory before evaluation.
A hash receipt detects later changes. It does not prove blinding or trusted time.
Keep builder inputs, test fixtures, and independent reference in separate dirs.
"""
from pathlib import Path
import argparse
from common_handoff import sha,write,load,utc

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--verify',action='store_true');a=p.parse_args();root=a.directory.resolve()
    current={str(f.relative_to(root)):sha(f) for f in sorted(root.rglob('*')) if f.is_file() and f.resolve()!=a.receipt.resolve()}
    if a.verify:
        if load(a.receipt)['files']!=current:raise ValueError('Frozen file inventory/hash mismatch')
        print('FROZEN_FILES_MATCH')
    else:
        if a.receipt.exists():raise FileExistsError('Do not overwrite a freeze receipt')
        write(a.receipt,{'created_utc':utc(),'files':current,'limits':'Integrity receipt; not time attestation or blinding proof'})
        print('SEALED',len(current),'files')
if __name__=='__main__':main()
