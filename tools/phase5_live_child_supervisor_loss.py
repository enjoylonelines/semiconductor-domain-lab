"""Inject Supervisor loss only after proving its recorded OpenSTA child is alive."""
from __future__ import annotations
import argparse, json, subprocess, time
from pathlib import Path

def run(*args): return subprocess.run(args, text=True, capture_output=True, check=False)
def query(pg):
    sql="SELECT supervisor_id,process_pid FROM eda_execution_requests WHERE status='RUNNING' AND supervisor_id LIKE 'phase5-supervisor-%' AND process_pid IS NOT NULL ORDER BY process_started_at DESC LIMIT 1"
    result=run('docker','exec',pg,'psql','-U','eda','-d','eda_m1','-At','-F','|','-c',sql)
    if result.returncode or not result.stdout.strip(): return None
    supervisor,pid=result.stdout.strip().split('|',1); return supervisor,int(pid)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--result-command',required=True); p.add_argument('--postgres',default='eda-multihost-m1-postgres-1'); p.add_argument('--timeout-seconds',type=float,default=30); p.add_argument('--injection-evidence', type=Path); args=p.parse_args()
    workload=subprocess.Popen(args.result_command,shell=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+args.timeout_seconds; target=None; observations=[]
    while time.monotonic()<deadline:
        candidate=query(args.postgres)
        if candidate:
            supervisor,pid=candidate
            alive=run('docker','exec',supervisor,'sh','-c',f'kill -0 {pid}')
            observations.append({'supervisor': supervisor, 'pid': pid, 'alive': alive.returncode == 0})
            if alive.returncode==0:
                observed_at=time.time()
                if args.injection_evidence:
                    args.injection_evidence.write_text(json.dumps({'supervisor': supervisor, 'pid': pid, 'observed_at': observed_at, 'precondition': 'docker exec supervisor kill -0 pid succeeded'}, sort_keys=True) + '\n')
                killed=run('docker','kill',supervisor)
                if killed.returncode==0: target={'supervisor':supervisor,'pid':pid,'observed_at':observed_at}; break
        time.sleep(.25)
    stdout,stderr=workload.communicate(timeout=360)
    outcome={'injection':target,'observations':observations[-20:],'workload_stdout':stdout,'workload_stderr':stderr}
    print(json.dumps(outcome,sort_keys=True))
    if target is None: raise SystemExit('no live child was observed; no fault was injected')
if __name__=='__main__': main()
