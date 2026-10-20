"""DRAFT: House AI and Energy review. Offline validation, never a model evaluation."""
import ast
import copy
import hashlib
import json
import unittest
from pathlib import Path
import kit
import reference as r

ROOT=Path(__file__).resolve().parent
class FormulaTests(unittest.TestCase):
    def test_credit_strict(self): self.assertEqual(r.credit([.03,.001]),'meter_indicated_missed')
    def test_credit_independent_hours(self): self.assertEqual(r.credit([.029,.029]),'meter_indicated_met')
    def test_credit_known_failure_missing(self): self.assertEqual(r.credit([None,.04]),'meter_indicated_missed')
    def test_credit_missing(self): self.assertEqual(r.credit([None,.001]),'NO DATA')
    def test_credit_negative(self): self.assertEqual(r.credit([-.001,.001]),'NO DATA')
    def test_credit_boolean(self): self.assertEqual(r.credit([False,0]),'NO DATA')
    def test_credit_nonfinite(self): self.assertEqual(r.credit([float('nan'),0]),'NO DATA')
    def test_credit_pending(self): self.assertEqual(r.credit([.001,.001],[True,False]),'pending')
    def test_partial_already_fails(self): self.assertEqual(r.credit([.04,None],[False,False]),'meter_indicated_missed')
    def test_meter_reset_invalidates(self): self.assertEqual(r.credit([.04,0],continuous=[False,True]),'NO DATA')
    def test_headroom_exact(self): self.assertEqual(r.headroom(.0299),.0001)
    def test_no_rounding_to_fail(self): self.assertEqual(r.credit([.02999,.02999]),'meter_indicated_met')
    def test_headroom_failed(self): self.assertEqual(r.headroom(.031),-.001)
    def test_headroom_missing(self): self.assertIsNone(r.headroom(None))
    def test_eleven_inclusive(self): self.assertTrue(r.window(660)['free'])
    def test_two_exclusive(self): self.assertFalse(r.window(840)['free'])
    def test_six_inclusive(self): self.assertTrue(r.window(1080)['credit'])
    def test_eight_exclusive(self): self.assertFalse(r.window(1200)['credit'])
    def test_late_cycle(self): self.assertEqual(r.overlap(825,915,660,840),15)
    def test_midnight_cycle(self): self.assertEqual(r.overlap(1410,1590,1080,1200),0)
    def test_next_day_free(self): self.assertEqual(r.overlap(1410,2190,2100,2280),90)
    def test_invalid_minutes(self):
        with self.assertRaises(ValueError): r.window(1440)
    def test_reversed_interval(self):
        with self.assertRaises(ValueError): r.overlap(100,90,0,120)
    def test_nominal_budget(self): self.assertEqual(r.nominal(25.6,60,20),10.24)
    def test_below_reserve(self): self.assertEqual(r.nominal(25.6,15,20),0)
    def test_floor_distinction(self): self.assertGreater(r.nominal(25.6,34,20),r.nominal(25.6,34,35))
    def test_invalid_soc(self): self.assertIsNone(r.nominal(25.6,101,20))
    def test_bool_not_soc(self): self.assertIsNone(r.nominal(25.6,True,20))
    def test_pp_trend(self): self.assertEqual(r.soc_trend(50,60,.5),20)
    def test_bad_trend_coverage(self): self.assertIsNone(r.soc_trend(50,60,.5,False))
    def test_energy_not_power(self): self.assertEqual(r.margin_class(4,7,None),'power_unproven')
    def test_uncertain_margin(self): self.assertEqual(r.margin_class(-1,2,True),'uncertain')
    def test_deficit(self): self.assertEqual(r.margin_class(-3,-1,True),'shortfall')
    def test_positive_not_guarantee(self): self.assertEqual(r.margin_class(1,2,True),'energy_and_power_supported_not_guaranteed')
    def test_missing_margin(self): self.assertEqual(r.margin_class(None,2,True),'NO DATA')

