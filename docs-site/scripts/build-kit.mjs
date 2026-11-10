// The downloadable build kit: every printable part (oriented STLs, 3MF plates), the slicer profile,
// the print list, the catalogue & assembly book PDF and the BOM, in one ZIP for the documentation
// site (public/downloads/). Deterministic: fixed entry order and timestamps, so an unchanged kit is
// byte-identical and `writeChanged` leaves it alone. Plain ZIP (deflate), no dependency.
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { crc32, deflateRawSync } from 'node:zlib';

export const KIT_NAME = 'strido-build-kit.zip';
const KIT_ROOT = 'strido-build-kit';
// Repository path -> path inside the kit; a directory entry takes every file below it.
const KIT_CONTENTS = [
  ['hardware/print/stl', 'stl'],
  ['hardware/print/plates', 'plates'],
  ['hardware/print/print_list.md', 'print_list.md'],
  ['hardware/print/prusaslicer.ini', 'prusaslicer.ini'],
  ['docs/catalog/strido-catalog.pdf', 'strido-catalog.pdf'],
  ['docs/bom/README.md', 'bom/README.md'],
  ['docs/bom/shopping_list.md', 'bom/shopping_list.md'],
  ['docs/bom/bom.csv', 'bom/bom.csv'],
];
const README = `Strido build kit
==================

stl/                  every printed part, oriented for printing (one file per part type)
plates/               ready 220 x 220 mm build plates (3MF), one colour per plate
prusaslicer.ini       the verified print profile (PrusaSlicer: File > Import > Import Config)
print_list.md         quantity, colour, supports and notes per part
strido-catalog.pdf   catalogue & assembly book: parts, hardware at 1:1, shopping plan, all steps
bom/                  bill of materials and the shopping plan

Every part and plate slices without errors or stability warnings with prusaslicer.ini
(docs/verification/printability.md on the documentation site).
`;
// 2026-10-31 00:00 as MS-DOS date/time (fixed for reproducible archives)
const DOS_TIME = 0;
const DOS_DATE = ((2026 - 1980) << 9) | (10 << 5) | 31;

/** [path inside the kit, absolute file] for a repository file, or for every file of a directory. */
async function entriesOf(repositoryRoot, source, target) {
  const absolute = path.join(repositoryRoot, source);
  const entries = await readdir(absolute, { withFileTypes: true }).catch((error) => {
    if (error.code === 'ENOTDIR') return null;
    throw error;
  });
  if (entries === null) return [[target, absolute]];
  const names = entries.filter((entry) => entry.isFile() && !entry.name.startsWith('.')).map((entry) => entry.name).sort();
  return names.map((name) => [`${target}/${name}`, path.join(absolute, name)]);
}

function localHeader(name, crc, compressed, size) {
  const header = Buffer.alloc(30);
  header.writeUInt32LE(0x04034b50, 0);
  header.writeUInt16LE(20, 4); // version needed: 2.0 (deflate)
  header.writeUInt16LE(0x0800, 6); // UTF-8 names
  header.writeUInt16LE(8, 8); // deflate
  header.writeUInt16LE(DOS_TIME, 10);
  header.writeUInt16LE(DOS_DATE, 12);
  header.writeUInt32LE(crc, 14);
  header.writeUInt32LE(compressed, 18);
  header.writeUInt32LE(size, 22);
  header.writeUInt16LE(name.length, 26);
  return Buffer.concat([header, name]);
}

function centralHeader(name, crc, compressed, size, offset) {
  const header = Buffer.alloc(46);
  header.writeUInt32LE(0x02014b50, 0);
  header.writeUInt16LE(20, 4); // made by
  header.writeUInt16LE(20, 6); // needed
  header.writeUInt16LE(0x0800, 8);
  header.writeUInt16LE(8, 10);
  header.writeUInt16LE(DOS_TIME, 12);
  header.writeUInt16LE(DOS_DATE, 14);
  header.writeUInt32LE(crc, 16);
  header.writeUInt32LE(compressed, 20);
  header.writeUInt32LE(size, 24);
  header.writeUInt16LE(name.length, 28);
  header.writeUInt32LE(offset, 42);
  return Buffer.concat([header, name]);
}

/** The kit as a ZIP buffer, and the number of files in it. */
export async function buildKit(repositoryRoot) {
  const files = [[`${KIT_ROOT}/README.txt`, Buffer.from(README, 'utf8')]];
  for (const [source, target] of KIT_CONTENTS) {
    for (const [inside, file] of await entriesOf(repositoryRoot, source, target)) {
      files.push([`${KIT_ROOT}/${inside}`, await readFile(file)]);
    }
  }
  return zipArchive(files);
}

/** A deterministic plain ZIP (deflate, fixed timestamps) of [entry name, Buffer] pairs, in that order. */
export function zipArchive(files) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const [entryName, data] of files) {
    const name = Buffer.from(entryName, 'utf8');
    const compressed = deflateRawSync(data, { level: 9 });
    const crc = crc32(data);
    const local = Buffer.concat([localHeader(name, crc, compressed.length, data.length), compressed]);
    centrals.push(centralHeader(name, crc, compressed.length, data.length, offset));
    locals.push(local);
    offset += local.length;
  }
  const central = Buffer.concat(centrals);
  if (offset + central.length > 0xffffffff || files.length > 0xffff) throw new Error('archive exceeds plain ZIP limits');
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  return { zip: Buffer.concat([...locals, central, end]), files: files.length };
}
