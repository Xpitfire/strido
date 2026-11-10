<script setup lang="ts">
// Interactive 3D model of the verified Strido assembly (GLB exported from the CAD by
// `make viewer`): orbit, explode, step through the assembly manual, pick a part to identify it.
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { withBase } from 'vitepress';
import { dataUrl, defineMessages, useLocale, useLocalePath } from '../i18n';

const useMessages = defineMessages({
  en: {
    loading: 'Loading the 3D model…', loadFailed: 'The 3D model could not be loaded. Download it from the Downloads page instead.',
    complete: 'Complete robot', step: (index: number, title: string) => `Step ${index}: ${title}`, model: 'Interactive 3D model of Strido',
    inRobot: (count: number) => `${count}× in the robot`, assembledIn: 'assembled in', stepLink: (index: number) => `step ${index}`, printIt: 'print it →',
    kind: (kind: string) => kind,
    explode: 'Explode', stepSlider: 'Step', shells: 'shells', fasteners: 'fasteners', rotate: 'rotate',
    hint: 'Drag to orbit, scroll to zoom, click a part to identify it. The step slider replays the assembly manual: parts of the current step glow orange.',
  },
  de: {
    loading: '3D-Modell wird geladen…', loadFailed: 'Das 3D-Modell konnte nicht geladen werden. Sie können es stattdessen auf der Seite Downloads herunterladen.',
    complete: 'Kompletter Roboter', step: (index: number, title: string) => `Schritt ${index}: ${title}`, model: 'Interaktives 3D-Modell von Strido',
    inRobot: (count: number) => `${count}× im Roboter`, assembledIn: 'montiert in', stepLink: (index: number) => `Schritt ${index}`, printIt: 'drucken →',
    kind: (kind: string) => ({ printed: 'gedruckt', purchased: 'gekauft', fastener: 'Verbindungselement' })[kind] ?? kind,
    explode: 'Explosion', stepSlider: 'Schritt', shells: 'Schalen', fasteners: 'Verbindungselemente', rotate: 'drehen',
    hint: 'Ziehen zum Drehen, Scrollen zum Zoomen, ein Teil anklicken, um es zu bestimmen. Der Schrittregler spielt die Montageanleitung nach: Teile des aktuellen Schritts leuchten orange.',
  },
});
const t = useMessages();
const locale = useLocale();
const localePath = useLocalePath();

interface NodeInfo { part: string; title: string; kind: string; step: number; explode: [number, number, number]; shell: boolean }
interface StepInfo { index: number; title: string }
interface AssemblyInfo { steps: StepInfo[]; nodes: Record<string, NodeInfo>; counts: Record<string, number> }

const props = withDefaults(defineProps<{ height?: string; compact?: boolean }>(), { height: '560px', compact: false });

const host = ref<HTMLDivElement | null>(null);
const status = ref(t.value.loading);
const info = shallowRef<AssemblyInfo | null>(null);
const explode = ref(0);
const step = ref(0); // 0 = complete robot
const showShells = ref(true);
const showFasteners = ref(true);
const autoRotate = ref(!props.compact ? false : true);
const picked = ref<{ title: string; part: string; kind: string; step: number; count: number } | null>(null);
const stepCount = computed(() => info.value?.steps.length ?? 0);
const stepTitle = computed(() => (step.value === 0 ? t.value.complete : t.value.step(step.value, info.value?.steps[step.value - 1]?.title ?? '')));

let dispose: (() => void) | undefined;
let applyState: (() => void) | undefined;

