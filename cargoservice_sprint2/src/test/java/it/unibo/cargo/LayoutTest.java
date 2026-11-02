package it.unibo.cargo;

import it.unibo.cargo.model.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class LayoutTest {
    @Test public void suppliedRobotMapMatchesAllLayoutCellsAndReachableAccessPoints() throws Exception {
        var layout = new CargoLayout();
        assertEquals(6, layout.rows());
        assertEquals(8, layout.columns());
        assertEquals(new Position(4, 0), layout.destination(Target.IOPORT).accessPoint());
        assertEquals(Set.of(new Position(4, 0)), layout.destination(Target.IOPORT).area());
        assertEquals(layout.robotMap(), Files.readString(Path.of("config/tf25map.txt")).trim());
        assertEquals(new Position(0, 2), layout.destination(Target.SLOT1).accessPoint());
        assertEquals(new Position(0, 3), layout.destination(Target.SLOT2).accessPoint());
        assertEquals(new Position(4, 2), layout.destination(Target.SLOT3).accessPoint());
        assertEquals(new Position(4, 3), layout.destination(Target.SLOT4).accessPoint());
        assertEquals(new Position(2, 5), layout.destination(Target.SLOT5).accessPoint());
        Set<Position> visited = new HashSet<>();
        var queue = new ArrayDeque<Position>();
        queue.add(layout.destination(Target.HOME).accessPoint());
        while (!queue.isEmpty()) {
            Position p = queue.remove();
            if (!layout.isTraversable(p) || !visited.add(p)) continue;
            queue.add(new Position(p.row() - 1, p.column()));
            queue.add(new Position(p.row() + 1, p.column()));
            queue.add(new Position(p.row(), p.column() - 1));
            queue.add(new Position(p.row(), p.column() + 1));
        }
        for (Target target : Target.values()) assertTrue(target.name(), visited.contains(layout.destination(target).accessPoint()));
    }
}
