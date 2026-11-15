"""Build the frozen SupeRR snapshot from the organiser's six CSVs."""
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

CFG=dict(version="S2.1", first_score_year=2023, prior_weight=100, pressure_min=100, ordinary_min=180, match_min=10, shrink_balls=180, bootstrap=600, seed=202711, bat_wicket=7, bowl_wicket=8)
SCHEMAS={'ball_by_ball':'match_id innings innings_ball_num overid over_ball_num batting_team_id bowling_team_id striker_id striker_name non_striker_id non_striker_name bowler_id bowler_name batting_order runs extras_type extras1_runs extras_2_runs is_wicket dismissal_type dismissed_player_id pace_or_spin','matches':'match_id comp_id match_date first_inn_revised_overs second_inn_revised_overs revised_target result win_team_id','competitions':'comp_id comp_name match_format season','teams':'comp_id team_id team_name','playing_eleven':'match_id team_id player_id is_played','competition_team_player_mapping':'comp_id team_id player_id player_name'}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def load(root):
    data={}; sources={}
    for name,columns in SCHEMAS.items():
        path=root/(name+'.csv'); d=pd.read_csv(path)
        require(not(set(columns.split())-set(d.columns)),f'{name}: missing columns')
        sources[name]={'rows':len(d),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}; data[name]=d
    b,m,c,t,x,p=[data[k] for k in SCHEMAS]
    for frame,key in [(b,['match_id','innings','innings_ball_num']),(b,['match_id','innings','overid','over_ball_num']),(m,['match_id']),(c,['comp_id']),(t,['comp_id','team_id']),(p,['comp_id','team_id','player_id'])]:
        require(not frame.duplicated(key).any(),f'duplicate {key}')
    for src,ref,key in [(m,c,'comp_id'),(b,m,'match_id'),(x,m,'match_id'),(p,c,'comp_id'),(t,c,'comp_id')]:
        require(src[key].isin(ref[key]).all(),f'unresolved key {key}')
    b=b.merge(m,on='match_id',validate='many_to_one').merge(c,on='comp_id',validate='many_to_one')
    audit={'lineup_duplicate_keys':int(x.duplicated(['match_id','team_id','player_id']).sum()),'sources':sources}
    for col,team in [('striker_id','batting_team_id'),('non_striker_id','batting_team_id'),('bowler_id','bowling_team_id')]:
        def missing(keys,ref,refs):
            return int((~pd.MultiIndex.from_frame(b[keys]).isin(pd.MultiIndex.from_frame(ref[refs]))).sum())
        audit[col+'_lineup_unmatched_rows']=missing(['match_id',team,col],x,['match_id','team_id','player_id'])
        audit[col+'_squad_unmatched_rows']=missing(['comp_id',team,col],p,['comp_id','team_id','player_id'])
        require(missing(['comp_id',team],t,['comp_id','team_id'])==0,'unknown team')
    return b,audit
def ledger(b):
    b=b.sort_values(['match_id','innings','innings_ball_num']).copy()
    e=b.extras_type.fillna('None'); require(e.isin(['wide','Overstep','other','byes','legbyes','Penalty','None']).all(),'unknown extras')
    require((b[['runs','extras1_runs','extras_2_runs']]>=0).all().all(),'negative runs')
    b['team_runs']=b.runs+b.extras1_runs+b.extras_2_runs
    b['legal']=(~e.isin(['wide','Overstep','other'])).astype(int)
    b['faced']=e.ne('wide').astype(int)
    b['charge']=b.runs+b.extras1_runs.where(e.isin(['Overstep','other','wide']),0)
    b['bw']=(b.is_wicket & b.dismissal_type.isin(['Bowled','Caught','LBW','Stump','Hit Wicket'])).astype(int)
    b['sw']=(b.is_wicket & b.dismissed_player_id.eq(b.striker_id)).astype(int)
    b['nw']=(b.is_wicket & b.dismissed_player_id.eq(b.non_striker_id)).astype(int)
    g=b.groupby(['match_id','innings'])
    for name,col in [('pre','legal'),('score','team_runs'),('down','is_wicket')]: b[name]=g[col].cumsum()-b[col].astype(int)
    return b
def pressure(d,shift=0):
    left=120-d.pre; need=d.target-d.score; rr=6*need/left.clip(lower=1)
    chase=(need>0)&(rr<=18)&((rr>=10+shift)|((left<=24-6*shift)&(rr>=6+shift)&(rr<=12))|((d.down>=6)&(rr>=8+shift)))
    setting=(left<=24-6*shift)|((d.down>=5+shift)&(d.pre>=60))
    return np.where(d.innings.eq(2),chase,setting)
