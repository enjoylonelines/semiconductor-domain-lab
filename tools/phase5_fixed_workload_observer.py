"""Observe fixed Heavy workload batches without changing operational state contracts."""
from __future__ import annotations
import argparse, json, os, subprocess, threading, time
from statistics import quantiles


def command(*args):
    return subprocess.check_output(args, text=True).strip()

def percentile(values, q):
    values=sorted(values)
    if not values: return None
    index=round((len(values)-1)*q)
    return values[index]

def sample(stop, rows, names, pg):
    while not stop.wait(.25):
        stats=command('docker','stats','--no-stream','--format','{{json .}}',*names).splitlines()
        query="SELECT count(*) FILTER (WHERE wait_event_type='Lock'), count(*) FILTER (WHERE state='active'), count(*) FROM pg_stat_activity WHERE datname='eda_m1'"
        raw=command('docker','exec',pg,'psql','-U','eda','-d','eda_m1','-At','-F',',','-c',query)
        lock,active,connections=(int(x) for x in raw.split(','))
        rows.append({'at':time.time(),'containers':[json.loads(x) for x in stats],'lock_waits':lock,'active_connections':active,'connections':connections})

def queue_waits(job_ids, pg):
    quoted=','.join("'" + job_id.replace("'", "''") + "'" for job_id in job_ids)
    raw=command('docker','exec',pg,'psql','-U','eda','-d','eda_m1','-At','-F',',','-c',f"SELECT job_id,claimed_at-created_at FROM eda_execution_requests WHERE job_id IN ({quoted})")
    return {job_id:float(wait) for job_id,wait in (line.split(',',1) for line in raw.splitlines() if line)}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--workers',type=int,required=True); p.add_argument('--repeats',type=int,default=3); p.add_argument('--jobs',type=int,default=8); p.add_argument('--result-command',required=True); args=p.parse_args()
    names=[f'phase5-supervisor-{n}' for n in range(1,args.workers+1)]
    batches=[]
    for repeat in range(args.repeats):
        rows=[]; stop=threading.Event(); thread=threading.Thread(target=sample,args=(stop,rows,names,'eda-multihost-m1-postgres-1'),daemon=True); thread.start()
        started=time.perf_counter(); output=subprocess.check_output(args.result_command,shell=True,text=True); elapsed=time.perf_counter()-started
        stop.set(); thread.join(2); result=json.loads(output.strip().splitlines()[-1]); waits=queue_waits([item['job_id'] for item in result['terminal']],'eda-multihost-m1-postgres-1'); batches.append({'repeat':repeat+1,'observer_elapsed_seconds':elapsed,'result':result,'queue_wait_seconds':waits,'samples':rows})
    makespans=[b['result']['elapsed_seconds'] for b in batches]
    latencies=[b['result']['elapsed_seconds']/args.jobs for b in batches]
    waits=[value for batch in batches for value in batch['queue_wait_seconds'].values()]
    print(json.dumps({'scope':'fixed Heavy Runs; same-VM container experiment','workers':args.workers,'jobs':args.jobs,'repeats':args.repeats,'p50_makespan_seconds':percentile(makespans,.5),'p95_makespan_seconds':percentile(makespans,.95),'p50_queue_wait_seconds':percentile(waits,.5),'p95_queue_wait_seconds':percentile(waits,.95),'batches':batches},sort_keys=True))
if __name__=='__main__': main()
