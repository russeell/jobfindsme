import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {assertPackagePrivacy, packagePrivacyViolations} from '../scripts/package-privacy.mjs';

function fixture(run) {
  const temporary = mkdtempSync(path.join(os.tmpdir(), 'jfm-package-privacy-'));
  const root = path.join(temporary, 'bundle');
  mkdirSync(root);
  const write = relative => {
    const file = path.join(root, relative);
    mkdirSync(path.dirname(file), {recursive: true});
    writeFileSync(file, 'Fictional test data only.');
  };
  try { run({root, temporary, write}); }
  finally { rmSync(temporary, {recursive: true, force: true}); }
}

for (const resources of ['Contents/Resources', 'resources']) {
  test(`${resources}: refuse private files even inside dependency/runtime directories`, () => fixture(({root, write}) => {
    const files = [
      `${resources}/app/resume.pdf`,
      `${resources}/app/resume.docx`,
      `${resources}/app/dist/notes.md`,
      `${resources}/app/node_modules/example/personal.txt`,
      `${resources}/app/node_modules/example/credentials.json`,
      `${resources}/app/node_modules/example/Cookies-journal`,
      `${resources}/app/node_modules/example/.env.local`,
      `${resources}/python/jobfindsme-api/_internal/resume.docx`,
      `${resources}/python/jobfindsme-api/_internal/data.sqlite3`,
      `${resources}/python/jobfindsme-api/_internal/data.sqlite-journal`,
      `${resources}/python/jobfindsme-api/_internal/data.db-wal`,
      `${resources}/python/jobfindsme-api/_internal/data.db-shm`,
      `${resources}/python/jobfindsme-api/_internal/data.db-journal`,
      `${resources}/python/jobfindsme-api/_internal/data.sqlite3.backup`,
      `${resources}/python/jobfindsme-api/_internal/data.db.bak`,
    ];
    files.forEach(write);
    mkdirSync(path.join(root, resources, 'app/IndexedDB'));
    assert.deepEqual(packagePrivacyViolations(root, resources).sort(), [...files, `${resources}/app/IndexedDB`].sort());
    assert.throws(() => assertPackagePrivacy(root, resources), /private or unexpected data/);
  }));

  test(`${resources}: retain required code, licenses, skills and named runtime resources`, () => fixture(({root, write}) => {
    const runtime = `${resources}/python/jobfindsme-api/_internal`;
    [
      `${resources}/app/dist/index.html`,
      `${resources}/app/dist/brand.png`,
      `${resources}/app/dist-electron/main/index.js`,
      `${resources}/app/node_modules/example/LICENSE.md`,
      `${resources}/app/node_modules/tslib/CopyrightNotice.txt`,
      `${resources}/app/node_modules/example/sessions/index.js`,
      `${resources}/app/node_modules/example/resources/secrets.js`,
      `${resources}/app/skills/resume-tailor/SKILL.md`,
      `${resources}/app/skills/NOTICE.md`,
      `${resources}/app/skills/licenses/resume-tailoring-MIT.txt`,
      `${resources}/third-party/PI_LICENSE.txt`,
      `${resources}/third-party/PDFJS_LICENSE.txt`,
      `${resources}/third-party/EDITOR_LICENSES.txt`,
      `${runtime}/docx/templates/default.docx`,
      `${runtime}/pdfminer/cmap/README.txt`,
      `${runtime}/setuptools/_vendor/jaraco/text/Lorem ipsum.txt`,
      `${runtime}/lxml/isoschematron/resources/xsl/iso-schematron-xslt1/readme.txt`,
      `${runtime}/example-1.0.dist-info/top_level.txt`,
      `${runtime}/example-1.0.dist-info/entry_points.txt`,
      `${runtime}/example-1.0.dist-info/licenses/LICENSE.txt`,
      ...(resources === 'resources' ? ['LICENSE-JobFindsMe.txt'] : []),
    ].forEach(write);
    assertPackagePrivacy(root, resources);
  }));

  test(`${resources}: links cannot pull in files outside the bundle or expose target paths`, () => fixture(({root, temporary, write}) => {
    write(`${resources}/app/dist/index.html`);
    const outside = path.join(temporary, 'outside');
    mkdirSync(outside);
    writeFileSync(path.join(outside, 'fictional.txt'), 'Fictional test only.');
    const directory = path.join(root, resources, 'app');
    const type = process.platform === 'win32' ? 'junction' : 'dir';
    symlinkSync(path.join(directory, 'dist'), path.join(directory, 'dist-alias'), type);
    assertPackagePrivacy(root, resources);
    symlinkSync(outside, path.join(directory, 'external'), type);
    assert.deepEqual(packagePrivacyViolations(root, resources), [`${resources}/app/external (outside bundle)`]);
    assert.throws(() => assertPackagePrivacy(root, resources), error => !error.message.includes(outside));
  }));
}
