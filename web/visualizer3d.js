/**
 * AETHERIS-ADR 3D WebGL Orbital Visualizer (Three.js)
 * High-performance rendering of Earth, 3D orbits, Point Nemo corridor, and debris fields.
 */

class DebrisVisualizer3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.width = this.container.clientWidth;
    this.height = this.container.clientHeight;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;

    this.earthMesh = null;
    this.atmosphereMesh = null;
    this.debrisPointCloud = null;
    this.debrisPositions = [];
    this.debrisMetadata = [];

    this.selectedOrbitLine = null;
    this.selectedSatelliteMesh = null;
    this.pointNemoGroup = null;
    this.hpopTrajectoryLine = null;

    this.showOrbits = true;
    this.showPointNemo = true;
    this.trackingSelected = false;
    this.selectedNoradId = 27386; // Default ENVISAT

    this.initScene();
    this.createEarth();
    this.createPointNemoCorridor();
    this.animate();

    window.addEventListener('resize', () => this.onWindowResize());
  }

  initScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x02050a);

    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 1000);
    this.camera.position.set(0, 8, 16);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.container.appendChild(this.renderer.domElement);

    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.minDistance = 4.0;
      this.controls.maxDistance = 60.0;
    }

    // Lighting: Sun Directional Light + Ambient
    const ambientLight = new THREE.AmbientLight(0x334466, 0.8);
    this.scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffffff, 1.4);
    sunLight.position.set(20, 10, 15);
    this.scene.add(sunLight);

    // Deep Space Starfield
    this.createStarfield();
  }

  createStarfield() {
    const starCount = 1500;
    const starGeo = new THREE.BufferGeometry();
    const starCoords = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 250 + Math.random() * 50;

      starCoords[i] = r * Math.sin(phi) * Math.cos(theta);
      starCoords[i + 1] = r * Math.sin(phi) * Math.sin(theta);
      starCoords[i + 2] = r * Math.cos(phi);
    }

    starGeo.setAttribute('position', new THREE.BufferAttribute(starCoords, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0x99bbff,
      size: 0.8,
      transparent: true,
      opacity: 0.65
    });

    const starPoints = new THREE.Points(starGeo, starMat);
    this.scene.add(starPoints);
  }

  createEarth() {
    // Earth Radius scaled: 1 Earth Radius = 3.0 units in 3D scene
    this.EARTH_SCALE = 3.0; // 6378 km -> 3.0 units
    this.KM_TO_SCENE = this.EARTH_SCALE / 6378.137;

    const earthGeo = new THREE.SphereGeometry(this.EARTH_SCALE, 64, 64);
    
    // Canvas-generated procedural high-tech Earth texture
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = 1024;
    const ctx = canvas.getContext('2d');

    // Deep ocean gradient
    const oceanGrad = ctx.createLinearGradient(0, 0, 0, 1024);
    oceanGrad.addColorStop(0, '#0a1d37');
    oceanGrad.addColorStop(0.5, '#061325');
    oceanGrad.addColorStop(1, '#0a1d37');
    ctx.fillStyle = oceanGrad;
    ctx.fillRect(0, 0, 2048, 1024);

    // Continental grid lines & glowing coastlines
    ctx.strokeStyle = 'rgba(0, 210, 255, 0.35)';
    ctx.lineWidth = 1.5;
    for (let x = 0; x < 2048; x += 128) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 1024);
      ctx.stroke();
    }
    for (let y = 0; y < 1024; y += 128) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(2048, y);
      ctx.stroke();
    }

    // Equator highlight
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.7)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, 512);
    ctx.lineTo(2048, 512);
    ctx.stroke();

    const earthTex = new THREE.CanvasTexture(canvas);
    const earthMat = new THREE.MeshStandardMaterial({
      map: earthTex,
      roughness: 0.6,
      metalness: 0.2,
      wireframe: false
    });

    this.earthMesh = new THREE.Mesh(earthGeo, earthMat);
    this.scene.add(this.earthMesh);

    // Atmospheric Glow
    const atmosGeo = new THREE.SphereGeometry(this.EARTH_SCALE * 1.025, 48, 48);
    const atmosMat = new THREE.MeshBasicMaterial({
      color: 0x00c8ff,
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide
    });
    this.atmosphereMesh = new THREE.Mesh(atmosGeo, atmosMat);
    this.scene.add(this.atmosphereMesh);
  }

  createPointNemoCorridor() {
    this.pointNemoGroup = new THREE.Group();

    // Convert Point Nemo Lat/Lon (-48.87° Lat, -123.39° Lon) to 3D Sphere coordinates
    const latRad = THREE.MathUtils.degToRad(-48.876667);
    const lonRad = THREE.MathUtils.degToRad(-123.393333);
    const r = this.EARTH_SCALE * 1.002;

    const x = r * Math.cos(latRad) * Math.cos(lonRad);
    const y = r * Math.sin(latRad);
    const z = -r * Math.cos(latRad) * Math.sin(lonRad);

    // Pulsing Point Nemo Beacon
    const beaconGeo = new THREE.SphereGeometry(0.08, 16, 16);
    const beaconMat = new THREE.MeshBasicMaterial({ color: 0x00e676 });
    const beacon = new THREE.Mesh(beaconGeo, beaconMat);
    beacon.position.set(x, y, z);
    this.pointNemoGroup.add(beacon);

    // SPOUA 3-Sigma Dispersion Ellipse Ring
    const ellipseGeo = new THREE.RingGeometry(0.25, 0.28, 32);
    const ellipseMat = new THREE.MeshBasicMaterial({
      color: 0x00e676,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7
    });
    const ellipseMesh = new THREE.Mesh(ellipseGeo, ellipseMat);
    ellipseMesh.position.set(x, y, z);
    ellipseMesh.lookAt(0, 0, 0);
    this.pointNemoGroup.add(ellipseMesh);

    this.scene.add(this.pointNemoGroup);
  }

  updateDebrisCatalog(objects) {
    if (this.debrisPointCloud) {
      this.scene.remove(this.debrisPointCloud);
      this.debrisPointCloud.geometry.dispose();
      this.debrisPointCloud.material.dispose();
    }

    const count = objects.length;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    this.debrisMetadata = objects;

    objects.forEach((obj, idx) => {
      // Calculate instantaneous position from semi-major axis, inclination, raan
      const altKm = obj.perigee_alt_km || 750.0;
      const rKm = 6378.137 + altKm;
      const rScene = rKm * this.KM_TO_SCENE;

      const incRad = THREE.MathUtils.degToRad(obj.inclination_deg || 70.0);
      const raanRad = THREE.MathUtils.degToRad(obj.raan_deg || 0.0);
      const nuRad = THREE.MathUtils.degToRad(obj.true_anomaly_deg || Math.random() * 360.0);

      // Perifocal to ECI coordinates
      const xOrb = rScene * Math.cos(nuRad);
      const yOrb = rScene * Math.sin(nuRad);

      const x = (Math.cos(raanRad) * xOrb - Math.sin(raanRad) * yOrb * Math.cos(incRad));
      const z = -(Math.sin(raanRad) * xOrb + Math.cos(raanRad) * yOrb * Math.cos(incRad));
      const y = yOrb * Math.sin(incRad);

      positions[idx * 3] = x;
      positions[idx * 3 + 1] = y;
      positions[idx * 3 + 2] = z;

      // Color coding by criticality score
      const score = obj.criticality_score || 0;
      if (score >= 60.0) {
        // Red critical
        colors[idx * 3] = 1.0;
        colors[idx * 3 + 1] = 0.09;
        colors[idx * 3 + 2] = 0.27;
      } else if (score >= 30.0) {
        // Amber moderate
        colors[idx * 3] = 1.0;
        colors[idx * 3 + 1] = 0.67;
        colors[idx * 3 + 2] = 0.0;
      } else {
        // Cyan nominal
        colors[idx * 3] = 0.0;
        colors[idx * 3 + 1] = 0.89;
        colors[idx * 3 + 2] = 1.0;
      }
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.14,
      vertexColors: true,
      transparent: true,
      opacity: 0.95
    });

    this.debrisPointCloud = new THREE.Points(geometry, material);
    this.scene.add(this.debrisPointCloud);

    // If an object is selected, render its orbit
    this.selectObject(this.selectedNoradId);
  }

  selectObject(noradId) {
    this.selectedNoradId = noradId;
    const obj = this.debrisMetadata.find(o => o.norad_id === noradId);
    if (!obj) return;

    // Clear previous orbit line
    if (this.selectedOrbitLine) {
      this.scene.remove(this.selectedOrbitLine);
      this.selectedOrbitLine.geometry.dispose();
      this.selectedOrbitLine.material.dispose();
      this.selectedOrbitLine = null;
    }
    if (this.selectedSatelliteMesh) {
      this.scene.remove(this.selectedSatelliteMesh);
      this.selectedSatelliteMesh.geometry.dispose();
      this.selectedSatelliteMesh.material.dispose();
      this.selectedSatelliteMesh = null;
    }

    // Generate Elliptical Keplerian Orbit Line (120 segments)
    const smaKm = obj.semi_major_axis_km || (6378.137 + 768.0);
    const ecc = obj.eccentricity || 0.001;
    const incRad = THREE.MathUtils.degToRad(obj.inclination_deg || 98.54);
    const raanRad = THREE.MathUtils.degToRad(obj.raan_deg || 45.0);
    const argPRad = THREE.MathUtils.degToRad(obj.arg_of_perigee_deg || 90.0);

    const orbitPoints = [];
    const segments = 128;

    for (let i = 0; i <= segments; i++) {
      const nu = (i / segments) * 2.0 * Math.PI;
      const rKm = (smaKm * (1.0 - ecc * ecc)) / (1.0 + ecc * Math.cos(nu));
      const rScene = rKm * this.KM_TO_SCENE;

      // Position in orbital plane (PQW) rotated by arg_p
      const u = argPRad + nu;
      const xOrb = rScene * Math.cos(u);
      const yOrb = rScene * Math.sin(u);

      const x = (Math.cos(raanRad) * xOrb - Math.sin(raanRad) * yOrb * Math.cos(incRad));
      const z = -(Math.sin(raanRad) * xOrb + Math.cos(raanRad) * yOrb * Math.cos(incRad));
      const y = yOrb * Math.sin(incRad);

      orbitPoints.push(new THREE.Vector3(x, y, z));
    }

    const orbitGeo = new THREE.BufferGeometry().setFromPoints(orbitPoints);
    const orbitMat = new THREE.LineBasicMaterial({
      color: 0x00e5ff,
      linewidth: 2,
      transparent: true,
      opacity: 0.85
    });

    this.selectedOrbitLine = new THREE.Line(orbitGeo, orbitMat);
    if (this.showOrbits) {
      this.scene.add(this.selectedOrbitLine);
    }

    // Satellite marker at true anomaly
    const satPos = orbitPoints[Math.floor(segments * 0.33)];
    const satGeo = new THREE.OctahedronGeometry(0.12);
    const satMat = new THREE.MeshBasicMaterial({ color: 0xff1744 });
    this.selectedSatelliteMesh = new THREE.Mesh(satGeo, satMat);
    this.selectedSatelliteMesh.position.copy(satPos);
    this.scene.add(this.selectedSatelliteMesh);

    if (this.trackingSelected) {
      this.camera.lookAt(satPos);
    }
  }

  toggleOrbits() {
    this.showOrbits = !this.showOrbits;
    if (this.selectedOrbitLine) {
      this.selectedOrbitLine.visible = this.showOrbits;
    }
    return this.showOrbits;
  }

  togglePointNemo() {
    this.showPointNemo = !this.showPointNemo;
    if (this.pointNemoGroup) {
      this.pointNemoGroup.visible = this.showPointNemo;
    }
    return this.showPointNemo;
  }

  resetCamera() {
    this.camera.position.set(0, 8, 16);
    this.camera.lookAt(0, 0, 0);
    if (this.controls) {
      this.controls.target.set(0, 0, 0);
    }
  }

  onWindowResize() {
    this.width = this.container.clientWidth;
    this.height = this.container.clientHeight;
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.width, this.height);
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    // Earth slow axial rotation
    if (this.earthMesh) {
      this.earthMesh.rotation.y += 0.0003;
    }

    if (this.selectedSatelliteMesh) {
      this.selectedSatelliteMesh.rotation.x += 0.02;
      this.selectedSatelliteMesh.rotation.y += 0.03;
    }

    if (this.controls) {
      this.controls.update();
    }

    this.renderer.render(this.scene, this.camera);
  }
}
