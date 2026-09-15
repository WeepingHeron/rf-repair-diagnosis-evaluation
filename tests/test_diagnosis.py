import unittest
from copy import deepcopy
from rf_repair.diagnosis import cases,payload,schema,score,CONDITIONS
from rf_repair.lossy import patch

class DiagnosisTests(unittest.TestCase):
    def test_visibility_is_only_payload_difference(self):
        c=cases()[0];c['initial_metrics']={'synthetic_test':1};c['numerical_search']={'candidates':[{'component':c['component']}]}
        hidden=payload(c,CONDITIONS[0]);shown=payload(c,CONDITIONS[1])
        search=shown.pop('numerical_search');self.assertEqual(hidden,shown)
        self.assertEqual(search,c['numerical_search'])
        self.assertNotIn('healthy_value',str(hidden));self.assertNotIn('design_evaluator_only',str(hidden))
        hidden['public_main_component_model']['ports'][0]='MUTATED'
        self.assertNotEqual(c['public_model']['ports'][0],'MUTATED')

    def test_unknown_is_not_a_correct_diagnosis_or_a_false_location(self):
        c=cases()[0];c['numerical_search']={'candidates':[{'component':c['component']}]}
        s=score({'component':'unknown','fault_type':'unknown_direction'},c)
        self.assertTrue(s['abstained']);self.assertFalse(s['diagnosed']);self.assertFalse(s['false_location'])
        with self.assertRaises(ValueError):score({'component':'unknown','fault_type':'value_too_low'},c)

    def test_compensating_candidate_is_not_the_fault(self):
        c=cases()[0];other=next(p['component'] for p in c['public_model']['main_components'] if p['component']!=c['component'])
        c['numerical_search']={'candidates':[{'component':other}]}
        s=score({'component':other,'fault_type':c['fault_type']},c)
        self.assertTrue(s['matches_top_repair_component']);self.assertTrue(s['false_location']);self.assertFalse(s['diagnosed'])

    def test_new_case_oracles_and_protected_schema(self):
        cs=cases();self.assertEqual(len(cs),8);self.assertEqual(len({c['design_id'] for c in cs}),4)
        for c in cs:
            self.assertEqual(patch(c['faulty_netlist'],c['public_model'],c['component'],c['healthy_value']),c['healthy_netlist'])
            allowed=schema(c['public_model'])['properties']['component']['enum']
            self.assertEqual(len(allowed),7);self.assertIn('unknown',allowed)
            self.assertFalse(any(n.startswith(('RS_','CP_','LS_','VPORT')) for n in allowed))

if __name__=='__main__':unittest.main()
