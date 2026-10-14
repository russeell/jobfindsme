import {lstatSync, readdirSync, realpathSync} from 'node:fs';
import path from 'node:path';

const skills = [
  'NOTICE.md',
  ...['resume-tailor', 'interview-prep', 'deep-research', 'web-retrieval'].map(id => `${id}/SKILL.md`),
  ...['resume-tailoring', 'tech-interview-handbook', 'deep-research', 'ai-job-search', 'agent-reach', 'interview-mentor', 'open-interviewer'].map(id => `licenses/${id}-MIT.txt`),
];
const runtimeDocuments = new Set([
  'docx/templates/default.docx',
  'pdfminer/cmap/README.txt',
  'setuptools/_vendor/jaraco/text/Lorem ipsum.txt',
  'lxml/isoschematron/resources/xsl/iso-schematron-xslt1/readme.txt',
]);
const database = /\.(?:db|sqlite|sqlite3)(?:[-.](?:wal|shm|journal|bak|backup|old))?$/i;
const browserStorage = /^(?:Cookies(?:-(?:wal|shm|journal))?|Local Storage|Session Storage|IndexedDB|Login Data(?:-(?:wal|shm|journal))?|Web Data(?:-(?:wal|shm|journal))?|Local State|Secure Preferences)$/i;
const credential = /^(?:credentials?|secrets?|api[-_]?keys?|tokens?|auth)(?:\.[^/]*)?$|^id_(?:rsa|ed25519)(?:\.pub)?$/i;
const document = /\.(?:pdf|docx?|odt|rtf|pages|md|txt)$/i;
const license = /^(?:licen[sc]e|copying|notice|copyrightnotice)(?:[.-].*)?$/i;

// This checks known private-file shapes, not arbitrary private text hidden in
// code/images. Source and public assets still need review before sharing.
export function packagePrivacyViolations(root, resourceDirectory) {
  if (!['Contents/Resources', 'resources'].includes(resourceDirectory)) throw new Error('Unknown package resource layout');
  const bundle = realpathSync(root);
  const modules = `${resourceDirectory}/app/node_modules/`;
  const runtime = `${resourceDirectory}/python/jobfindsme-api/_internal/`;
  const allowed = new Set([
    ...skills.map(file => `${resourceDirectory}/app/skills/${file}`),
    ...['PI_LICENSE.txt', 'PDFJS_LICENSE.txt', 'EDITOR_LICENSES.txt'].map(file => `${resourceDirectory}/third-party/${file}`),
    ...(resourceDirectory === 'resources' ? ['LICENSE-JobFindsMe.txt'] : []),
  ]);
  const violations = [];
  function allowedDocument(relative) {
    if (allowed.has(relative)) return true;
    const name = path.posix.basename(relative);
    if (relative.startsWith(modules)) return /\.(?:md|txt)$/i.test(name) && license.test(name);
    if (!relative.startsWith(runtime)) return false;
    const internal = relative.slice(runtime.length);
    return runtimeDocuments.has(internal)
      || /^[^/]+\.dist-info\/(?:entry_points|top_level)\.txt$/.test(internal)
      || /^[^/]+\.dist-info\/licenses\//.test(internal) && /\.(?:md|txt)$/i.test(name) && license.test(name);
  }
  function visit(directory) {
    for (const name of readdirSync(directory).sort()) {
      const file = path.join(directory, name);
      const relative = path.relative(bundle, file).split(path.sep).join('/');
      const stat = lstatSync(file);
      const dependencyCode = relative.startsWith(modules) && /\.(?:c?js|mjs|ts)$/.test(name);
      if (database.test(name) || browserStorage.test(name) || /^\.env(?:\.|$)/i.test(name)
        || !stat.isDirectory() && (credential.test(name) && !dependencyCode
          || document.test(name) && !allowedDocument(relative))) {
        violations.push(relative);
        continue;
      }
      if (stat.isSymbolicLink()) {
        try {
          const target = path.relative(bundle, realpathSync(file));
          if (target === '..' || target.startsWith(`..${path.sep}`) || path.isAbsolute(target)) violations.push(`${relative} (outside bundle)`);
        } catch {
          violations.push(`${relative} (unresolvable link)`);
        }
        // Internal targets are checked at their physical location, not followed
        // recursively. Never read or print a link target outside the package.
      } else if (stat.isDirectory()) visit(file);
    }
  }
  visit(bundle);
  return violations;
}

export function assertPackagePrivacy(root, resourceDirectory) {
  const violations = packagePrivacyViolations(root, resourceDirectory);
  if (violations.length) throw new Error(`Package contains private or unexpected data: ${violations.join(', ')}`);
}
