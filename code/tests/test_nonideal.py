import math
import unittest
from rf_repair.nonideal import make_conditions, element_parameters, render, protected_patch, analytic_magnitudes


class NonidealTests(unittest.TestCase):
    def test_full_factorial_paired_draws_and_new_designs(self):
        cs = make_conditions()
        self.assertEqual(len(cs), 320)
        self.assertEqual(len({c['condition_id'] for c in cs}), 320)
        self.assertEqual({c['design']['f0'] for c in cs}, {103e6,139e6,167e6,211e6})
        selected = [c for c in cs if c['design']['design_id']=='nonideal_d1' and c['draw']==1 and c['tolerance']==.03]
        self.assertTrue(all(c['deviations']==selected[0]['deviations'] for c in selected))

    def test_q_loss_and_protected_parasitics(self):
        c = next(c for c in make_conditions() if c['q']==100 and c['parasitics'] and c['tolerance']==0)
        parts = element_parameters(c); w = 2*math.pi*c['design']['f0']
        for p in parts:
            reactance = w*p['nominal'] if p['name'][0]=='L' else 1/(w*p['nominal'])
            self.assertAlmostEqual(reactance/p['resistance'], 100, places=7)
        source = render(c); name = parts[0]['name']; changed = protected_patch(source, name, '1e-6', [p['name'] for p in parts])
        self.assertEqual(sum(a!=b for a,b in zip(source.splitlines(),changed.splitlines())),1)
        for protected in ['CP_'+name, 'RS_'+name, 'VPORT1']:
            with self.assertRaises(ValueError): protected_patch(source, protected, '1', [p['name'] for p in parts])

    def test_ideal_analytic_center_and_loss_passivity(self):
        for c in make_conditions():
            if c['tolerance'] or c['parasitics']: continue
            s11,s21,s22 = analytic_magnitudes(c, {}, c['design']['f0'])
            self.assertLessEqual(s11*s11+s21*s21, 1+1e-12)
            if c['q'] is None:
                self.assertLess(s11, 1e-10); self.assertAlmostEqual(s21,1,places=10)
            else: self.assertLess(s21,1)

    def test_oracle_keeps_tolerances_and_loss_fixed(self):
        c = next(c for c in make_conditions() if c['tolerance']==.05 and c['q']==50 and c['parasitics'])
        parts=element_parameters(c); p=parts[0]; n=p['name']; healthy=render(c)
        faulty=render(c,{n:f'{float(p["value"])*.55:.12g}'})
        self.assertEqual(protected_patch(faulty,n,p['value'],[p['name'] for p in parts]),healthy)
        with self.assertRaises(ValueError): render(c, {'RS_'+n:'1'})

if __name__=='__main__': unittest.main()
