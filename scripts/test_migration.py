"""Command-recorder regressions for the offline Tri-Zero migration, not physical tests."""
import ast
import math
import os
from pathlib import Path
import shlex
import unittest
import jinja2
from verify_migration import ROOT,parse_config

CFG=parse_config(Path(os.environ.get('KALICO_SOURCE',ROOT.parent/'kalico')))

class Runtime:
    def __init__(self):
        self.p={}
        for section in CFG.sections():
            if section.startswith('gcode_macro '):
                self.p[section]={k[9:]:ast.literal_eval(v) for k,v in CFG.items(section) if k.startswith('variable_')}
        self.p.update(toolhead={'homed_axes':'xyz','max_accel':50000},gcode_move={'gcode_position':[60,60,50,0]},
            probe={'last_query':False},extruder={'target':150,'can_extrude':True},heater_bed={'target':100,'temperature':100},
            configfile={'settings':{section:dict(CFG.items(section)) for section in CFG.sections()},'config':{}},
            pause_resume={'is_paused':False},virtual_sdcard={'is_active':False},print_stats={'filename':'test.gcode','state':'standby'},
            gcode={'commands':dict.fromkeys(['MAYBE_HOME','PREHEAT','PICK_PARK_LOCATION','_FALLBACK_PURGE'])})
        self.out=[];self.queries=[];self.fail_on=None
    def emit(self,c):
        self.out.append(c)
        if c==self.fail_on:raise ValueError('injected failure')
        if c=='QUERY_PROBE' and self.queries:self.p['probe']['last_query']=self.queries.pop(0)
        if c.startswith('SET_KINEMATIC_POSITION'):
            if 'SET_HOMED=Z' in c:self.p['toolhead']['homed_axes']+='z'
            if 'CLEAR_HOMED=Z' in c:self.p['toolhead']['homed_axes']=self.p['toolhead']['homed_axes'].replace('z','')
        if c.startswith('G28 '):
            axis=c[-1].lower();self.p['toolhead']['homed_axes']=''.join(sorted(set(self.p['toolhead']['homed_axes']+axis)))
        if c.startswith('G1 '):
            for token in c.split()[1:]:
                if token[0] in 'XYZ':self.p['gcode_move']['gcode_position']['XYZ'.index(token[0])]=float(token[1:])
        if c=='_PROBE_CALIBRATE_BASE':self.p['gcode_move']['gcode_position']=[60,60,5,0]
        if c in ('DEPLOY_PROBE','STOW_PROBE'):
            # Model only the changed position of docking, not hardware behavior.
            self.p['gcode_move']['gcode_position']=[1,100,50,0]
    def script(self,name,params=None):
        def fail(message):raise ValueError(message)
        context=dict(printer=self.p,params=params or {},rawparams='HOTEND_TEMP=260 BED_TEMP=100',
            math=math,emit=self.emit,raise_error=fail,respond_info=lambda m:None,wait_moves=lambda:None,
            set_gcode_variable=lambda macro,key,value:self.p['gcode_macro '+macro].__setitem__(key,value))
        exec(compile((ROOT/'custom/macros/python'/name).read_text(),name,'exec'),context,{})
    def render(self,name,params=None):
        env=jinja2.Environment('{%','%}','{','}',extensions=['jinja2.ext.do','jinja2.ext.loopcontrols'])
        def fail(message):raise ValueError(message)
        return env.from_string(CFG.get('gcode_macro '+name,'gcode')).render(printer=self.p,params=params or {},rawparams='',action_raise_error=fail,action_respond_info=lambda m:'',**self.p['gcode_macro '+name])

