package it.unibo.cargo.model;

import java.util.HashSet;
import java.util.Set;
import org.json.JSONObject;

/** Filtro temporale a tempo monotono. Solo nuovi campioni possono confermare una condizione. */
public final class SonarMonitor {
    private final double dfree;
    private final long confirm, maxGap, stale;
    private long last = -1, candidateSince = -1, sequence = -1;
    private String session = "", candidate = "", condition = "unavailable", pending = "unavailable";
    private final Set<String> retired = new HashSet<>();

    public SonarMonitor(double dfree, long confirm, long maxGap, long stale) {
        if (!Double.isFinite(dfree) || dfree <= 0 || confirm <= 0 || maxGap <= 0 || stale < maxGap)
            throw new IllegalArgumentException("Invalid sonar configuration");
        this.dfree = dfree; this.confirm = confirm; this.maxGap = maxGap; this.stale = stale;
    }
    public void packet(String data, long now) {
        try {
            JSONObject p = new JSONObject(data);
            String next = p.getString("session");
            Object seqValue = p.get("seq");
            if (!next.matches("[A-Za-z0-9_:-]{1,100}") || !(seqValue instanceof Number)
                    || p.getDouble("seq") != p.getLong("seq") || p.getLong("seq") < 0)
                throw new IllegalArgumentException("Invalid session/sequence");
            long seq = p.getLong("seq");
            if (retired.contains(next) || (session.equals(next) && seq <= sequence)) return;
            if (!session.equals(next)) {
                if (!session.isEmpty()) retired.add(session);
                session = next; last = -1; candidate = ""; candidateSince = -1;
                set("unavailable");
            }
            sequence = seq;
            sample(p.getBoolean("valid") ? p.getDouble("distance") : Double.NaN, now);
        } catch (RuntimeException invalid) { sample(Double.NaN, now); }
    }
    public void sample(double distance, long now) {
        if (!Double.isFinite(distance) || distance < 0) {
            candidate = ""; candidateSince = -1; last = -1; set("unavailable"); return;
        }
        if (last < 0 || now < last || now - last > maxGap) {
            candidate = ""; candidateSince = -1; set("unavailable");
        }
        last = now;
        String next = distance < dfree / 2 ? "present" : distance > dfree ? "anomaly" : "free";
        if (next.equals("free")) {
            candidate = ""; candidateSince = -1; set("free"); return;
        }
        if (!candidate.equals(next)) { candidate = next; candidateSince = now; }
        if (now - candidateSince >= confirm) set(next);
        else set("unavailable"); // una presenza ancora da confermare non autorizza nuovi carichi
    }
    public void tick(long now) {
        if (last < 0 || now < last || now - last > stale) {
            candidate = ""; candidateSince = -1; set("unavailable");
        }
    }
    private void set(String value) {
        // free/present sono anche heartbeat aggregati per il controllo di freschezza del coordinatore.
        if (!condition.equals(value) || value.equals("free") || value.equals("present")) pending = value;
        condition = value;
    }
    public String drain() { String result = pending; pending = ""; return result; }
    public String condition() { return condition; }
}
