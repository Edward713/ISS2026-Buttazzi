package it.unibo.cargo.tools;

/** Sequenza D:durataMillis separata da virgole; campioni ogni 100 ms come eventi QAK. */
public final class SonarSimulator {
    public static void main(String[] args) throws Exception {
        String sequence = args.length == 0 ? "100:1000,40:4000,100:1000" : args[0];
        try (var sensor = new QakTcpClient(8023, "sensorservice")) {
            for (String segment : sequence.split(",")) {
                String[] values = segment.split(":");
                double distance = Double.parseDouble(values[0]);
                long duration = Long.parseLong(values[1]);
                if (duration <= 0) throw new IllegalArgumentException("Duration must be positive");
                long end = System.nanoTime() + duration * 1_000_000;
                do {
                    sensor.send("sonar_sample", "event", Double.toString(distance));
                    Thread.sleep(100);
                } while (System.nanoTime() < end);
            }
        }
    }
}