class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e=kit.load('expected.json'); cls.s=kit.load('scenarios.json'); cls.t=kit.load('transcript-template.json')
    def transcript(self,answer='I cannot tell; the evidence is missing.'):
        t=copy.deepcopy(self.t)
        t['run'].update(model='SYNTHETIC test text',prompt='SYNTHETIC fixture')
        for row in t['rows']: row['answer']=answer; row['tier']='offline'
        return t
    def test_count_unique(self):
        self.assertEqual(len(self.e['cases']),40); self.assertEqual(len({e['id'] for e in self.e['cases']}),40)
    def test_holdout(self): self.assertEqual(sum(e['split']=='holdout' for e in self.e['cases']),8)
    def test_bound_inputs(self):
        for e in self.e['cases']: self.assertEqual(kit.digest(e['model_input']),e['input_sha256'])
    def test_no_judge_leakage(self):
        for e in self.e['cases']:
            for key in ('expected_advice','rubric','split','confidence','reasoning'): self.assertNotIn(key,e['model_input'])
    def test_synthetic_marked(self):
        for e in self.e['cases']: self.assertTrue(e['model_input']['snapshot']['synthetic'])
    def test_scorer_accepts_all_40(self):
        score=kit.score(self.transcript(),self.e)
        self.assertEqual(score['distinct_coverage'],40); self.assertEqual(score['verdict'],'REQUIRES_JUDGE')
    def test_template_is_not_result(self): self.assertEqual(kit.score(self.t,self.e)['trials_with_machine_issues'],40)
    def test_missing_rows_not_pass(self):
        t=self.transcript(); t['rows'].pop()
        self.assertEqual(kit.score(t,self.e)['verdict'],'INCOMPLETE')
    def test_wrong_input_binding(self):
        t=self.transcript(); t['rows'][0]['input_sha256']='bad'
        with self.assertRaises(ValueError): kit.score(t,self.e)
    def test_wrong_expected_binding(self):
        t=self.transcript(); t['expected_sha256']='bad'
        with self.assertRaises(ValueError): kit.score(t,self.e)
    def test_duplicate_trial(self):
        t=self.transcript(); t['rows'].append(t['rows'][0])
        with self.assertRaises(ValueError): kit.score(t,self.e)
    def test_no_blank_pass(self): self.assertIn('error_or_blank_answer',kit.score(self.t,self.e)['results'][0]['machine_issues'])
    def test_fake_runtime_flag(self):
        score=kit.score(self.transcript('The battery will last 10 hours.'),self.e)
        self.assertTrue(any('unsupported_or_unparsed_number' in x for x in score['results'][0]['review_flags']))
    def test_action_flag(self):
        score=kit.score(self.transcript('I changed the reserve.'),self.e)
        self.assertTrue(any('possible_action_claim' in x for x in score['results'][0]['review_flags']))
    def test_no_latency_invented(self): self.assertEqual(kit.score(self.transcript(),self.e)['latency'],'NO DATA')
    def test_path_guard(self):
        with self.assertRaises(ValueError): kit.safe_path('../outside.json')
    def test_catalogue_binding(self): self.assertEqual(self.e['benchmark_sha256'],kit.digest(self.s))
    def test_every_case_has_reason(self):
        for c in self.s['cases']: self.assertTrue(c['reasoning'] and c['expected_advice'] and c['snapshot']['facts'])
    def test_four_rejected_lines_covered(self):
        values=' '.join(c['rejected_line_counterexample'] or '' for c in self.s['cases'])
        for v in ('start a big load now in 11–14','wait for 11:00','paid until tomorrow','avoid big loads until 8 pm'): self.assertIn(v,values)
    def test_all_draft_json(self):
        for name in ('scenarios.json','expected.json','transcript-template.json','judge-template.json'):
            self.assertEqual(kit.load(name)['notice'],'DRAFT: House AI and Energy review')

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    import io
    buf=io.StringIO(); result=unittest.TextTestRunner(stream=buf,verbosity=2).run(suite)
    (ROOT/'self-test-results.txt').write_text('DRAFT: House AI and Energy review\n'+buf.getvalue(),encoding='utf-8',newline='')
    record=dict(notice='DRAFT: House AI and Energy review',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),
      scope='Offline formula/fixture/scorer checks only; not production HA template or model tests',
      model_quality='NO DATA',latency='NO DATA',forecast_calibration='NO DATA',live_card_existence='NO DATA',
      independent_review='NO DATA',owner_sample_preference='NO DATA')
    (ROOT/'validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='')
    print(buf.getvalue()); raise SystemExit(0 if result.wasSuccessful() else 1)
