import {execFileSync} from 'node:child_process';
import {readFileSync as readManifest} from 'node:fs';
import { existsSync, lstatSync, readdirSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appRoot = process.env.JFM_PACKAGE_OUTPUT || path.join(desktopRoot, "release/mac-unpacked/JobFindsMe.app");
if (!existsSync(appRoot)) throw new Error("packaged app does not exist");

const forbidden = [
  /\.db(?:-wal|-shm)?$/i,
  /\.(?:pdf|docx|md|txt)$/i,
  /(^|\/)(?:Cookies|Local Storage|Session Storage)(\/|$)/i,
  /(^|\/)\.env(?:\.|$)/i,
  /(^|\/)(?:credentials?|secrets?|api[-_]?keys?)(?:\.[^/]*)?$/i,
];
const skillFiles=new Set(["NOTICE.md","licenses/resume-tailoring-MIT.txt","licenses/tech-interview-handbook-MIT.txt","licenses/deep-research-MIT.txt","licenses/ai-job-search-MIT.txt","licenses/agent-reach-MIT.txt","licenses/interview-mentor-MIT.txt","licenses/open-interviewer-MIT.txt",... ["resume-tailor","interview-prep","deep-research","web-retrieval"].map(id=>`${id}/SKILL.md`)].map(file=>`Contents/Resources/app/skills/${file}`));
const violations = [];
const visit = (directory) => {
  for (const entry of readdirSync(directory)) {
    const absolute = path.join(directory, entry);
    const relative = path.relative(appRoot, absolute);
    const dependencyCode=relative.startsWith("Contents/Resources/app/node_modules/");
    if (forbidden.some((rule, index) => !(index === 1 && (relative.startsWith("Contents/Resources/python/jobfindsme-api/_internal/") || (relative === "Contents/Resources/third-party/PI_LICENSE.txt" || relative === "Contents/Resources/third-party/PDFJS_LICENSE.txt" || relative === "Contents/Resources/third-party/EDITOR_LICENSES.txt") || skillFiles.has(relative) || dependencyCode)) && !(dependencyCode && (index === 2 || index === 4)) && rule.test(relative))) violations.push(relative);
    const stat = lstatSync(absolute);
    if (stat.isSymbolicLink()) {
      const target = realpathSync(absolute);
      const targetRelative = path.relative(appRoot, target);
      if (targetRelative.startsWith("..") || path.isAbsolute(targetRelative)) {
        violations.push(`${relative} -> ${target}`);
      }
      continue;
    }
    if (stat.isDirectory()) visit(absolute);
  }
};
visit(appRoot);
for(const file of skillFiles)if(!existsSync(path.join(appRoot,file)))violations.push(`missing ${file}`);
if (violations.length) {
  throw new Error(`packaged app contains private or development data: ${violations.join(", ")}`);
}
for (const required of [
  "Contents/MacOS/JobFindsMe",
  "Contents/Resources/jobfindsme.icns",
  "Contents/Resources/app/dist/index.html",
  "Contents/Resources/app/dist-electron/main/index.js",
  "Contents/Resources/app/dist-electron/main/research/pi-research-agent.mjs",
  "Contents/Resources/app/node_modules/@earendil-works/pi-agent-core/dist/index.js",
  "Contents/Resources/third-party/PI_LICENSE.txt",
  "Contents/Resources/third-party/PDFJS_LICENSE.txt",
  "Contents/Resources/app/dist-electron/main/browser/source-browser.js",
  "Contents/Resources/app/dist-electron/main/backend/python-service.js",
  "Contents/Resources/app/dist-electron/shared/source-browser-policy.js",
  "Contents/Resources/python/jobfindsme-api/jobfindsme-api",
  "Contents/Frameworks/Electron Framework.framework/Resources/icudtl.dat",
  "Contents/Frameworks/Electron Framework.framework/Resources/resources.pak",
]) {
  if (!existsSync(path.join(appRoot, required))) throw new Error(`missing ${required}`);
}
for (const stale of ["source-browser", "source-browser-policy", "api-client", "python-service", "boss-page"]) {
  if (existsSync(path.join(appRoot, `Contents/Resources/app/dist-electron/main/${stale}.js`))) {
    throw new Error(`obsolete pre-D47 module in package: ${stale}`);
  }
}
console.log("package audit passed");

const manifest=JSON.parse(readManifest(path.join(appRoot,'Contents/Resources/app/package.json'),'utf8'));
const expected=packageProvenance(path.resolve('.'),path.join(appRoot,'Contents/Resources/python/jobfindsme-api'));
if(JSON.stringify(manifest.dependencyLocks)!==JSON.stringify(expected.dependencyLocks)||JSON.stringify(manifest.sourceInputs)!==JSON.stringify(expected.sourceInputs))throw Error('Package dependency/source fingerprints do not match the build');
if(!/^[a-f0-9]{40}$/.test(manifest.sourceCommit)||manifest.sourceCommit!==execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim())throw Error('Package source commit does not match checkout');
if(!manifest.jobfindsmePreview&&(!manifest.build.includes('+local.')&&(manifest.build!==`v${manifest.version}`||manifest.releaseTag!==manifest.build||manifest.qa)))throw Error('Invalid release version or QA configuration');
const runtime=JSON.parse(execFileSync(path.join(appRoot,'Contents/Resources/python/jobfindsme-api/jobfindsme-api'),['--check-runtime'],{encoding:'utf8',timeout:30000}));
if(runtime.curl_http!=='ok'||runtime.ca_bundle!=='ok')throw Error('Packaged HTTP runtime failed');
console.log('Frozen HTTP request and CA bundle passed');
import {packageProvenance} from './build-provenance.mjs';
