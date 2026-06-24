import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const IsometricViewer = ({ segments, fittings }) => {
  const mountRef = useRef(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  // Observe container size changes
  useEffect(() => {
    if (!mountRef.current) return;
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        setContainerSize({ width, height });
      }
    });
    resizeObserver.observe(mountRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // Three.js setup
  useEffect(() => {
    if (!mountRef.current || containerSize.width === 0 || containerSize.height === 0) {
      return;
    }

    // Guard: ensure segments is an array
    if (!segments || !Array.isArray(segments) || segments.length === 0) {
      // Show a message
      mountRef.current.innerHTML = '<div style="text-align:center;padding:2rem;color:#666;">No geometry to display</div>';
      return;
    }

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);

    const camera = new THREE.PerspectiveCamera(45, containerSize.width / containerSize.height, 0.1, 1000);
    camera.position.set(20, 15, 25);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(containerSize.width, containerSize.height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 0, 0);

    // Lights
    const ambientLight = new THREE.AmbientLight(0x404040);
    scene.add(ambientLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 1);
    dirLight.position.set(1, 2, 1);
    scene.add(dirLight);

    // Group for all objects
    const group = new THREE.Group();

    // --- Draw pipe lines (blue) ---
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x0000ff });
    const geometry = new THREE.BufferGeometry();
    const vertices = [];
    segments.forEach(seg => {
      vertices.push(seg[0], seg[1], seg[2]);
      vertices.push(seg[3], seg[4], seg[5]);
    });
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    const lines = new THREE.LineSegments(geometry, lineMaterial);
    group.add(lines);

    // --- Draw fittings ---
    if (fittings && Array.isArray(fittings) && fittings.length > 0) {
      const flangeMaterial = new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0x330000 });
      const elbowMaterial = new THREE.MeshStandardMaterial({ color: 0xff8800, emissive: 0x331100 });
      fittings.forEach(f => {
        const pos = f.pos;
        const type = f.type;
        const sphereGeom = new THREE.SphereGeometry(0.4, 16, 16);
        const mat = type === 'flange' ? flangeMaterial : elbowMaterial;
        const sphere = new THREE.Mesh(sphereGeom, mat);
        sphere.position.set(pos[0], pos[1], pos[2]);
        group.add(sphere);
      });
    }

    scene.add(group);

    // Grid helper
    const gridHelper = new THREE.GridHelper(20, 10, 0xcccccc, 0xcccccc);
    scene.add(gridHelper);

    // Auto-center and zoom
    const box = new THREE.Box3().setFromObject(group);
    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    if (maxDim > 0) {
      controls.target.copy(center);
      const distance = maxDim * 1.8;
      camera.position.set(center.x + distance * 0.8, center.y + distance * 0.6, center.z + distance);
    }
    controls.update();

    // Animation loop
    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    // Handle resize when container size changes
    function handleResize() {
      const width = mountRef.current.clientWidth;
      const height = mountRef.current.clientHeight;
      if (width > 0 && height > 0) {
        renderer.setSize(width, height);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      }
    }

    // Use ResizeObserver inside the effect to handle resize
    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(mountRef.current);

    // Cleanup
    return () => {
      resizeObserver.disconnect();
      renderer.dispose();
      if (mountRef.current) {
        while (mountRef.current.firstChild) {
          mountRef.current.removeChild(mountRef.current.firstChild);
        }
      }
    };
  }, [segments, fittings, containerSize]);

  return <div ref={mountRef} style={{ width: '100%', height: '600px' }} />;
};

export default IsometricViewer;