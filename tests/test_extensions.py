import math
import unittest
from rf_repair.extensions import resonance_hints, deterministic_candidates, make_bpf_extension_cases, make_matching_cases, extension_payload, validate_extension
from rf_repair.transfer import apply_patch


class ExtensionTests(unittest.TestCase):
    def test_public_resonance_math_and_connectivity(self):
        source='* test\nVPORT1 a 0 DC 0\nL8 a b 10n\nC7 b 0 100p\n.end\n'
        hints=resonance_hints(source,1e8)
        self.assertEqual(len(hints['pairs']),1)
        pair=hints['pairs'][0]
        self.assertEqual(pair['connection'],'series')
        self.assertAlmostEqual(pair['current_resonance_hz'],1/(2*math.pi*math.sqrt(1e-8*1e-10)))
        candidates={p['component']:float(p['proposed_value']) for p in pair['candidate_edits']}
        self.assertAlmostEqual(candidates['L8']*(2*math.pi*1e8)**2*1e-10,1)
        branched=source.replace('.end','R9 b 0 50\n.end')
        self.assertEqual(resonance_hints(branched,1e8)['pairs'],[])
        with self.assertRaises(ValueError):resonance_hints(source,float('nan'))

    def test_all_new_cases_exactly_one_edit(self):
        for generator in [make_bpf_extension_cases,make_matching_cases]:
            cases=generator();self.assertEqual(len(cases),8)
            for c in cases:
                self.assertEqual(apply_patch(c['faulty_netlist'],c['component'],c['healthy_value']),c['healthy_netlist'])
        self.assertEqual(len({c['spec']['target_center_frequency_hz'] for c in make_bpf_extension_cases()}),4)

    def test_only_calculation_payload_differs(self):
        c=make_bpf_extension_cases()[0];c['initial_metrics']={}
        a=extension_payload(c,[],'feedback');b=extension_payload(c,[],'calculator_feedback')
        hints=b.pop('resonance_calculations');self.assertEqual(a,b)
        self.assertEqual(len(hints['pairs']),3)
        self.assertNotIn('healthy_value',str(a))
        self.assertLessEqual(len(deterministic_candidates(c['faulty_netlist'],c['spec']['target_center_frequency_hz'])),3)

    def test_matching_rejects_bad_evidence_and_uses_own_spec(self):
        spec=make_matching_cases()[0]['spec']
        metrics={'simulation_converged':True,'samples':{k:{'measured_frequency_hz':f,'s11_db':-40.,'s21_db':0.} for k,f in spec['measurement_frequencies_hz'].items()}}
        self.assertEqual(validate_extension(metrics,spec,'matching')['verdict'],'PASS')
        metrics['samples']['center']['s11_db']=float('nan')
        self.assertEqual(validate_extension(metrics,spec,'matching')['verdict'],'FAIL')
        metrics['samples']['center']['measured_frequency_hz']+=10
        self.assertEqual(validate_extension(metrics,spec,'matching')['reason'],'MEASUREMENT_FREQUENCY_MISMATCH')

if __name__=='__main__':unittest.main()
