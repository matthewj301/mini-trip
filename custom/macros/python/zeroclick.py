action = params.get('ACTION', '')
if action not in ('attach', 'detach'):
    raise_error('ZeroClick: ACTION must be attach or detach')
if not all(axis in printer['toolhead']['homed_axes'] for axis in 'xy'):
    raise_error('ZeroClick: home X and Y before docking')
emit('M400')
emit('QUERY_PROBE')
is_stowed = printer['probe']['last_query']
if (action == 'attach' and is_stowed) or (action == 'detach' and not is_stowed):
    v = printer['gcode_macro _ZEROCLICK']
    accel = printer['toolhead']['max_accel']
    emit('SAVE_GCODE_STATE NAME=_ZEROCLICK_MOVE')
    try:
        emit('G90')
        emit('SET_VELOCITY_LIMIT ACCEL=%s' % printer['gcode_macro _PRINTER_VARS']['travel_accel'])
        if 'z' in printer['toolhead']['homed_axes']:
            # Never lower the bed clearance to a fixed height during a dock move.
            z = max(printer['gcode_move']['gcode_position'][2], float(v['clearance']))
            emit('G1 Z%s F600' % z)
        route = ['preflight','side','dock','exit','preflight'] if action == 'attach' else ['preflight','exit','dock','side','preflight']
        for key in route:
            xy = v[key]
            emit('G1 X%s Y%s F%s' % (xy[0], xy[1], float(v['speed'])*60))
        emit('M400')
        emit('G4 P100')
        emit('QUERY_PROBE')
        if printer['probe']['last_query'] != (action == 'detach'):
            raise_error('ZeroClick: %s failed; check the probe before any further motion' % action)
    finally:
        emit('RESTORE_GCODE_STATE NAME=_ZEROCLICK_MOVE')
        emit('SET_VELOCITY_LIMIT ACCEL=%s' % accel)
