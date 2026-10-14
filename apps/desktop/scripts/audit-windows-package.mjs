import {execFileSync} from 'node:child_process';
import {readFileSync as readManifest} from 'node:fs';
import {existsSync} from 'node:fs';
import path from 'node:path';
import {packageProvenance} from './build-provenance.mjs';
import {assertPackagePrivacy} from './package-privacy.mjs';
const root=path.resolve('release/windows/JobFindsMe');
assertPackagePrivacy(root, 'resources');
for(const required of ['JobFindsMe.exe','resources/python/jobfindsme-api/jobfindsme-api.exe','resources/app/dist/index.html','resources/app/dist-electron/main/index.js','resources/app/node_modules/@earendil-works/pi-agent-core/dist/index.js','resources/third-party/PI_LICENSE.txt','resources/third-party/PDFJS_LICENSE.txt','resources/third-party/EDITOR_LICENSES.txt',...['resume-tailor','interview-prep','deep-research','web-retrieval'].map(id=>`resources/app/skills/${id}/SKILL.md`),'resources/app/skills/NOTICE.md',...['resume-tailoring','tech-interview-handbook','deep-research','agent-reach','ai-job-search','interview-mentor','open-interviewer'].map(id=>`resources/app/skills/licenses/${id}-MIT.txt`)]){
 if(!existsSync(path.join(root,required)))throw Error(`Missing ${required}`);
}
const manifest=JSON.parse(readManifest(path.join(root,'resources/app/package.json'),'utf8'));
const expected=packageProvenance(path.resolve('.'),path.join(root,'resources/python/jobfindsme-api'));
if(JSON.stringify(manifest.dependencyLocks)!==JSON.stringify(expected.dependencyLocks)||JSON.stringify(manifest.sourceInputs)!==JSON.stringify(expected.sourceInputs))throw Error('Package dependency/source fingerprints do not match the build');
if(!/^[a-f0-9]{40}$/.test(manifest.sourceCommit)||manifest.sourceCommit!==execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim())throw Error('Package source commit does not match checkout');
if(!manifest.jobfindsmePreview&&(!manifest.build.includes('+local.')&&(manifest.build!==`v${manifest.version}`||manifest.releaseTag!==manifest.build||manifest.qa)))throw Error('Invalid release version or QA configuration');
const runtime=JSON.parse(execFileSync(path.join(root,'resources/python/jobfindsme-api/jobfindsme-api.exe'),['--check-runtime'],{encoding:'utf8',timeout:30000}));
if(runtime.curl_http!=='ok'||runtime.ca_bundle!=='ok')throw Error('Packaged HTTP runtime failed');
console.log('Frozen HTTP request and CA bundle passed');
console.log('Windows package audit passed');
