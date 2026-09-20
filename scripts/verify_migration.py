#!/usr/bin/env python3
"""Read-only source checks using Kalico's actual include/SAVE_CONFIG parser.
Usage: python scripts/verify_migration.py --kalico-source /path/to/kalico
Requires Jinja2. Does not connect to MCUs or qualify motion/thermal behavior.
"""
import argparse
import ast
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import jinja2

ROOT = Path(__file__).resolve().parents[1]

def parse_config(kalico_source):
    sys.path.insert(0, str(kalico_source))
    # Load only the real parser, bypassing klippy.__init__ MCU/serial runtime imports.
    package=ModuleType('klippy')
    package.__path__=[str(kalico_source/'klippy')]
    sys.modules['klippy']=package
    from klippy.configfile import PrinterConfig
    class Printer:
        def lookup_object(self, name):
            return SimpleNamespace(ready_gcode_handlers={'SAVE_CONFIG': True})
        def get_start_args(self):
            return {'config_file': str(ROOT/'printer.cfg')}
    return PrinterConfig(Printer()).read_main_config().fileconfig

def verify(cfg, kalico_source):
    env=jinja2.Environment('{%','%}','{','}',extensions=['jinja2.ext.do','jinja2.ext.loopcontrols'])
    compiled=0
    for section in cfg.sections():
        # Every active extension must exist in clean Kalico; no RatOS/addon requirement.
        kind=section.split()[0]
        if kind not in ('printer','mcu','constants','extruder') and not kind.startswith('stepper_'):
            module=kalico_source/'klippy/extras'/kind
            assert module.with_suffix('.py').is_file() or (module/'__init__.py').is_file(), ('unavailable module',section)
        assert not (kind.startswith('ratos') or section == 'gcode_macro RatOS'), ('RatOS section remains',section)
        if cfg.has_option(section,'gcode'):
            source=cfg.get(section,'gcode').strip()
            if source.startswith('!!include '):
                path=Path(source.split(maxsplit=1)[1]);assert path.is_relative_to(ROOT)
                compile(path.read_text(),str(path),'exec')
            elif source.startswith('!'):
                compile('\n'.join(line.lstrip()[1:] for line in source.splitlines()),section,'exec')
            else: env.from_string(source)
            compiled+=1
    assert cfg.get('printer','kinematics')=='corexy'
    assert cfg.getfloat('probe','z_offset')==9.199
    assert cfg.get('probe','pin')=='^toolboard_t0:PB8'
    assert cfg.getfloat('stepper_x','position_max')==118
    assert cfg.getfloat('stepper_y','position_max')==118
    assert cfg.getfloat('stepper_z','position_max')==115
    assert cfg.getfloat('extruder','pid_kp')==16.863
    assert cfg.getfloat('heater_bed','pid_kp')==72.068
    assert cfg.getfloat('printer','max_accel')==50000
    assert cfg.getfloat('tmc5160 stepper_x','run_current')==1.8
    assert cfg.getfloat('tmc2209 extruder','run_current')==.85
    for axis in ('z','z1','z2'):
        assert cfg.getfloat('stepper_'+axis,'rotation_distance')==40
        assert cfg.getint('stepper_'+axis,'microsteps')==128
    # Mesh corners are probe coordinates; check the required nozzle travel.
    for option in ('mesh_min','mesh_max'):
        xy=[float(x) for x in cfg.get('bed_mesh',option).split(',')]
        for index,axis in enumerate('xy'):
            nozzle=xy[index]-cfg.getfloat('probe',axis+'_offset')
            assert cfg.getfloat('stepper_'+axis,'position_min') <= nozzle <= cfg.getfloat('stepper_'+axis,'position_max')
    assert cfg.get('save_variables','filename').endswith('/ratos-variables.cfg')
    assert not cfg.has_section('gcode_macro T0'), 'No fake tool system on a single extruder'
    vars={k[9:]:ast.literal_eval(v) for k,v in cfg.items('gcode_macro _PRINTER_VARS') if k.startswith('variable_')}
    assert vars['default_chamber_target']==0 and not vars['chamber_fan']
    print('PASS: Kalico include/SAVE_CONFIG parser; %d templates; local hardware invariants.' % compiled)
    print('MCU serials require installation-specific values. No runtime or physical qualification.')
    return compiled

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kalico-source',type=Path,required=True)
    args=parser.parse_args()
    verify(parse_config(args.kalico_source),args.kalico_source)
