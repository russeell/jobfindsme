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
const violations = [];
const visit = (directory) => {
  for (const entry of readdirSync(directory)) {
    const absolute = path.join(directory, entry);
    const relative = path.relative(appRoot, absolute);
    if (forbidden.some((rule, index) => !(index === 1 && relative.startsWith("Contents/Resources/python/jobfindsme-api/_internal/")) && rule.test(relative))) violations.push(relative);
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
if (violations.length) {
  throw new Error(`packaged app contains private or development data: ${violations.join(", ")}`);
}
for (const required of [
  "Contents/MacOS/JobFindsMe",
  "Contents/Resources/jobfindsme.icns",
  "Contents/Resources/app/dist/index.html",
  "Contents/Resources/app/dist-electron/main/index.js",
  "Contents/Resources/python/jobfindsme-api/jobfindsme-api",
  "Contents/Frameworks/Electron Framework.framework/Resources/icudtl.dat",
  "Contents/Frameworks/Electron Framework.framework/Resources/resources.pak",
]) {
  if (!existsSync(path.join(appRoot, required))) throw new Error(`missing ${required}`);
}
console.log("package audit passed");
