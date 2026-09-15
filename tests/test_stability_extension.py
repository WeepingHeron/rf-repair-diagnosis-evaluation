import unittest
from copy import deepcopy
from rf_repair import stability_extension as ext,abstention,diagnosis_dev as dev

class StabilityExtensionTests(unittest.TestCase):
    def test_prefix_matches_active_policy_and_input_is_preserved(self):
        e=dev.inputs(dev.cohort()[1],dev.profiles()[0])['estimator_input'];before=deepcopy(e)
        out=list(ext.perturbations(e,16))
        self.assertEqual(out[:4],abstention.perturbations(e));self.assertEqual(e,before)
        self.assertEqual(out,list(ext.perturbations(e,16)))
        self.assertEqual(len({tuple(p['offsets_db']) for p in out}),16)
        for p in out:
            self.assertEqual(p['input']['source'],e['source']);self.assertEqual(p['input']['public'],e['public'])
            self.assertEqual(set(p['offsets_db']),{-.01,.01})
    def test_both_location_and_direction_must_match(self):
        def fit(n,d):return {'hypotheses':[{'component':n,'current_fault_direction':d}]}
        original=fit('L1','value_too_low')
        self.assertTrue(ext.compare(original,original)['matches'])
        self.assertFalse(ext.compare(fit('L1','value_too_high'),original)['matches'])
        self.assertFalse(ext.compare(fit('C1','value_too_low'),original)['matches'])
    def test_invalid_draw_contract(self):
        for n in [0,3,65,4.0,True]:
            with self.assertRaises(ValueError):list(ext.perturbations({},n))

if __name__=='__main__':unittest.main()
