package it.unibo.cargo;

import it.unibo.cargo.model.*;
import org.junit.Test;
import static org.junit.Assert.*;

/** Fixture della scena letta da localhost:8090/sceneConfig.js.
 * StaticObstacle inverte Z e allarga ogni rettangolo di padding=2.
 * PlayerControls percorre nominalmente 60*speed*secondi per passo.
 */
public class WenvGeometryTest {
    private record Block(double x, double y, double width, double height) {
        boolean collides(double worldX, double worldZ) {
            double cx = (x - .5) * 31;
            double cy = (y - .5) * 24;
            return Math.abs(worldX - cx) <= width * 31 / 2 + 2
                && Math.abs(-worldZ - cy) <= height * 24 / 2 + 2;
        }
    }
    private final Block[] blocks = {
        new Block(.4, .65, .08, .065), new Block(.5, .65, .08, .065),
        new Block(.4, .3, .08, .065), new Block(.5, .3, .08, .065),
        new Block(.61, .49, .07, .065),
        new Block(.49, .97, .96, .02), new Block(.05, .01, .05, .01),
        new Block(.6, .01, .77, .01), new Block(.02, .48, .01, .94),
        new Block(.98, .5, .01, .99)
    };
    private boolean free(double row, double column) {
        double step = 60 * .2 * .335;
        double x = (.10 - .5) * 31 + column * step;
        double z = (.17 - .5) * 24 + row * step;
        if (Math.abs(x) > 31 / 2.0 || Math.abs(z) > 24 / 2.0) return false;
        for (Block block : blocks) if (block.collides(x, z)) return false;
        return true;
    }
    @Test public void everyCellMatchesTheActualSceneCollisionGeometry() {
        var layout = new CargoLayout();
        for (int row = 0; row < layout.rows(); row++) {
            for (int col = 0; col < layout.columns(); col++) {
                assertEquals("row=" + row + ",column=" + col,
                    free(row, col), layout.isTraversable(new Position(row, col)));
            }
        }
        for (Target target : Target.values()) {
            Position access = layout.destination(target).accessPoint();
            assertTrue(target.name(), free(access.row(), access.column()));
        }
    }
    @Test public void traversableGridEdgesDoNotCrossAnExpandedWenvObstacle() {
        var layout = new CargoLayout();
        for (int row = 0; row < layout.rows(); row++) {
            for (int col = 0; col < layout.columns(); col++) {
                if (!layout.isTraversable(new Position(row, col))) continue;
                for (int[] direction : new int[][]{{1, 0}, {0, 1}}) {
                    if (!layout.isTraversable(new Position(row + direction[0], col + direction[1]))) continue;
                    for (int sample = 0; sample <= 100; sample++) {
                        double fraction = sample / 100.0;
                        assertTrue("Segment from " + row + "," + col,
                            free(row + fraction * direction[0], col + fraction * direction[1]));
                    }
                }
            }
        }
    }
}
