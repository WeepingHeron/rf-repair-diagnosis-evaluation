import unittest
from copy import deepcopy
from rf_repair import abstention as a, diagnosis_dev as dev

class AbstentionTests(unittest.TestCase):
    def policy(self):return dict(status='CALIBRATED_SYNTHETIC',parameters=dict(fit_max_db=.02,gap_min_db=.03,ratio_min=5.,null_score_min=15.,stability_required=4,score_floor_db=.01))
    def test_invalid_policy_never_diagnoses(self):
        for change in [{'null_score_min':float('nan')},{'fit_max_db':.1},{'stability_required':0}]:
            p=self.policy();p['parameters'].update(change)
            self.assertEqual(a.diagnose({},p)['diagnosis']['component'],'unknown')
            self.assertIn('INVALID_INPUT_OR_POLICY',a.diagnose({},p)['reasons'])
    def test_observed_wrong_candidate_example_is_blocked(self):
        b=dict(fit={'hypotheses':[dict(component='C266',current_fault_direction='value_too_low')]},features=dict(best_rmse_db=.0588,gap_db=.0553,separation_ratio=1.94,null_score=22.),stability=[{}]*4,stability_matches=4)
        r=a.decide(b,self.policy());self.assertTrue(r['abstained']);self.assertIn('MODEL_MISMATCH',r['reasons'])
    def test_null_and_stability_are_required(self):
        b=dict(fit={'hypotheses':[dict(component='L1',current_fault_direction='value_too_low')]},features=dict(best_rmse_db=.003,gap_db=.2,separation_ratio=20.,null_score=30.),stability=[{}]*4,stability_matches=4)
        self.assertFalse(a.decide(b,self.policy())['abstained'])
        c=deepcopy(b);c['features']['null_score']=1.;self.assertIn('CHANGE_NOT_DISTINGUISHED_FROM_NULL',a.decide(c,self.policy())['reasons'])
        c=deepcopy(b);c['stability_matches']=3;self.assertIn('STABILITY_NOT_CONFIRMED',a.decide(c,self.policy())['reasons'])
    def test_input_only_perturbations_preserve_measurement_contract(self):
        item=dev.cohort()[1];e=dev.inputs(item,dev.profiles()[0])['estimator_input'];before=deepcopy(e)
        ps=a.perturbations(e);self.assertEqual(ps,a.perturbations(e));self.assertEqual(e,before);self.assertEqual(len(ps),4)
        for p in ps:
            self.assertEqual(p['input']['source'],e['source']);self.assertEqual(p['input']['public'],e['public'])
            self.assertEqual(set(p['offsets_db']),{-.01,.01})
    def test_calibration_requires_null_controls(self):
        with self.assertRaises(ValueError):a.select([], 'protocol', {})

if __name__=='__main__':unittest.main()
