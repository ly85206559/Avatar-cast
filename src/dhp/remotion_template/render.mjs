import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const [configFile, publicDir, outputLocation] = process.argv.slice(2);
const directory = path.dirname(fileURLToPath(import.meta.url));
const inputProps = JSON.parse(fs.readFileSync(configFile, 'utf8'));
const serveUrl = await bundle({entryPoint: path.join(directory, 'index.tsx'), publicDir,
  outDir: path.join(path.dirname(configFile), 'remotion-bundle')});
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null;
const composition = await selectComposition({serveUrl, id: 'ProductDemo', inputProps, browserExecutable});
await renderMedia({serveUrl, composition, inputProps, outputLocation, browserExecutable,
  codec: 'h264', muted: true, concurrency: 2, crf: 20, overwrite: false});
