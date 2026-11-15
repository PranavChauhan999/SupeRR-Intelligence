"""Explain the frozen score by calendar year and league without changing it."""
import argparse,json
from pathlib import Path
from pipeline import load,ledger,prepare,pressure,events
def build(source,base):
    snapshot=json.loads((base/'snapshot.json').read_text())
    raw,audit=load(source);d=prepare(ledger(raw),audit);d['press']=pressure(d)
    by_player={}
    for role in ['bat','bowl']:
        f=events(d,role);q=f.groupby(['id','year','league','press']).agg(balls=('balls','sum'),runs=('runs','sum'),wickets=('wickets','sum'),v=('value','sum')).reset_index()
        for pid,rows in q.groupby('id'):
            by_player[f'{role}/{pid}']=[dict(year=int(year),league=league,pressure=bool(press),balls=int(balls),runs=int(runs),wickets=int(wickets),value=round(float(v),6)) for _,year,league,press,balls,runs,wickets,v in rows.itertuples(index=False,name=None)]
    for pl in snapshot['players']:
        rows=[s for s in by_player[f"{pl['role']}/{pl['id']}"] if s['pressure']]
        for k in ['balls','wickets','runs']:
            if sum(s[k] for s in rows)!=pl[k]:raise ValueError(f"Split does not reconcile: {pl['name']} {k}")
    (base/'splits.json').write_text(json.dumps({'freeze':snapshot['freeze'],'by_player':by_player},separators=(',',':')))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('folder',type=Path);a=p.parse_args();build(a.source,a.folder)