def prepare(b,a):
    ids=b.match_id; regulation=b.innings.isin([1,2]); b=b[regulation].copy()
    first=b[b.innings.eq(1)].groupby('match_id').team_runs.sum()
    b['target']=b.match_id.map(first)+1
    scope=b.comp_name.str.match(r'^IPL \d{4}$')|b.match_format.eq('T20I')
    revised=b[['first_inn_revised_overs','second_inn_revised_overs','revised_target']].notna().any(axis=1)|b.result.str.contains('D/L|DLS|Duckworth',case=False,na=False)
    incomplete=b.result.str.contains('abandon|no result',case=False,na=False)|b.result.isna()
    unusual=b[(b.pre>=120)|(b.down>=10)|(b.is_wicket & (b.sw+b.nw!=1))].match_id.unique()
    # Validate ordinary margins and winning team against the reconstructed regulation score.
    overs=b.groupby(['match_id','innings','overid']).legal.sum().reset_index()
    last=overs.groupby(['match_id','innings']).overid.transform('max')
    irregular=overs[(overs.overid<last)&(overs.legal!=6)].match_id.unique()
    firsts=b[b.innings==1].groupby('match_id').agg(balls=('legal','sum'),outs=('is_wicket','sum'))
    short=firsts[(firsts.balls<120)&(firsts.outs<9)].index
    bad=set(unusual)|set(irregular)|set(short);checked=0; mismatches=[]
    for mid,g in b[scope&~revised&~incomplete].groupby('match_id'):
        values=g.groupby('innings').agg(r=('team_runs','sum'),w=('is_wicket','sum'),team=('batting_team_id','first'))
        if len(values)!=2:bad.add(mid);continue
        first,second=values.itertuples(index=False,name=None); result=str(g.result.iloc[0]).lower(); winner=g.win_team_id.iloc[0]
        margin=re.search(r'(?:won\s+(?:by\s*)?|by\s*)(\d+)\s*(runs?|wickets?|wkts?)',result)
        if re.search('tied|super over',result): ok=first[0]==second[0]
        elif margin:
            num,unit=margin.groups(); defended=unit.startswith('run')
            ok=(first[0]-second[0]==int(num) and winner==first[2]) if defended else (second[0]>first[0] and 10-second[1]==int(num) and winner==second[2])
        else:ok=False
        checked+=1
        if not ok:bad.add(mid);mismatches.append(int(mid))
    keep=scope&~revised&~incomplete&~b.match_id.isin(bad)
    a.update(raw_deliveries=len(ids),super_over_rows=int((~regulation).sum()),out_of_scope_matches=int(b[~scope].match_id.nunique()),revised_matches=int(b[revised].match_id.nunique()),match_results_checked=checked,margin_mismatch_ids=mismatches,integrity_excluded_ids=sorted(map(int,bad)),retained_matches=int(b[keep].match_id.nunique()))
    d=b[keep].copy(); d['year']=pd.to_datetime(d.match_date).dt.year;d['league']=np.where(d.comp_name.str.startswith('IPL '),'IPL','T20I')
    d['phase']=np.select([d.pre<36,d.pre<90],['powerplay','middle'],default='death')
    d['order']=np.select([d.batting_order<=3,d.batting_order<=6],['top','middle'],default='lower')
    d['bat_outcome']=d.runs-CFG['bat_wicket']*d.sw; d['other_outcome']=-CFG['bat_wicket']*d.nw
    d['bowl_outcome']=CFG['bowl_wicket']*d.bw-d.charge
    for year in sorted(d.year.unique())[1:]:
        hist=d.year<year; current=d.year==year
        for metric,keys in [('bat_outcome',['league','innings','phase','order']),('other_outcome',['league','innings','phase']),('bowl_outcome',['league','innings','phase'])]:
            train=d.loc[hist]; prior=train[metric].mean(); grouped=train.groupby(keys)[metric].agg(['sum','count'])
            rates=(grouped['sum']+100*prior)/(grouped['count']+100)
            d.loc[current,metric+'_v']=d.loc[current,metric].to_numpy()-rates.reindex(pd.MultiIndex.from_frame(d.loc[current,keys])).fillna(prior).to_numpy()
    d=d[d.year>=CFG['first_score_year']].copy();a['scored_deliveries']=len(d);a['scored_matches']=d.match_id.nunique();a['pressure_deliveries']=int(pressure(d).sum());return d
def events(d,role):
    def frame(idcol,name,balls,runs,w,val):
        f=d[['match_id','year','league','press','phase','pace_or_spin','order']].copy()
        f['id']=d[idcol]; f['name']=d[name];f['balls']=balls;f['runs']=runs;f['wickets']=w;f['value']=val;return f
    if role=='bat':return pd.concat([frame('striker_id','striker_name',d.faced,d.runs,d.sw,d.bat_outcome_v),frame('non_striker_id','non_striker_name',0,0,d.nw,d.other_outcome_v)])
    return frame('bowler_id','bowler_name',d.legal,d.charge,d.bw,d.bowl_outcome_v)
