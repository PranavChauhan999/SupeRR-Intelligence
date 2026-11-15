"""Run with SUPERR_DATA=/path/to/Data\ Pack python -m unittest test_source."""
import os,unittest
from pathlib import Path
import pandas as pd
from pipeline import load, ledger, prepare, pressure
@unittest.skipUnless(os.environ.get('SUPERR_DATA'),'Set SUPERR_DATA to the original six-file archive directory')
class DeliveryAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw,cls.audit=load(Path(os.environ['SUPERR_DATA'])); cls.ledger=ledger(raw);cls.scored=prepare(cls.ledger,cls.audit)
    def test_dates_and_sources(self):
        s=self.scored
        self.assertEqual(set(s.year),{2023,2024,2025,2026})
        self.assertEqual(set(s.league),{'IPL','T20I'})
        self.assertFalse(s.match_id.isin(self.audit['integrity_excluded_ids']).any())
        self.assertEqual(len(self.audit['sources']),6)
    def test_actual_scorekeeping(self):
        b=self.ledger; self.assertTrue((b.team_runs>=b.charge).all())
        self.assertTrue((b.loc[b.extras_type=='other','legal']==0).all())
        self.assertFalse((b.bw.astype(bool)&b.dismissal_type.eq('RunOut')).any())
        self.assertTrue((b.loc[~b.is_wicket,'sw']+b.loc[~b.is_wicket,'nw']).eq(0).all())
    def test_counters_and_targets(self):
        for (_,inn),g in self.scored.groupby(['match_id','innings']):
            self.assertEqual((g.pre.iloc[0],g.down.iloc[0],g.score.iloc[0]),(0,0,0))
            self.assertEqual(g.pre.iloc[-1]+g.legal.iloc[-1],g.legal.sum())
            self.assertEqual(g.score.iloc[-1]+g.team_runs.iloc[-1],g.team_runs.sum())
            self.assertEqual(g.down.iloc[-1]+int(g.is_wicket.iloc[-1]),g.is_wicket.sum())
            if inn==1:self.assertEqual(g.target.iloc[0],g.team_runs.sum()+1)
    def test_later_data_cannot_change_earlier_fit(self):
        earlier=self.ledger[self.ledger.match_date<'2026-01-01'];a={}
        previous=prepare(earlier,a)
        full=self.scored[self.scored.year<2026]
        columns=['pre','score','down','bat_outcome_v','bowl_outcome_v','other_outcome_v']
        pd.testing.assert_frame_equal(previous[columns],full[columns])
        self.assertTrue((pressure(previous)==pressure(full)).all())
    def test_baseline_and_pressure_invariant_to_final_result_on_day(self):
        d=self.scored.copy();flags=pressure(d);d['result']='changed';d['win_team_id']=-1
        self.assertTrue((flags==pressure(d)).all())
