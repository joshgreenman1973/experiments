"""Regression checks for source interpretation, not just serialized output shape."""
import json, pathlib, sys, unittest
from unittest.mock import patch
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import stats, transform, ratios
import tempfile, contextlib, io

class StatisticsTests(unittest.TestCase):
    def test_streak_breaks_at_missing_year(self):
        s = stats.series_stats([10, 9, None, 8, 7], [2022,2023,2024,2025,2026], -1, False)
        self.assertNotIn('st', s)
    def test_largest_step_is_one_year_only(self):
        s = stats.series_stats([1, None, 100, 110], [2023,2024,2025,2026], 1, False)
        self.assertAlmostEqual(s['br'], .1)
    def test_cagr_excludes_zero_crossing(self):
        self.assertNotIn('cagr', stats.series_stats([10,-5,20], [2024,2025,2026], 1, False))
    def test_clock_and_decimal_units(self):
        self.assertEqual(transform.timespan(9.42), (9.7, True))
        self.assertFalse(transform.timespan_mode({'agency':'DOB','indicator':'Wait (minutes)'}))
        self.assertTrue(transform.timespan_mode({'agency':'FDNY','indicator':'Average response time'}))

class ResourcesTests(unittest.TestCase):
    def test_final_prior_year_replaces_provisional_not_current_plan(self):
        records = {
            'resources': [{'agency':'DOC','reporting_fiscal_year':'2025','resource_indicators':'Expenditures ($000,000)','current_fy_projected_actual':'1342.6'}],
            'resources_pmmr': [{'agency':'DOC','reporting_fiscal_year':'2026','resource_indicators':'Expenditures ($000,000)','previous_fy_actual':'1356.2','current_fy_plan':'9999'}],
        }
        with patch.object(transform, 'rows', side_effect=lambda name:records[name]):
            res, _ = transform.resources()
        self.assertEqual(res['DOC']['2025']['exp'], 1356.2)
        self.assertNotIn('2026', res['DOC'])
        self.assertEqual(res['DOC']['2025']['_sources']['exp']['dataset'], 'nvzu-6t9y')
    def test_partial_staff_is_not_total(self):
        rec={'agency':'DOC','reporting_fiscal_year':'2025','resource_indicators':'Personnel (uniformed)','current_fy_projected_actual':'100'}
        with patch.object(transform, 'rows', side_effect=lambda name:[rec] if name=='resources' else []):
            res, _ = transform.resources()
        self.assertNotIn('pers',res['DOC']['2025'])

class PublishedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/indicators.json').read_text())
        cls.byid={r['id']:r for r in cls.data['ind']}
    def test_pre_k_direction_and_target(self):
        r=self.byid['15763']
        self.assertEqual(r['dirs']['2026'], -1)
        self.assertLessEqual(r['v'][-1],r['tgt']['t26'])
    def test_dob_revisions_and_values(self):
        r=self.byid['5507']
        self.assertEqual(r['v'][-2:], [73641,78294])
        self.assertEqual(r['pdf']['original']['2025'],75932)
        self.assertEqual(r['pdf']['p'],371)
    def test_library_definition_break(self):
        for id in ('2285','3056','3072','3253'):
            self.assertEqual(self.byid[id]['breaks'],[2026])
            self.assertLessEqual((self.byid[id]['st'] or {}).get('n',0),1)
    def test_directional_target_is_not_missing(self):
        self.assertEqual(self.byid['3947']['targetDirections']['t26'],'down')
    def test_final_doc_resources(self):
        self.assertEqual(self.data['res']['DOC']['2025']['exp'],1356.2)
    def test_flagged_year_does_not_distort_statistics(self):
        r=self.byid['9102']
        self.assertIn('2020',r['sus'])
        self.assertEqual(r['st']['n'],sum(v is not None for v in r['v'])-1)
    def test_all_pdf_values_and_directions_survive_merge(self):
        pdf=json.loads((ROOT/'data/fy2026.json').read_text())
        count=0
        for id,p in pdf['ind'].items():
            if id not in self.byid:continue
            r=self.byid[id]
            if r['pdf']['valueSource']=='pdf' and 'v' in p:
                self.assertEqual(r['v'][-1],p['v'],id)
            self.assertEqual(r['dir'],p['direction'],id)
            count+=1
        self.assertGreater(count,1900)
    def test_ratio_build_rejects_definition_break_or_missing_history(self):
        for failure in ('break', 'missing', 'reconciliation'):
            data=json.loads((ROOT/'data/indicators.json').read_text())
            record=next(r for r in data['ind'] if r['id']=='10950')
            if failure=='break':record['breaks']=[2024]
            elif failure=='missing':record['v'][data['years'].index(2023)]=None
            else:record['v'][data['years'].index(2023)]+=1
            with tempfile.TemporaryDirectory() as directory:
                pathlib.Path(directory,'indicators.json').write_text(json.dumps(data))
                with patch.object(ratios,'OUT',directory), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):ratios.main()
                self.assertFalse(pathlib.Path(directory,'ratios.json').exists())
    def test_ratio_arithmetic_and_resource_labels(self):
        ratios=json.loads((ROOT/'data/ratios.json').read_text())['ratios']
        for r in ratios:
            scale=100 if r['kind']=='share' else 1
            for p in r['pts']:
                self.assertAlmostEqual(p['v'],p['n']/p['d']*scale,places=3,msg=r['id'])
        byid={r['id']:r for r in ratios}
        self.assertIn('Overtime',byid['doc-ot']['numLabel'])
        self.assertAlmostEqual(byid['doc-ot']['pts'][-1]['v'],341.1/1356.2*100,places=3)
        self.assertEqual(len(ratios),8)
        for r in ratios:
            self.assertEqual([p['y'] for p in r['pts']],list(range(r['reviewedYears'][0],r['reviewedYears'][1]+1)))
            self.assertGreaterEqual(len(r['pts']),5)
            self.assertTrue(all(0 <= p['v'] <= 100 and 0 <= p['n'] <= p['d'] for p in r['pts']))
            self.assertTrue(r['historyNote'])
        self.assertAlmostEqual(byid['oath-default']['pts'][-1]['v'],453811/686960*100,places=3)
        self.assertTrue(set(byid).isdisjoint({'bpl-circ','nypl-circ','qpl-circ','ccrb-sub','nypd-arrests','dot-potholes','doc-cost','dsny-cost','dsny-tons'}))

if __name__=='__main__':unittest.main()