def aggregate(f,role):
    sums=f.groupby(['id','match_id','press'])[['balls','runs','wickets','value']].sum()
    mat=4 if role=='bat' else 6
    p=sums.xs(True,level='press').copy();p['material']=(p.balls>=mat).astype(int);p['positive']=((p.balls>=mat)&(p.value>0)).astype(int)
    n=sums.xs(False,level='press')
    return p,n
def rating(pb,pv,nb,nv,m,k):
    pr=100*pv/np.maximum(1,pb);nr=100*nv/np.maximum(1,nb);frac=k/np.maximum(m,1)
    return (pr-.35*nr)*pb/(pb+180)*(.8+.2*frac)
def summarize(f,role):
    p,n=aggregate(f,role);s=p.groupby('id').sum().join(n.groupby('id').sum(),lsuffix='_p',rsuffix='_n',how='outer').fillna(0)
    s['score']=rating(s.balls_p,s.value_p,s.balls_n,s.value_n,s.material,s.positive);s['eligible']=(s.balls_p>=100)&(s.balls_n>=180)&(s.material>=10)
    return s.sort_values(['score','id'],ascending=[False,True]),p,n
def analyze(d,role):
    d['press']=pressure(d);f=events(d,role);s,p,n=summarize(f,role); eligible=s.index[s.eligible]; mids=np.sort(d.match_id.unique())
    # A draw samples whole matches jointly for all players and both situations.
    rng=np.random.default_rng(CFG['seed']);weights=rng.multinomial(len(mids),np.ones(len(mids))/len(mids),size=CFG['bootstrap']).T
    def draw(g,k):return g[k].unstack(fill_value=0).reindex(index=eligible,columns=mids,fill_value=0).to_numpy()@weights
    boot=rating(draw(p,'balls'),draw(p,'value'),draw(n,'balls'),draw(n,'value'),draw(p,'material'),draw(p,'positive'))
    ranks=np.argsort(np.argsort(-boot,axis=0,kind='stable'),axis=0)+1
    gain={};checks={}
    for label,shift in [('loose',-1),('strict',1)]:
        d['press']=pressure(d,shift); z,_,_=summarize(events(d,role),role);gain[label]={int(k):i+1 for i,k in enumerate(z.index[z.eligible])}
    train,_,_=summarize(f[f.year<2026],role);test,_,_=summarize(f[f.year==2026],role)
    overlap=train.index[train.eligible].intersection(test.index[(test.balls_p>=30)&(test.balls_n>=30)&(test.material>=3)])
    checks={'validation_overlap':len(overlap),'validation_spearman':round(float(spearmanr(train.loc[overlap,'score'],test.loc[overlap,'score']).statistic),3) if len(overlap)>2 else None}
    names=f.groupby('id').name.first(); pf=f[f.press];ipl=pf[pf.league=='IPL'].groupby('id').balls.sum();phase=pf.groupby(['id','phase']).balls.sum(); styles=f[f.balls>0].groupby(['id','pace_or_spin' if role=='bowl' else 'order']).balls.sum()
    rows=[]
    for i,(pid,r) in enumerate(s.iterrows()):
        ranked=pid in eligible;j=eligible.get_loc(pid) if ranked else None
        rd=lambda x:round(float(x),3)
        rows.append(dict(id=int(pid),name=names[pid],role=role,rank=j+1 if ranked else None,score=rd(r.score),balls=int(r.balls_p),normal_balls=int(r.balls_n),matches=int(r.material),positive=rd(r.positive/r.material) if r.material else None,runs=int(r.runs_p),wickets=int(r.wickets_p),pressure_rate=rd(100*r.value_p/max(1,r.balls_p)),normal_rate=rd(100*r.value_n/max(1,r.balls_n)),ipl_balls=int(ipl.get(pid,0)),style=str(styles.loc[pid].idxmax()) if pid in styles.index.get_level_values(0) else 'Unclassified',phase={k:int(phase.get((pid,k),0)) for k in ['powerplay','middle','death']},ci=[rd(x) for x in np.quantile(boot[j],[.025,.975])] if ranked else None,top10=rd(np.mean(ranks[j]<=10)) if ranked else None,strict=gain['strict'].get(pid),loose=gain['loose'].get(pid),prior_rank=list(train.index[train.eligible]).index(pid)+1 if pid in train.index[train.eligible] else None,holdout_score=rd(test.loc[pid,'score']) if pid in overlap else None))
    return rows,checks
def main():
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    b,a=load(args.source);d=prepare(ledger(b),a);out={'config':CFG,'audit':a,'players':[],'validation':{}}
    for role in ['bat','bowl']:
        rows,v=analyze(d,role);out['players']+=rows;out['validation'][role]=v
    content=json.dumps(out,sort_keys=True,allow_nan=False);out['freeze']=hashlib.sha256(content.encode()).hexdigest()[:12]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,allow_nan=False,separators=(',',':')));print(out['freeze'],a,out['validation'])
if __name__=='__main__':main()
