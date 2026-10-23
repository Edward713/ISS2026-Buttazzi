package it.unibo.cargo.model;

import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;
import static it.unibo.cargo.model.LoadOperation.Phase.*;

/** Aggregato posseduto esclusivamente dall'attore cargoservice; non invia messaggi. */
public final class CargoState {
    private InMemoryHoldInventory inventory = new InMemoryHoldInventory();
    private InMemoryMarkingBuffer buffer = new InMemoryMarkingBuffer();
    private ServiceStatus status = ServiceStatus.WORKING;
    private LoadOperation operation;
    private boolean ioportOccupied;
    private String error = "";

    public LoadOperation operation() { return operation; }
    public ServiceStatus status() { return status; }
    public LoadOperation.Phase phase() { return operation == null ? DISENGAGED : operation.phase(); }
    public boolean canAccept() { return phase() == DISENGAGED && status == ServiceStatus.WORKING && !ioportOccupied; }
    public boolean accept(long now, long waitMillis) {
        if (!canAccept()) return false;
        var slot = inventory.reserveFirstAvailable();
        if (slot.isEmpty()) return false;
        operation = new LoadOperation("load_" + UUID.randomUUID().toString().replace("-", ""), slot.getAsInt(), now + waitMillis);
        return true;
    }
    public void sensor(String condition) {
        if (condition.equals("present")) ioportOccupied = true;
        else if (condition.equals("free")) ioportOccupied = false;
    }
    public boolean confirmPresence(long now) {
        if (status != ServiceStatus.WORKING || phase() != WAIT_CONTAINER || now > operation.arrivalDeadlineMillis()) return false;
        ioportOccupied = true;
        operation.moving(TO_IOPORT, Target.IOPORT);
        return true;
    }
    public boolean expire(String operationId, long now) {
        if (phase() != WAIT_CONTAINER || !operation.id().equals(operationId) || now < operation.arrivalDeadlineMillis()) return false;
        inventory.releaseReservation(operation.slotId());
        operation = null;
        return true;
    }
    public boolean expects(String target) {
        return status == ServiceStatus.WORKING && operation != null && operation.target() != null
            && operation.navigationState() == LoadOperation.NavigationState.MOVING
            && operation.target().name().equalsIgnoreCase(target);
    }
    public void arrive(String target) {
        if (!expects(target)) return;
        operation.arrived();
        switch (phase()) {
            case TO_IOPORT -> { ioportOccupied = false; operation.moving(TO_SLOT5, Target.SLOT5); }
            case TO_SLOT5 -> { buffer.confirmDeposit(operation.id()); operation.phase(WAIT_MARKER); }
            case TO_FINAL -> {
                // Il deposito finale attesta anche il prelievo da slot5, senza una tratta aggiuntiva.
                inventory.confirmDeposit(operation.slotId(), operation.barcode());
                buffer.confirmCollection();
                operation.moving(RETURN_HOME, Target.HOME);
            }
            case RETURN_HOME -> operation = null;
            default -> throw new IllegalStateException("Unexpected arrival");
        }
    }
    public boolean finishMarking(String id) {
        if (status != ServiceStatus.WORKING || phase() != WAIT_MARKER || !operation.id().equals(id)) return false;
        operation.barcode("BC_" + UUID.randomUUID().toString().replace("-", ""));
        buffer.applyBarcode(operation.barcode());
        operation.moving(TO_FINAL, Target.valueOf("SLOT" + operation.slotId()));
        return true;
    }
    public void fail(String reason) {
        if (operation == null) return;
        status = ServiceStatus.OUT_OF_SERVICE;
        error = reason;
        operation.failed();
    }
    /** Ripristino OOS solo col flag di test, mai durante un carico operativo. */
    public String setup(String mode, boolean testMode) {
        if (phase() != DISENGAGED && !(testMode && status == ServiceStatus.OUT_OF_SERVICE)) return "busy";
        if (status == ServiceStatus.OUT_OF_SERVICE && !testMode) return "out_of_service";
        if (!mode.equals("empty") && !mode.equals("full") && !mode.equals("slot1_occupied")) return "invalid_mode";
        inventory = new InMemoryHoldInventory();
        buffer = new InMemoryMarkingBuffer();
        int count = mode.equals("full") ? 4 : mode.equals("slot1_occupied") ? 1 : 0;
        for (int i = 1; i <= count; i++) inventory.confirmDeposit(inventory.reserveFirstAvailable().orElseThrow(), "preset_" + i);
        operation = null;
        status = ServiceStatus.WORKING;
        if (testMode) ioportOccupied = false;
        error = "";
        return "ok";
    }
    public String snapshot() {
        JSONObject json = new JSONObject();
        json.put("serviceStatus", status.name()).put("phase", phase().name()).put("ioportOccupied", ioportOccupied);
        JSONArray slots = new JSONArray();
        for (int id = 1; id <= 4; id++) slots.put(new JSONObject().put("id", id).put("state", inventory.stateOf(id).name())
            .put("barcode", inventory.containerId(id).orElse("")));
        json.put("slots", slots).put("slot5", buffer.containerId().orElse("")).put("error", error);
        if (operation != null) json.put("operation", new JSONObject().put("id", operation.id()).put("slot", operation.slotId())
            .put("barcode", operation.barcode() == null ? "" : operation.barcode())
            .put("deadline", operation.arrivalDeadlineMillis()).put("navigationState", operation.navigationState().name())
            .put("target", operation.target() == null ? "" : operation.target().name()));
        return json.toString();
    }
}
