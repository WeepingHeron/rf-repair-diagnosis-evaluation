import unittest
from copy import deepcopy
from rf_repair import reference,lossy

class ReferenceTests(unittest.TestCase):
    def fixture(self):
        c=reference.cases()[0];rows=lossy.curve(c['public_model'],c['design_evaluator_only']['healthy_values'],[r*c['public_model']['frequency_hz'] for r in reference.RATIOS])
        ref={'quantization_db':.01,'samples':[dict(frequency_hz=r[0],**{k:round(v,2) for k,v in zip(['s11_db','s21_db','s22_db'],r[1:])}) for r in rows]}
        return c,ref

    def test_inputs_differ_only_by_added_evidence(self):
        c,ref=self.fixture();c.update(initial_metrics={},current_spectrum={},reference_spectrum=ref,reference_fit={})
        a,b,d=[reference.payload(c,k) for k in reference.CONDITIONS]
        self.assertEqual(b.pop('prefault_reference_spectrum'),ref);self.assertEqual(a,b)
        d.pop('reference_inverse_fit');d.pop('prefault_reference_spectrum');self.assertEqual(a,d)
        self.assertFalse(any(k in a for k in ['healthy_value','component','healthy_netlist','design_evaluator_only']))

    def test_reference_contract_rejects_wrong_frequency_and_nan(self):
        c,ref=self.fixture();bad=deepcopy(ref);bad['samples'][0]['frequency_hz']+=10
        with self.assertRaises(ValueError):reference.fit_reference(c['faulty_netlist'],c['public_model'],bad)
        bad=deepcopy(ref);bad['samples'][0]['s11_db']=float('nan')
        with self.assertRaises(ValueError):reference.fit_reference(c['faulty_netlist'],c['public_model'],bad)

    def test_ambiguous_fit_abstains(self):
        self.assertEqual(reference.deterministic_diagnosis({'resolved_within_search':False}),{'component':'unknown','fault_type':'unknown_direction'})
        c,_=self.fixture();c['reference_fit']={'hypotheses':[{'component':c['component']}]}
        r=reference.score({'component':'unknown','fault_type':'unknown_direction'},c)
        self.assertTrue(r['abstained']);self.assertFalse(r['diagnosed']);self.assertFalse(r['false_location'])

    def test_oracle_is_single_value_and_new_designs(self):
        cs=reference.cases();self.assertEqual(len(cs),8)
        for c in cs:self.assertEqual(lossy.patch(c['faulty_netlist'],c['public_model'],c['component'],c['healthy_value']),c['healthy_netlist'])
        self.assertEqual({c['spec']['target_center_frequency_hz'] for c in cs},{115e6,153e6,203e6,257e6})

if __name__=='__main__':unittest.main()
