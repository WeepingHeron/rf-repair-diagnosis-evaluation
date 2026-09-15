import unittest
from rf_repair.transfer import make_cases, components, apply_patch, agent_payload, response_schema


class TransferTests(unittest.TestCase):
    def test_all_cases_have_one_exact_oracle_edit(self):
        cases=make_cases()
        self.assertEqual(len(cases),12)
        self.assertEqual(len({c['design_id'] for c in cases}),4)
        for c in cases:
            self.assertEqual(apply_patch(c['faulty_netlist'],c['component'],c['healthy_value']),c['healthy_netlist'])
            self.assertEqual(set(components(c['faulty_netlist'])),set(components(c['healthy_netlist'])))
            self.assertNotIn('RFAULT',c['faulty_netlist'])
            self.assertNotIn('Butterworth',c['faulty_netlist'])

    def test_no_feedback_input_is_identical_across_attempts(self):
        c=make_cases()[0];history=[{'outcome':'FAIL','secret_test':'not present'}]
        a=agent_payload(c['faulty_netlist'],c['spec'],{},history,'no_feedback')
        b=agent_payload(c['faulty_netlist'],c['spec'],{},[],'feedback')
        self.assertEqual(a,b)
        self.assertNotIn('previous_attempts',a)
        self.assertIn('previous_attempts',agent_payload(c['faulty_netlist'],c['spec'],{},history,'feedback'))
        self.assertNotIn('healthy_value',str(a))

    def test_dynamic_schema_never_names_missing_components(self):
        c=make_cases()[0];schema=response_schema(c['faulty_netlist'])
        self.assertEqual(set(schema['properties']['repair']['properties']['component']['enum']),set(components(c['faulty_netlist'])))
        with self.assertRaises(ValueError):apply_patch(c['faulty_netlist'],'C1','1p')
        value=components(c['faulty_netlist'])[c['component']]
        with self.assertRaises(ValueError):apply_patch(c['faulty_netlist'],c['component'],value)
