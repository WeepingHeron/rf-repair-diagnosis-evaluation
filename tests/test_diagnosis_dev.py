import unittest
from rf_repair import diagnosis_dev as dev,lossy

class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.items=dev.cohort();self.item=next(i for i in self.items if i['kind']=='fault')

    def test_new_cohort_and_exact_injected_changes(self):
        self.assertEqual(len(self.items),148);self.assertEqual(sum(i['kind']=='control' for i in self.items),4)
        self.assertEqual({i['public_model']['frequency_hz'] for i in self.items},{127e6,173e6,217e6,269e6})
        for i in self.items:
            p=i['public_model'];old=lossy.observed_values(i['historical_netlist'],p);new=lossy.observed_values(i['current_netlist'],p)
            changed=[k for k in old if old[k]!=new[k]]
            self.assertEqual(changed,[] if i['kind']=='control' else [i['expected_component']])

    def test_heterogeneous_model_is_hidden_and_noise_paired(self):
        a=dev.inputs(self.item,dev.profiles()[0]);b=dev.inputs(self.item,next(p for p in dev.profiles() if p['family']=='combined'))
        self.assertEqual(a['estimator_input']['public'],b['estimator_input']['public'])
        self.assertEqual(set(b['estimator_input']),{'source','public','reference'})
        self.assertNotEqual(a['generation']['historical_source'],b['generation']['historical_source'])
        self.assertEqual(a['generation']['vectors'],b['generation']['vectors'])
        self.assertGreater(len(set(b['generation']['vectors']['drift']['values'])),1)

    def test_clean_curve_matches_frozen_public_model(self):
        for item in self.items[::37]:
            p=item['public_model'];f=[p['frequency_hz']*r for r in [.7,1.,1.4]]
            a=dev.heterogeneous_curve(item['historical_netlist'],p,f)
            b=lossy.curve(p,lossy.observed_values(item['historical_netlist'],p),f)
            for x,y in zip(a,b):
                for m,n in zip(x,y):self.assertAlmostEqual(m,n,places=8)

    def test_invalid_and_heterogeneous_drift_bounds(self):
        profile=next(p for p in dev.profiles() if p['family']=='drift_0.5pct')
        e=dev.inputs(self.item,profile);p=self.item['public_model']
        old=lossy.observed_values(self.item['current_netlist'],p);new=lossy.observed_values(e['estimator_input']['source'],p)
        ratios=[float(new[k])/float(old[k])-1 for k in old]
        self.assertTrue(all(abs(x)<=.005000001 for x in ratios));self.assertGreater(max(ratios)-min(ratios),.0001)
        with self.assertRaises(ValueError):dev.inputs(self.item,profile|{'model_amplitude':float('nan')})

if __name__=='__main__':unittest.main()
