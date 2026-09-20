# Called inside homing_override: nested G28 invokes firmware's original homing.
v = printer['gcode_macro _HOMING_VARS']
requested = set(params).intersection(('X','Y','Z')) or set(('X','Y','Z'))
if 'Z' in requested:
    for axis in 'xy':
        if axis not in printer['toolhead']['homed_axes']:
            requested.add(axis.upper())
accel = printer['toolhead']['max_accel']
settings = printer['configfile']['settings']
x_current = settings['tmc5160 stepper_x']['run_current']
y_current = settings['tmc5160 stepper_y']['run_current']
emit('SAVE_GCODE_STATE NAME=_TRIZERO_HOME')
try:
    emit('G90')
    emit('SET_VELOCITY_LIMIT ACCEL=%s' % v['accel'])
    if 'z' not in printer['toolhead']['homed_axes']:
        # Same unknown-Z clearance strategy as Kalico safe_z_home; don't leave Z homed.
        emit('SET_KINEMATIC_POSITION Z=0 SET_HOMED=Z')
        try:
            emit('G1 Z%s F600' % v['z_hop'])
        finally:
            emit('SET_KINEMATIC_POSITION SET_HOMED= CLEAR_HOMED=Z')
    elif printer['gcode_move']['gcode_position'][2] < v['z_hop']:
        emit('G1 Z%s F600' % v['z_hop'])
    for axis in ('X','Y'):
        if axis in requested:
            current = v[axis.lower()+'_current']
            # CoreXY homing uses both motor currents, then restores both on every exit.
            emit('SET_TMC_CURRENT STEPPER=stepper_x CURRENT=%s' % current)
            emit('SET_TMC_CURRENT STEPPER=stepper_y CURRENT=%s' % current)
            emit('G4 P300')
            emit('G28 '+axis)
            emit('G1 %s59 F6000' % axis)
            emit('M400')
            emit('SET_TMC_CURRENT STEPPER=stepper_x CURRENT=%s' % x_current)
            emit('SET_TMC_CURRENT STEPPER=stepper_y CURRENT=%s' % y_current)
            emit('G4 P300')
    if 'Z' in requested:
        emit('DEPLOY_PROBE')
        emit('G1 X77 Y48 F6000')  # Probe at bed center (60,60), offsets (-17,+12).
        emit('G28 Z')
        emit('G1 Z15 F600')
        emit('STOW_PROBE')
finally:
    emit('SET_TMC_CURRENT STEPPER=stepper_x CURRENT=%s' % x_current)
    emit('SET_TMC_CURRENT STEPPER=stepper_y CURRENT=%s' % y_current)
    emit('RESTORE_GCODE_STATE NAME=_TRIZERO_HOME')
    emit('SET_VELOCITY_LIMIT ACCEL=%s' % accel)
