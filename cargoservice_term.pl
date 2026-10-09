%====================================================================================
% cargoservice_term description   
%====================================================================================
request( load_request, load_request(none) ).
reply( load_accepted, load_accepted(SLOT) ).  %%for load_request
reply( retrylater, retrylater(none) ).  %%for load_request
reply( load_refused, load_refused(none) ).  %%for load_request
dispatch( button_pressed, button_pressed(none) ).
dispatch( display_update, display_update(DATA) ).
dispatch( led_command, led_command(MODE) ).
dispatch( sensor_state, sensor_state(CONDITION) ).
request( reach_target, reach_target(TARGET) ).
reply( target_reached, target_reached(TARGET) ).  %%for reach_target
dispatch( sonar_sample, sonar_sample(D) ).
%====================================================================================
context(ctxcargoservice, "localhost",  "TCP", "8020").
context(ctxioport, "localhost",  "TCP", "8021").
context(ctxrobot, "localhost",  "TCP", "8022").
context(ctxsensor, "localhost",  "TCP", "8023").
 qactor( cargoservice, ctxcargoservice, "it.unibo.cargoservice.Cargoservice").
 static(cargoservice).
  qactor( ioportservice, ctxioport, "it.unibo.ioportservice.Ioportservice").
 static(ioportservice).
  qactor( cargorobot, ctxrobot, "it.unibo.cargorobot.Cargorobot").
 static(cargorobot).
  qactor( sensorservice, ctxsensor, "it.unibo.sensorservice.Sensorservice").
 static(sensorservice).