onMounted(async () => {
  const THREE = await import('three');
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
  const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
  const { RoomEnvironment } = await import('three/examples/jsm/environments/RoomEnvironment.js');
  const element = host.value;
  if (!element) return;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(element.clientWidth, element.clientHeight);
  renderer.toneMapping = THREE.NeutralToneMapping;  // keeps the lime shells close to the printed colour
  element.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = environment;
  const camera = new THREE.PerspectiveCamera(35, element.clientWidth / element.clientHeight, 0.01, 20);
  camera.position.set(0.55, 0.38, 0.62);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.17, 0);
  controls.enableDamping = true;
  const grid = new THREE.GridHelper(1.2, 24, 0x888888, 0xcccccc);
  (grid.material as THREE.Material).opacity = 0.35;
  (grid.material as THREE.Material).transparent = true;
  scene.add(grid);

  const [gltf, meta] = await Promise.all([
    new GLTFLoader().loadAsync(withBase('/viewer/strido.glb'), (event) => {
      if (event.total) status.value = `${t.value.loading} ${Math.round((100 * event.loaded) / event.total)} %`;
    }),
    fetch(withBase(dataUrl('/viewer/assembly.json', locale.value))).then((response) => response.json() as Promise<AssemblyInfo>),
  ]).catch(() => {
    status.value = t.value.loadFailed;
    return [null, null] as const;
  });
  if (!gltf || !meta) return;
  info.value = meta;
  scene.add(gltf.scene);

  const highlight = new THREE.Color(0xff7a1a);
  const pickedTint = new THREE.Color(0x2f9bff);
  let pickedNode = '';
  const nodes: { object: THREE.Object3D; base: THREE.Vector3; meta: NodeInfo; meshes: THREE.Mesh[] }[] = [];
  gltf.scene.traverse((object) => {
    const nodeMeta = meta.nodes[object.name];
    if (!nodeMeta) return;
    const meshes: THREE.Mesh[] = [];
    object.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = (mesh.material as THREE.MeshStandardMaterial).clone();
        mesh.userData.node = object.name;
        meshes.push(mesh);
      }
    });
    nodes.push({ object, base: object.position.clone(), meta: nodeMeta, meshes });
  });

  applyState = () => {
    for (const node of nodes) {
      const [x, y, z] = node.meta.explode;
      node.object.position.set(node.base.x + x * explode.value, node.base.y + y * explode.value, node.base.z + z * explode.value);
      const hiddenByStep = step.value > 0 && node.meta.step > step.value;
      const hiddenByFilter = (!showShells.value && node.meta.shell) || (!showFasteners.value && node.meta.kind === 'fastener');
      node.object.visible = !hiddenByStep && !hiddenByFilter;
      const current = step.value > 0 && node.meta.step === step.value;
      const selected = node.object.name === pickedNode;
      for (const mesh of node.meshes) {
        const material = mesh.material as THREE.MeshStandardMaterial;
        if (material.emissiveMap) continue;  // the LCD face lights itself; never tint or darken it
        material.emissive = selected ? pickedTint : current ? highlight : new THREE.Color(0x000000);
        material.emissiveIntensity = selected ? 0.6 : current ? 0.55 : 0;
      }
    }
  };
  applyState();
  status.value = '';

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const PICK_MAX_TRAVEL_PX = 4; // a pointer that moved further was an orbit drag, not a click
  let pressed = { x: 0, y: 0 };
  const onPress = (event: PointerEvent) => {
    pressed = { x: event.clientX, y: event.clientY };
  };
  const onPick = (event: PointerEvent) => {
    if (Math.hypot(event.clientX - pressed.x, event.clientY - pressed.y) > PICK_MAX_TRAVEL_PX) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(gltf.scene.children, true).find((candidate) => candidate.object.visible);
    const name = hit?.object.userData.node as string | undefined;
    const nodeMeta = name ? meta.nodes[name] : undefined;
    pickedNode = nodeMeta ? name! : '';
    picked.value = nodeMeta ? { ...nodeMeta, count: meta.counts[nodeMeta.part] ?? 1 } : null;
    applyState?.();
  };
  renderer.domElement.addEventListener('pointerdown', onPress);
  renderer.domElement.addEventListener('pointerup', onPick);

  // Portrait canvases (phones) see less width at the same vertical field of view: back the camera
  // off by 1/aspect so the whole robot stays in view.
  const baseDistance = camera.position.distanceTo(controls.target);
  const fitCamera = () => {
    camera.aspect = element.clientWidth / element.clientHeight;
    camera.updateProjectionMatrix();
    const direction = camera.position.clone().sub(controls.target).normalize();
    camera.position.copy(controls.target).addScaledVector(direction, baseDistance / Math.min(1, camera.aspect));
    renderer.setSize(element.clientWidth, element.clientHeight);
  };
  fitCamera();
  const resize = new ResizeObserver(fitCamera);
  resize.observe(element);
  let frame = 0;
  const loop = () => {
    frame = requestAnimationFrame(loop);
    controls.autoRotate = autoRotate.value;
    controls.update();
    renderer.render(scene, camera);
  };
  loop();
  dispose = () => {
    cancelAnimationFrame(frame);
    resize.disconnect();
    renderer.domElement.removeEventListener('pointerdown', onPress);
    renderer.domElement.removeEventListener('pointerup', onPick);
    controls.dispose();
    environment.dispose();
    renderer.dispose();
  };
});

watch([explode, step, showShells, showFasteners], () => applyState?.());
onBeforeUnmount(() => dispose?.());
</script>

<template>
  <div class="yx-viewer" :class="{ 'yx-viewer--compact': compact }">
    <div ref="host" class="yx-viewer__canvas" :style="{ height }" role="img" :aria-label="t.model">
      <p v-if="status" class="yx-viewer__status">{{ status }}</p>
      <div v-if="picked" class="yx-viewer__picked">
        <strong>{{ picked.title }}</strong>
        <span>{{ t.kind(picked.kind) }} · <code>{{ picked.part }}</code> · {{ t.inRobot(picked.count) }}</span>
        <span v-if="picked.step">{{ t.assembledIn }} <a :href="localePath(`/docs/assembly/#step-${picked.step}`)">{{ t.stepLink(picked.step) }}</a></span>
        <a v-if="picked.kind === 'printed'" :href="localePath(`/docs/print-kit#part=${picked.part}`)">{{ t.printIt }}</a>
      </div>
    </div>
    <div v-if="!compact && info" class="yx-viewer__controls">
      <label>{{ t.explode }} <input v-model.number="explode" type="range" min="0" max="1" step="0.01" /></label>
      <label>{{ t.stepSlider }} <input v-model.number="step" type="range" min="0" :max="stepCount" step="1" :aria-valuetext="stepTitle" /></label>
      <span class="yx-viewer__step">{{ stepTitle }}</span>
      <label><input v-model="showShells" type="checkbox" /> {{ t.shells }}</label>
      <label><input v-model="showFasteners" type="checkbox" /> {{ t.fasteners }}</label>
      <label><input v-model="autoRotate" type="checkbox" /> {{ t.rotate }}</label>
    </div>
    <p v-if="!compact" class="yx-viewer__hint">{{ t.hint }}</p>
  </div>
</template>
