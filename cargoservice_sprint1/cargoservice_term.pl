%====================================================================================
% cargoservice_term description   
%====================================================================================
request( load_request, load_request(none) ).
reply( load_accepted, load_accepted(SLOT) ).  %%for load_request
reply( retrylater, retrylater(none) ).  %%for load_request
reply( load_refused, load_refused(none) ).  %%for load_request
request( get_hold_status, get_hold_status(none) ).
reply( hold_state, hold_state(DATA) ).  %%for get_hold_status
request( setup_hold, setup_hold(MODE) ).
reply( preset_ack, preset_ack(RESULT) ).  %%for setup_hold
dispatch( button_pressed, button_pressed(none) ).
dispatch( display_update, display_update(DATA) ).
dispatch( led_command, led_command(MODE) ).
dispatch( sensor_state, sensor_state(CONDITION) ).
event( sonar_sample, sonar_sample(D) ).
dispatch( wait_timeout, wait_timeout(ID) ).
dispatch( marker_done, marker_done(ID) ).
dispatch( navigation_timeout, navigation_timeout(ID,TARGET) ).
request( reach_target, reach_target(TARGET) ).
reply( target_reached, target_reached(TARGET) ).  %%for reach_target
reply( target_failed, target_failed(TARGET) ).  %%for reach_target
request( moverobot, moverobot(X,Y,STEPTIME) ).
reply( moverobotdone, moverobotok(ARG) ).  %%for moverobot
reply( moverobotfailed, moverobotfailed(DONE,TODO) ).  %%for moverobot
reply( failed, failed(REASON) ).  %%for moverobot
dispatch( move_done, move_done(ID) ).
dispatch( move_failed, move_failed(ID) ).
request( mock_control, mock_control(TARGET,DELAY) ).
reply( mock_ack, mock_ack(RESULT) ).  %%for mock_control
request( get_robot_status, get_robot_status(none) ).
reply( robot_status, robot_status(DATA) ).  %%for get_robot_status
request( get_sensor_status, get_sensor_status(none) ).
reply( sensor_status, sensor_status(DATA) ).  %%for get_sensor_status
request( reset_sensor, reset_sensor(none) ).
reply( sensor_reset, sensor_reset(RESULT) ).  %%for reset_sensor
request( get_ioport_status, get_ioport_status(none) ).
reply( ioport_status, ioport_status(DATA) ).  %%for get_ioport_status
%====================================================================================
context(ctxcargoservice, "localhost",  "TCP", "8020").
context(ctxcargorobot, "localhost",  "TCP", "8021").
context(ctxioport, "localhost",  "TCP", "8022").
context(ctxsensor, "localhost",  "TCP", "8023").
context(ctxrobotsmart, "127.0.0.1",  "TCP", "8019").
 qactor( robotsmart, ctxrobotsmart, "external").
  qactor( cargoservice, ctxcargoservice, "it.unibo.cargoservice.Cargoservice").
 static(cargoservice).
  qactor( cargorobot, ctxcargorobot, "it.unibo.cargorobot.Cargorobot").
 static(cargorobot).
  qactor( sensorservice, ctxsensor, "it.unibo.sensorservice.Sensorservice").
 static(sensorservice).
  qactor( ioportservice, ctxioport, "it.unibo.ioportservice.Ioportservice").
 static(ioportservice).
