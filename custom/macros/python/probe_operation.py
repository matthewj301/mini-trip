command = params.get('COMMAND', '')
if command not in ('_Z_TILT_ADJUST_BASE','_BED_MESH_CALIBRATE_BASE','_PROBE_BASE','_PROBE_ACCURACY_BASE','_PROBE_CALIBRATE_BASE'):
    raise_error('ZeroClick: unsupported probe operation')
if printer['toolhead']['homed_axes'] != 'xyz':
    raise_error('ZeroClick: home all axes before probing')
position = printer['gcode_move']['gcode_position']
emit('SAVE_GCODE_STATE NAME=_ZEROCLICK_OPERATION')
try:
    emit('DEPLOY_PROBE')
    emit('G90')
    emit('G1 X%s Y%s F6000' % (position[0], position[1]))
    # Forward parameters individually, excluding our private dispatch selector.
    arguments = ''
    for key, value in params.items():
        if key != 'COMMAND':
            arguments += ' %s=%s' % (key, value)
    emit(command + arguments)
    # Save the successful operation's result position, not its starting height.
    # In particular PROBE_CALIBRATE has now positioned the nozzle for manual probing.
    result = printer['gcode_move']['gcode_position']
    emit('STOW_PROBE')
    emit('G90')
    emit('G1 X%s Y%s F6000' % (result[0], result[1]))
    emit('G1 Z%s F600' % result[2])
finally:
    # On a probing error leave the tool/probe where they stopped; no blind docking.
    emit('RESTORE_GCODE_STATE NAME=_ZEROCLICK_OPERATION')
