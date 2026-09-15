import unittest
from copy import deepcopy
from rf_repair import robustness, reference, lossy

class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.cases = reference.cases()[:6]
        self.items = robustness.cohort(self.cases)
        self.item = next(i for i in self.items if i['kind']=='fault')
        self.base = robustness.scenarios()[0]

    def test_cohort_counts_and_control_label(self):
        self.assertEqual(len(self.items),9)
        self.assertEqual(sum(i['kind']=='control' for i in self.items),3)
        control=next(i for i in self.items if i['kind']=='control')
        scored=robustness.score({'component':'unknown','fault_type':'unknown_direction'},control)
        self.assertTrue(scored['abstained']);self.assertFalse(scored['correct'])
        self.assertTrue(robustness.score({'component':'L1','fault_type':'value_too_high'},control)['false_alarm'])

    def test_model_mismatch_does_not_leak_into_estimator(self):
        changed=self.base|{'rs_fraction':.5,'parasitic_fraction':-.25}
        evidence=robustness.measurement_inputs(self.item,changed)
        self.assertEqual(evidence['estimator_input']['public'],self.item['public_model'])
        self.assertNotEqual(evidence['generation']['physical_model']['model'],self.item['public_model']['model'])
        self.assertEqual(set(evidence['estimator_input']),{'source','public','reference'})

    def test_frequency_error_is_hidden_and_noise_is_paired(self):
        a=robustness.measurement_inputs(self.item,self.base|{'frequency_fraction':.001,'noise_sigma_db':.01})
        b=robustness.measurement_inputs(self.item,self.base|{'noise_sigma_db':.02})
        self.assertEqual(a['generation']['standard_normal'],b['generation']['standard_normal'])
        for x,y in zip(a['generation']['actual_frequencies_hz'],a['estimator_input']['reference']['samples']):
            self.assertAlmostEqual(x/y['frequency_hz'],1.001)
        self.assertEqual(a,robustness.measurement_inputs(self.item,self.base|{'frequency_fraction':.001,'noise_sigma_db':.01}))

    def test_clean_positive_and_negative_control(self):
        for item in [self.item,next(i for i in self.items if i['kind']=='control')]:
            fit=reference.fit_reference(**robustness.measurement_inputs(item,self.base)['estimator_input'])
            scored=robustness.score(reference.deterministic_diagnosis(fit),item)
            self.assertTrue(scored['correct'] if item['kind']=='fault' else scored['abstained'])

    def test_drift_updates_current_values_only_and_invalid_rejected(self):
        a=robustness.measurement_inputs(self.item,self.base)
        b=robustness.measurement_inputs(self.item,self.base|{'lc_drift_fraction':.01})
        self.assertEqual(a['estimator_input']['reference'],b['estimator_input']['reference'])
        before=lossy.observed_values(a['estimator_input']['source'],self.item['public_model'])
        after=lossy.observed_values(b['estimator_input']['source'],self.item['public_model'])
        for k in before:self.assertAlmostEqual(float(after[k])/float(before[k]),1.01)
        for change in [{'noise_sigma_db':-1},{'offset_db':float('nan')},{'rs_fraction':-1}]:
            with self.assertRaises(ValueError):robustness.measurement_inputs(self.item,self.base|change)

if __name__=='__main__':unittest.main()
