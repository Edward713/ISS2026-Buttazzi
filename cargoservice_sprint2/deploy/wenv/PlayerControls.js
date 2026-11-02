// WEnv course adapter: integrate each translation through its command deadline,
// including the interval between the last rendered frame and key release.
import * as THREE from '../../node_modules/three/build/three.module.js'
import eventBus from '../eventBus/EventBus.js'
import eventBusEvents from '../eventBus/events.js'

export default (mesh, camera, config, collisionManager, mirror) => {
    const keys = { W: 87, A: 65, S: 83, D: 68, Z: 90 }
    let motion = null
    let advancing = false
    let rotating = false
    let tween

    function setCameraPositionRelativeToMesh() {
        camera.position.x = mesh.position.x
        camera.position.z = mesh.position.z + 20
        camera.lookAt(new THREE.Vector3(mesh.position.x, 0, mesh.position.z))
    }
    setCameraPositionRelativeToMesh()

    function advance(now) {
        if (!motion || advancing) return
        advancing = true
        const active = motion
        try {
            const elapsed = Math.min(active.duration, Math.max(0, now - active.start))
            let seconds = Math.max(0, elapsed - active.elapsed) / 1000
            active.elapsed = elapsed
            // Small increments retain collision detection when no frames were drawn.
            while (seconds > 1e-10 && motion === active) {
                const dt = Math.min(seconds, 1 / 120)
                const distance = 60 * config.speed * active.direction * dt
                // Read the current angle, not the previous renderer's cached matrix.
                const step = new THREE.Vector3(
                    Math.sin(mesh.rotation.y) * distance, 0,
                    Math.cos(mesh.rotation.y) * distance)
                const next = mesh.position.clone().add(step)
                const collision = collisionManager.checkCollision(next, mirror)
                // A collision synchronously invokes SocketIO.stopMoving/onKeyUp.
                if (collision || motion !== active) { motion = null; break }
                mesh.position.add(step)
                camera.position.add(step)
                seconds -= dt
            }
        } finally { advancing = false }
    }

    function stopRotating() {
        rotating = false
        if (tween) tween.stop()
    }

    function rotate(angle, duration, moveindex) {
        if (rotating) return
        const finalAngle = mesh.rotation.y + angle
        rotating = true
        tween = new TWEEN.Tween(mesh.rotation)
            .to({ y: finalAngle }, duration)
            .easing(TWEEN.Easing.Quadratic.InOut)
            .onComplete(() => {
                mesh.rotation.y = finalAngle
                rotating = false
                eventBus.post(eventBusEvents.endmove, moveindex)
            }).start()
    }

    function onKeyDown(keyCode, duration = 300, moveindex) {
        if (keyCode === keys.W || keyCode === keys.S) {
            if (motion && motion.key === keyCode) return
            advance(performance.now())
            motion = {
                key: keyCode, direction: keyCode === keys.W ? 1 : -1,
                start: performance.now(), elapsed: 0,
                duration: moveindex === true && Number(duration) >= 0
                    ? Number(duration) : Infinity
            }
        } else if (keyCode === keys.Z) stopRotating()
        else if (keyCode === keys.D) rotate(-Math.PI / 2, duration, moveindex)
        else if (keyCode === keys.A) rotate(Math.PI / 2, duration, moveindex)
    }

    function onKeyUp(keyCode) {
        if (!motion || motion.key !== keyCode) return
        advance(performance.now())
        if (motion) console.log('CargoWEnv | translation complete',
            motion.elapsed, mesh.position.x, mesh.position.z)
        motion = null
    }

    function update() {
        if (motion) advance(performance.now())
        else collisionManager.checkCollision(mesh.position)
    }

    function resetPosition() {
        motion = null
        stopRotating()
        mesh.position.x = config.position.x
        mesh.position.z = config.position.y
        mesh.rotation.y = 0
        setCameraPositionRelativeToMesh()
    }

    return { resetPosition, onKeyDown, onKeyUp, update, stopRotating }
}
