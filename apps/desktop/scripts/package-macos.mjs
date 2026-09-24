import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = path.resolve(desktopRoot, "../..");
const electronApp = path.join(desktopRoot, "node_modules/electron/dist/Electron.app");
const pythonRuntime = path.join(desktopRoot, "runtime/python/jobfindsme-api");
const previewBuild=process.env.JFM_PACKAGE_PREVIEW === "1";
const buildInfo=JSON.parse(readFileSync(path.join(desktopRoot,"build-info.json"),"utf8"));
// Keep user-facing preview releases on the existing D55 profile. QA can opt
// into a separate profile; build labels must never silently reset sessions.
const previewUserData=process.env.JFM_PACKAGE_PREVIEW_USER_DATA || "jobfindsme-preview-D55-reading-column";
if(!/^jobfindsme-preview-[a-zA-Z0-9_-]+$/.test(previewUserData))throw Error("invalid preview user data profile");
const displayName=previewBuild?`JobFindsMe ${buildInfo.label} 测试版`:(process.env.JFM_PACKAGE_DISPLAY_NAME || "JobFindsMe");
const output = process.env.JFM_PACKAGE_OUTPUT || path.join(desktopRoot, "release/mac-unpacked/JobFindsMe.app");

if (!existsSync(electronApp)) throw new Error("Electron.app is missing; run npm install first");
if (!existsSync(pythonRuntime)) {
  throw new Error(
    "Bundled Python runtime is missing at apps/desktop/runtime/python/jobfindsme-api; " +
    "build scripts/jobfindsme_api.spec with PyInstaller first",
  );
}

rmSync(output, { recursive: true, force: true });
mkdirSync(path.dirname(output), { recursive: true });
// Electron.framework uses relative symlinks for its current version, resources,
// helpers and libraries.  fs.cp resolves those links to absolute source paths by
// default, which makes the resulting app depend on node_modules and also causes
// Electron subprocesses to look for ICU data in the wrong bundle.  Preserve the
// link text so the directory package is self-contained and relocatable.
cpSync(electronApp, output, { recursive: true, verbatimSymlinks: true });
const contents = path.join(output, "Contents");
renameSync(
  path.join(contents, "MacOS/Electron"),
  path.join(contents, "MacOS/JobFindsMe"),
);
const resources = path.join(contents, "Resources");
rmSync(path.join(resources, "default_app.asar"), { force: true });
cpSync(path.join(desktopRoot, "public/brand.icns"), path.join(resources, "jobfindsme.icns"));
const appRoot = path.join(resources, "app");
mkdirSync(appRoot, { recursive: true });
cpSync(path.join(desktopRoot, "dist"), path.join(appRoot, "dist"), { recursive: true });
cpSync(path.join(desktopRoot, "dist-electron"), path.join(appRoot, "dist-electron"), { recursive: true });
writeFileSync(
  path.join(appRoot, "package.json"),
  JSON.stringify({ name: "jobfindsme-desktop", version: "0.1.0", jobfindsmePreview:previewBuild, build:buildInfo.label, previewUserData, main: "dist-electron/main/index.js" }),
);
mkdirSync(path.join(resources, "python"), { recursive: true });
cpSync(pythonRuntime, path.join(resources, "python/jobfindsme-api"), { recursive:true, verbatimSymlinks:true });
execFileSync("/bin/chmod", ["755", path.join(resources, "python/jobfindsme-api/jobfindsme-api")]);

const plist = path.join(contents, "Info.plist");
for (const [key, value] of [
  ["CFBundleIconFile", "jobfindsme.icns"],
  ["CFBundleDisplayName", displayName],
  ["CFBundleName", displayName],
  ["CFBundleExecutable", "JobFindsMe"],
  ["CFBundleIdentifier", previewBuild?"com.jobfindsme.desktop.preview.d19":"com.jobfindsme.desktop"],
]) {
  execFileSync("/usr/bin/plutil", ["-replace", key, "-string", value, plist]);
}

console.log(output);
