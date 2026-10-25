import math
import unittest
from copy import deepcopy
from rf_repair import lossy


class LossyTests(unittest.TestCase):
    def test_parasitic_compensation_matches_reactance(self):
        w=2*math.pi*100e6
        c=lossy.compensated_value('C',100e-12,100e6)
        self.assertAlmostEqual(w*lossy.MODEL['capacitor_esl_h']-1/(w*c),-1/(w*100e-12))
        l=lossy.compensated_value('L',100e-9,100e6); z=complex(lossy.MODEL['inductor_rs_ohm'],w*l)
        effective=z/(1+z*complex(0,w*lossy.MODEL['inductor_cp_f']))
        self.assertAlmostEqual(effective.imag,w*100e-9)
        self.assertGreater(effective.real,0)

    def test_public_model_has_no_ground_truth_and_fixed_loss(self):
        a=lossy.make_design(103e6,.18,1,'dev',.02); b=lossy.make_design(113e6,.18,1,'dev',.02)
        self.assertEqual(a['public_model']['model'],b['public_model']['model'])
        case={'public_model':a['public_model'],'spec':a['spec'],'faulty_netlist':lossy.render(a['public_model'],a['healthy_values']),
              'initial_metrics':{},'numerical_search':{},'component':'SECRET','healthy_value':'SECRET','design_evaluator_only':a}
        payload=lossy.payload(case,[])
        self.assertNotIn('SECRET',str(payload))
        self.assertFalse(any(k in str(a['public_model']) for k in ['nominal','healthy','deviation']))

    def test_patch_and_schema_protect_parasitics_and_ports(self):
        d=lossy.make_design(103e6,.18,1,'dev'); p=d['public_model']; source=lossy.render(p,d['healthy_values'])
        names={r['component'] for r in p['main_components']}
        enum=set(lossy.schema(p)['properties']['repair']['properties']['component']['enum']);self.assertEqual(enum,names)
        for name in ['CP_'+next(n for n in names if n[0]=='L'),'RS_'+next(iter(names)),'VPORT1']:
            with self.assertRaises((ValueError,KeyError)):lossy.patch(source,p,name,'1e-9')
        name=next(iter(names)); changed=lossy.patch(source,p,name,'1e-9')
        self.assertEqual(sum(a!=b for a,b in zip(source.splitlines(),changed.splitlines())),1)

    def test_objective_penalizes_spec_failure(self):
        d=lossy.make_design(103e6,.18,202609070,'dev'); m=lossy.predict(d['public_model'],d['healthy_values'],d['spec'])
        failed=deepcopy(m); failed['samples']['center']['s21_db']=-10
        self.assertGreater(lossy.objective(failed,d['spec'],1),lossy.objective(m,d['spec'],1)+50)

if __name__=='__main__':unittest.main()
