// Product information for the shop and print kit (docs/bom/products.json from hardware/products.yaml,
// written by `make bom`), the assembly steps each part appears in (docs/catalog/parts.json) and the
// strength checks and tightening torques per part (docs/verification/data/strength.json).
import { ref } from 'vue';
import { dataUrl, type Locale } from '../i18n';

export interface ProductInfo {
  summary: string;
  description: string;
  features?: string[];
  specs?: Record<string, string>;
  role?: string;
  learn?: string[];
}
interface CatalogEntry { id: string; steps: number[] }

/** One strength check of strido_verify.strength (actual and allowable in `unit`, S = safety factor). */
export interface StrengthCheck { id: string; parts: string[]; what: string; formula: string; actual: number; allowable: number; unit: string; safety: number; status: string; note: string }
/** Pull-out force and recommended tightening torque of a thread-forming screw in a printed part. */
export interface ThreadTorque { joint: string; part: string; thread: string; engaged_mm: number; pull_out_n: number; strip_torque_nm: number; recommended_torque_nm: number }
export interface PartStrength { checks: StrengthCheck[]; torques: ThreadTorque[] }

export const productInfo = ref<{ purchased: Record<string, ProductInfo>; printed: Record<string, ProductInfo> } | null>(null);
const stepsByPart = ref<Record<string, number[]>>({});
const strength = ref<{ checks: StrengthCheck[]; thread_torques: ThreadTorque[] } | null>(null);

// Titles of the Learn wiki pages that product information links to (docs/wiki/<slug>.md, German: de/docs/wiki/<slug>.md).
export const WIKI_TITLES: Record<Locale, Record<string, string>> = {
  en: {
    'hardware/servos': 'Servos',
    'hardware/batteries': 'LiPo batteries',
    'hardware/power': 'Power electronics',
    'hardware/microcontrollers': 'Microcontrollers and the Pi',
    'hardware/buses': 'Buses: I²C, UART, SPI, PWM',
    'hardware/sensors': 'Sensors',
    'hardware/mechanics': 'Mechanics and bearings',
    'software/linux-on-the-pi': 'Linux on the Pi',
    'software/docker': 'Docker',
    'software/ros2': 'ROS 2',
    'software/firmware': 'Firmware',
    'software/kinematics-and-gaits': 'Kinematics and gaits',
    'software/simulation-and-rl': 'Simulation and RL',
    'software/cad-as-code': 'CAD as code',
    'making/3d-printing': '3D printing',
    'making/fasteners': 'Fasteners',
    'making/strength': 'Strength, torque and failure',
    'making/tools-and-workshop': 'Tools and workshop',
    'making/cable-management': 'Cable management and the wiring harness',
    'making/safety': 'Safety',
  },
  de: {
    'hardware/servos': 'Servos',
    'hardware/batteries': 'LiPo-Akkus',
    'hardware/power': 'Leistungselektronik',
    'hardware/microcontrollers': 'Mikrocontroller und der Pi',
    'hardware/buses': 'Busse: I²C, UART, SPI, PWM',
    'hardware/sensors': 'Sensoren',
    'hardware/mechanics': 'Mechanik und Lager',
    'software/linux-on-the-pi': 'Linux auf dem Pi',
    'software/docker': 'Docker',
    'software/ros2': 'ROS 2',
    'software/firmware': 'Firmware',
    'software/kinematics-and-gaits': 'Kinematik und Gaits',
    'software/simulation-and-rl': 'Simulation und RL',
    'software/cad-as-code': 'CAD als Code',
    'making/3d-printing': '3D-Druck',
    'making/fasteners': 'Verbindungselemente',
    'making/strength': 'Festigkeit, Drehmoment und Versagen',
    'making/tools-and-workshop': 'Werkzeug und Werkstatt',
    'making/cable-management': 'Kabelmanagement und Kabelbaum',
    'making/safety': 'Sicherheit',
  },
};

let loading: Promise<void> | null = null;
let loadedLocale: Locale | null = null;

/** Product information is optional decoration: a missing file, network error or bad JSON leaves it empty. */
async function optionalJson(url: string): Promise<any> {
  try {
    const response = await fetch(url);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

/** Loads product information and part steps of the site language (again when it changes; browser only); never rejects. */
export function loadProducts(locale: Locale): Promise<void> {
  if (loading && loadedLocale === locale) return loading;
  loadedLocale = locale;
  loading = (async () => {
    const [products, catalog, strengthReport] = await Promise.all([
      optionalJson(dataUrl('/bom/products.json', locale)), optionalJson(dataUrl('/catalog/parts.json', locale)), optionalJson('/data/strength.json'),
    ]);
    if (loadedLocale !== locale) return; // the language changed while these answers were on their way
    productInfo.value = products;
    strength.value = strengthReport;
    stepsByPart.value = Object.fromEntries(((catalog?.parts ?? []) as CatalogEntry[]).map((part) => [part.id, part.steps]));
  })();
  return loading;
}

/** Assembly steps (sorted, unique) in which any of the CAD parts is fitted. */
export function stepsOf(partIds: string[]): number[] {
  return [...new Set(partIds.flatMap((id) => stepsByPart.value[id] ?? []))].sort((a, b) => a - b);
}

/** Strength checks involving the part (printed part id or BOM line id) and its pilot-hole torques. */
export function strengthOf(partId: string): PartStrength {
  return {
    checks: (strength.value?.checks ?? []).filter((item) => item.parts.includes(partId)),
    torques: (strength.value?.thread_torques ?? []).filter((item) => item.part === partId),
  };
}
