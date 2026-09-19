// ==========================================================
// DIGITAL AGENCY - GLOBO TERRÁQUEO 3D INTERACTIVO
// Rotación lenta, arrastrable (OrbitControls) y doble clic para
// identificar el país bajo el cursor (100% offline tras la carga
// inicial del GeoJSON, sin API de geocodificación externa).
// ==========================================================

(function () {
    const GLOBE_RADIUS = 100; // radio interno estándar de three-globe

    // Inversa exacta de la convención polar2Cartesian de three-globe:
    // x = r*sin(phi)*cos(theta), y = r*cos(phi), z = r*sin(phi)*sin(theta)
    // con phi = (90-lat)*PI/180 y theta = (90-lng)*PI/180.
    function cartesianToLatLng(point) {
        const r = point.length();
        const lat = 90 - (Math.acos(point.y / r) * 180) / Math.PI;
        let lng = 90 - (Math.atan2(point.z, point.x) * 180) / Math.PI;
        lng = ((lng + 180) % 360 + 360) % 360 - 180; // normalizar a [-180, 180]
        return { lat, lng };
    }

    // Algoritmo de ray-casting para punto-en-polígono (soporta Polygon y MultiPolygon de GeoJSON)
    function pointInRing(lat, lng, ring) {
        let inside = false;
        for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const xi = ring[i][0], yi = ring[i][1];
            const xj = ring[j][0], yj = ring[j][1];
            const intersect = ((yi > lat) !== (yj > lat)) &&
                (lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }

    function findCountry(lat, lng, features) {
        for (const feature of features) {
            const geom = feature.geometry;
            if (!geom) continue;
            if (geom.type === 'Polygon') {
                if (pointInRing(lat, lng, geom.coordinates[0])) return feature.properties;
            } else if (geom.type === 'MultiPolygon') {
                for (const poly of geom.coordinates) {
                    if (pointInRing(lat, lng, poly[0])) return feature.properties;
                }
            }
        }
        return null;
    }

    function showTooltip(container, x, y, text) {
        let tip = container.querySelector('.globe-country-tip');
        if (!tip) {
            tip = document.createElement('div');
            tip.className = 'globe-country-tip';
            tip.style.cssText = 'position:absolute;pointer-events:none;background:rgba(18,18,22,0.95);border:1px solid #38BDF8;color:#F3F4F6;padding:6px 12px;border-radius:8px;font-size:0.85rem;font-weight:700;box-shadow:0 8px 20px rgba(0,0,0,0.6);z-index:50;transition:opacity 0.3s ease;white-space:nowrap;';
            container.style.position = container.style.position || 'relative';
            container.appendChild(tip);
        }
        tip.textContent = text;
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
        tip.style.opacity = '1';
        clearTimeout(tip._hideTimer);
        tip._hideTimer = setTimeout(() => { tip.style.opacity = '0'; }, 3200);
    }

    function initGlobe(container) {
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x0a0a0c, 1);
        container.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);
        camera.position.z = 250;

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.rotateSpeed = 0.8;
        controls.enableZoom = false;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.35; // rotación lenta

        scene.add(new THREE.AmbientLight(0xffffff, 1.2));
        const dLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dLight.position.set(1, 1, 1).normalize();
        scene.add(dLight);

        const world = new ThreeGlobe()
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png');

        scene.add(world);

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });

        // Cargar los bordes de países (una sola vez) para dibujarlos sutilmente y
        // reutilizar los mismos datos como base de la búsqueda punto-en-polígono.
        fetch('https://raw.githack.com/johan/world.geo.json/master/countries.geo.json')
            .then(r => r.json())
            .catch(() => fetch('https://cdn.jsdelivr.net/gh/johan/world.geo.json@master/countries.geo.json').then(r => r.json()))
            .then(geojson => {
                if (!geojson || !geojson.features) return;
                world
                    .polygonsData(geojson.features)
                    .polygonCapColor(() => 'rgba(0,0,0,0)')
                    .polygonSideColor(() => 'rgba(0,0,0,0)')
                    .polygonStrokeColor(() => 'rgba(56,189,248,0.35)')
                    .polygonAltitude(0.002);

                const raycaster = new THREE.Raycaster();
                const mouse = new THREE.Vector2();

                renderer.domElement.addEventListener('dblclick', (event) => {
                    const rect = renderer.domElement.getBoundingClientRect();
                    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
                    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

                    raycaster.setFromCamera(mouse, camera);
                    const sphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), GLOBE_RADIUS);
                    const hit = new THREE.Vector3();
                    if (!raycaster.ray.intersectSphere(sphere, hit)) return;

                    const { lat, lng } = cartesianToLatLng(hit);
                    const props = findCountry(lat, lng, geojson.features);
                    const name = props ? (props.name || props.ADMIN || props.NAME) : null;
                    const label = name
                        ? name
                        : (document.documentElement.lang === 'es' ? 'Océano / sin datos' : 'Ocean / no data');
                    showTooltip(container, event.clientX - rect.left, event.clientY - rect.top - 10, label);
                });
            })
            .catch(() => { /* si el GeoJSON no carga, el globo sigue funcionando sin detección de país */ });

        return { scene, camera, renderer, controls, world };
    }

    window.DigitalAgencyGlobe = { init: initGlobe };
})();