class MigrationTests(unittest.TestCase):
    def test_fresh_query_controls_attachment_and_preserves_route(self):
        r=Runtime();r.queries=[True,False]
        r.script('zeroclick.py',{'ACTION':'attach'})
        moves=[c for c in r.out if c.startswith('G1 X')]
        self.assertEqual(moves,['G1 X1 Y100 F6000.0','G1 X1 Y118 F6000.0','G1 X28 Y118 F6000.0','G1 X28 Y100 F6000.0','G1 X1 Y100 F6000.0'])
        self.assertIn('G1 Z50 F600',r.out)
    def test_failed_attachment_stops_before_probing(self):
        r=Runtime();r.queries=[True,True]
        with self.assertRaisesRegex(ValueError,'attach failed'):r.script('zeroclick.py',{'ACTION':'attach'})
        self.assertIn('RESTORE_GCODE_STATE NAME=_ZEROCLICK_MOVE',r.out)
        self.assertFalse(any(c.startswith('G28') for c in r.out))
    def test_homing_failure_restores_currents_accel_and_unknown_z(self):
        r=Runtime();r.p['toolhead']['homed_axes']='';r.fail_on='G28 X'
        with self.assertRaisesRegex(ValueError,'injected'):r.script('home.py')
        self.assertNotIn('z',r.p['toolhead']['homed_axes'])
        self.assertEqual(r.out[-4:],['SET_TMC_CURRENT STEPPER=stepper_x CURRENT=1.8','SET_TMC_CURRENT STEPPER=stepper_y CURRENT=1.8','RESTORE_GCODE_STATE NAME=_TRIZERO_HOME','SET_VELOCITY_LIMIT ACCEL=50000'])
        self.assertNotIn('DEPLOY_PROBE',r.out)
    def test_z_only_homes_missing_xy_before_attachment(self):
        r=Runtime();r.p['toolhead']['homed_axes']='';r.script('home.py',{'Z':'0'})
        self.assertLess(r.out.index('G28 X'),r.out.index('DEPLOY_PROBE'))
        self.assertLess(r.out.index('G28 Y'),r.out.index('DEPLOY_PROBE'))
        self.assertLess(r.out.index('DEPLOY_PROBE'),r.out.index('G28 Z'))
    def test_calibration_returns_to_post_probe_manual_position(self):
        r=Runtime();r.script('probe_operation.py',{'COMMAND':'_PROBE_CALIBRATE_BASE'})
        self.assertLess(r.out.index('_PROBE_CALIBRATE_BASE'),r.out.index('STOW_PROBE'))
        self.assertEqual(r.p['gcode_move']['gcode_position'][:3],[60,60,5])
    def test_failed_probe_does_not_attempt_blind_dock(self):
        r=Runtime();r.fail_on='_PROBE_BASE'
        with self.assertRaises(ValueError):r.script('probe_operation.py',{'COMMAND':'_PROBE_BASE'})
        self.assertNotIn('STOW_PROBE',r.out)
    def test_single_extruder_slot_and_missing_chamber_sensor(self):
        r=Runtime()
        self.assertIn('ignoring slicer TOOL=1',r.render('PRINT_START_PREFLIGHT',{'HOTEND_TEMP':'260','TOOL':'1'}))
        r.p['mmu']={'enabled':False}
        self.assertIn('ignoring slicer TOOL=1',r.render('PRINT_START_PREFLIGHT',{'HOTEND_TEMP':'260','TOOL':'1'}))
        with self.assertRaisesRegex(ValueError,'without a configured chamber sensor'):
            r.render('PRINT_START_PREFLIGHT',{'HOTEND_TEMP':'260','TARGET_CHAMBER_TEMP':'40'})
    def test_nonbeacon_start_preheats_at_probe_temperature(self):
        r=Runtime();r.script('print_start.py',{'HOTEND_TEMP':'260','BED_TEMP':'100'})
        self.assertTrue(any(c.startswith('PREHEAT STARTUP=1 HOTEND_TEMP=150.0') for c in r.out))
    def test_legacy_slicer_temperature_list_selects_initial_slot(self):
        r=Runtime()
        self.assertIn('HOTEND_TEMP=260',r.render('START_PRINT',{'EXTRUDER_TEMP':'240,260','INITIAL_TOOL':'1','BED_TEMP':'100'}))
    def test_legacy_alias_establishes_relative_extrusion_before_start(self):
        r=Runtime();lines=r.render('START_PRINT',{'EXTRUDER_TEMP':'260'}).splitlines()
        mode='absolute'
        for line in lines:
            if line.strip()=='M83':mode='relative'
            if line.strip().startswith('PRINT_START '):self.assertEqual(mode,'relative')
    def test_cancel_shutdown_precedes_optional_cleanup(self):
        r=Runtime();lines=[l.strip() for l in r.render('CANCEL_PRINT').splitlines() if l.strip() and not l.strip().startswith('#')]
        self.assertEqual(lines[:2],['TURN_OFF_HEATERS_BASE','BASE_CANCEL_PRINT'])
        self.assertFalse(any('PARK' in c or 'G28' in c for c in lines))

if __name__=='__main__':unittest.main()
