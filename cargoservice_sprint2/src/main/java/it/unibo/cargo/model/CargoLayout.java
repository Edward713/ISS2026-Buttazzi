package it.unibo.cargo.model;

import java.util.Map;
import java.util.Set;

/** Griglia della scena WEnv fornita: X del navigatore=riga, Y=colonna.
 * HOME fisica=(-12.4,-7.92); un passo nominale e 60*0.2*0.335=4.02 unita.
 * Ultima riga e ultima colonna rappresentano i muri, non destinazioni navigabili.
 */
public final class CargoLayout implements Layout {
    private static final Set<Position> OBSTACLES = Set.of(
        new Position(1, 2), new Position(1, 3), new Position(2, 4),
        new Position(3, 2), new Position(3, 3));
    private final Map<Target, Destination> destinations = Map.of(
        Target.HOME, at(0, 0, 0, 0), Target.IOPORT, at(4, 0, 4, 0),
        Target.SLOT1, at(1, 2, 0, 2), Target.SLOT2, at(1, 3, 0, 3),
        Target.SLOT3, at(3, 2, 4, 2), Target.SLOT4, at(3, 3, 4, 3),
        Target.SLOT5, at(2, 4, 2, 5));

    private static Destination at(int row, int column, int accessRow, int accessColumn) {
        return new CellDestination(Set.of(new Position(row, column)), new Position(accessRow, accessColumn));
    }
    private record CellDestination(Set<Position> area, Position accessPoint) implements Destination { }
    public int rows() { return 6; }
    public int columns() { return 8; }
    public boolean isTraversable(Position p) {
        return p != null && p.row() >= 0 && p.row() < rows() - 1 && p.column() >= 0
            && p.column() < columns() - 1 && !OBSTACLES.contains(p);
    }
    public Destination destination(Target target) {
        if (target == null) throw new IllegalArgumentException("Missing target");
        return destinations.get(target);
    }
    /** Formato di tf25map.txt letto da RobotSmart26: righe separate da @, 1=ostacolo. */
    public String robotMap() {
        StringBuilder map = new StringBuilder();
        for (int row = 0; row < rows(); row++) {
            if (row > 0) map.append('@');
            for (int col = 0; col < columns(); col++)
                map.append(isTraversable(new Position(row, col)) ? '0' : '1');
        }
        return map.toString();
    }
}
