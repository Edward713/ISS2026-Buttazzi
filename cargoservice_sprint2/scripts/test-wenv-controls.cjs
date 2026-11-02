// Regression for timed commands across sparse/absent browser render frames.
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = readFileSync(process.argv[2] || resolve(__dirname, '../deploy/wenv/PlayerControls.js'), 'utf8')
    .replace(/^import .*$/gm, '').replace('export default', 'globalThis.createControls =');
function fixture(blockAt = Infinity) {
    let now = 0, controls;
    class Vector3 {
        constructor(x=0, y=0, z=0) { Object.assign(this, {x,y,z}); }
        clone() { return new Vector3(this.x, this.y, this.z); }
        add(v) { this.x+=v.x; this.y+=v.y; this.z+=v.z; return this; }
    }
    const mesh = {position:new Vector3(), rotation:{y:0}};
    const camera = {position:new Vector3(), lookAt() {}};
    const scope = {THREE:{Vector3}, performance:{now:()=>now}, console:{log(){}},
        eventBus:{post(){}}, eventBusEvents:{endmove:'endmove'}};
    vm.runInNewContext(source, scope);
    controls = scope.createControls(mesh, camera, {speed:.2,position:{x:0,y:0}}, {
        checkCollision(p) {
            if (p.z < blockAt) return false;
            controls.onKeyUp(87); // Real SocketIO collision handler is synchronous.
            return true;
        }
    }, false);
    return {mesh, controls, time(t){now=t;}};
}
const close = (a,b) => assert.ok(Math.abs(a-b)<1e-8, `${a} != ${b}`);
let count=0;
function test(name, run) { run(); count++; console.log('PASS', name); }
test('335 ms step completes without a rendered frame', () => {
    const f=fixture(); f.controls.onKeyDown(87,335,true);
    f.time(335); f.controls.onKeyUp(87); close(f.mesh.position.z,4.02);
});
test('four steps with idle gaps cover the full four cells', () => {
    const f=fixture();
    for(let i=0;i<4;i++) {
        f.time(i*1000); f.controls.onKeyDown(87,335,true);
        f.time(i*1000+335); f.controls.onKeyUp(87);
    }
    close(f.mesh.position.z,16.08);
});
test('render cadence and delayed stop do not change command distance', () => {
    for(const cadence of [16,67,250,1000]) {
        const f=fixture(); f.time(10000); f.controls.onKeyDown(87,335,true);
        for(let t=10000+cadence;t<11000;t+=cadence) {f.time(t); f.controls.update(t/1000);}
        f.time(11000); f.controls.onKeyUp(87); close(f.mesh.position.z,4.02);
    }
});
test('first step after a turn uses the current angle', () => {
    const f=fixture(); f.mesh.rotation.y=Math.PI/2;
    f.controls.onKeyDown(87,335,true); f.time(335); f.controls.onKeyUp(87);
    close(f.mesh.position.x,4.02); close(f.mesh.position.z,0);
});
test('a frame-free step still detects obstacles without recursive motion', () => {
    const f=fixture(2); f.controls.onKeyDown(87,335,true);
    f.time(335); f.controls.onKeyUp(87);
    assert.ok(f.mesh.position.z<2 && f.mesh.position.z>1.8);
    const stopped=f.mesh.position.z; f.time(2000); f.controls.update();
    close(f.mesh.position.z,stopped);
});
test('early halt and backward motion retain their actual duration', () => {
    const f=fixture(); f.controls.onKeyDown(87,335,true);
    f.time(100); f.controls.onKeyUp(87); close(f.mesh.position.z,1.2);
    f.controls.onKeyDown(83,100,true); f.time(200); f.controls.onKeyUp(83);
    close(f.mesh.position.z,0);
});
console.log(`${count} WEnv regression checks passed`);
