from pathlib import Path
import hashlib,json,unittest
import pandas as pd
import numpy as np
from pipeline import ledger,pressure,rating
class Accounting(unittest.TestCase):
    def setUp(self):
        self.raw=pd.DataFrame(dict(match_id=[1]*6,innings=[1]*6,innings_ball_num=range(1,7),extras_type=['wide','other','Overstep','legbyes',None,'Penalty'],runs=[0,4,0,0,1,0],extras1_runs=[2,1,1,1,0,5],extras_2_runs=[0,0,3,0,0,0],is_wicket=[False,False,False,False,True,False],dismissal_type=['','','','','RunOut',''],dismissed_player_id=[np.nan]*4+[2,np.nan],striker_id=[1]*6,non_striker_id=[2]*6))
    def test_score_conservation_and_debits(self):
        d=ledger(self.raw);self.assertEqual(d.team_runs.sum(),18);self.assertEqual(d.charge.sum(),9);self.assertEqual(d.faced.sum(),5);self.assertEqual(d.legal.sum(),3)
    def test_pre_ball_and_non_striker(self):
        d=ledger(self.raw);self.assertEqual(d.score.iloc[1],2);self.assertEqual(d.pre.iloc[3],0);self.assertEqual(d.down.iloc[4],0);self.assertEqual(d.nw.sum(),1);self.assertEqual(d.bw.sum(),0)
    def test_future_invariance(self):
        a=ledger(self.raw); self.raw.loc[4,'runs']=6;b=ledger(self.raw);pd.testing.assert_frame_equal(a.loc[:4,['score','down','pre']],b.loc[:4,['score','down','pre']])
    def test_pressure_boundary(self):
        d=pd.DataFrame({'innings':[1,1,2,2,2],'pre':[95,96,60,60,108],'target':[0,0,150,150,150],'score':[0,0,50,49,110],'down':[0]*5});self.assertEqual(pressure(d).tolist(),[False,True,True,True,False])
    def test_shrinkage(self):
        self.assertLess(rating(100,100,200,0,10,8),rating(400,400,200,0,10,8))
class Freeze(unittest.TestCase):
    def setUp(self): self.d=json.loads(Path('data/snapshot.json').read_text())
    def test_signature(self):
        signature=self.d.pop('freeze'); self.assertEqual(hashlib.sha256(json.dumps(self.d,sort_keys=True,allow_nan=False).encode()).hexdigest()[:12],signature)
    def test_complete_cohorts(self):
        for role in ['bat','bowl']:
            rows=[p for p in self.d['players'] if p['role']==role];self.assertEqual(len({p['id'] for p in rows}),len(rows))
            ranks=sorted((p for p in rows if p['rank']),key=lambda p:p['rank']);self.assertEqual([p['rank'] for p in ranks],list(range(1,len(ranks)+1)))
            for p in rows:
                self.assertEqual(bool(p['rank']),p['balls']>=100 and p['normal_balls']>=180 and p['matches']>=10)
                self.assertEqual(sum(p['phase'].values()),p['balls']);self.assertLessEqual(p['ipl_balls'],p['balls'])
            self.assertEqual([p['score'] for p in ranks],sorted((p['score'] for p in ranks),reverse=True))
if __name__=='__main__':unittest.main()
