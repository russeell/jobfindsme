# D03/D08 独立 AI 复核包

日期：2026-09-18。用途：供调度者决定是否对隐私、迁移、密钥和外部协议边界发起一次独立只读审查。不包含真实简历或密钥，不代表已要求审查。

## 请重点核对

1. 确认事实与当前版本是否保持原子性，部分迁移/并发确认是否可使旧当前版本丢失。
2. 脱敏规则是否仅影响临时分析副本，以及正则过度脱敏/漏脱敏的边界。
3. renderer/preload/main/回环 API 的路径与密钥传递是否维持最小权限，密钥是否可通过数据库、响应、日志或错误回显泄露。
4. OpenAI 兼容、Anthropic、Gemini 请求/响应和用量映射，以及超时/取消后状态是否误报。
5. 0014/0015 在旧数据库上是否只增量建表/索引并保留原 profile/source/fact 数据。

## 精确文件哈希（SHA-256）

```text
49adcfd7d7f7124f048c3f72f25e28206b59cf801c1ee470f6e736a7cc0d8777  src/jobfindsme/migrations/0014_resume_versions.sql
6d7babe1de3f0200001ff03d07da4b2f41b0d3a2a2243df9c9aa15375fddbe42  src/jobfindsme/migrations/0015_model_connections.sql
36a90e5276b23f547e2404b52ea8ac0a77426b03dd7550ce32fe096ca3c8d6d5  src/jobfindsme/profiles/models.py
03738d0c9a134b96a622543de1cdecfbf91900f01a07fc849d638374ff4eee42  src/jobfindsme/profiles/service.py
5a73536c5d3ddf4401d6f76e6805bf0395d7b83a65b57b89fcc81b84c3816243  src/jobfindsme/privacy.py
1a99a60cc0a0dc94374822356cf890ce7c8fe7f48fc6fea6de6aaababcd52bf8  src/jobfindsme/models/__init__.py
8265a9e99c276a8f0ef1bcaa0224d4f23b688f74d2963f326f6b9ee67434ad1b  src/jobfindsme/models/gateway.py
7635a0674846af52a27998ed98de1befd1231c14ce746161f2f31cd533af4cec  src/jobfindsme/desktop_api/app.py
d3f6ae63395ad9c0aed62c7895bccc3948f30a2f9ee962f49c4de057ce2ef76d  apps/desktop/main/api-client.ts
369e1e9dfd1fe7ed56ebc3d903bec12d1e1e6bd54eadbf18bd1ea842fee30cd3  apps/desktop/main/index.ts
92188c4af8184ecf02902acff589970cb409feae8aa69e98b8c15f1868a52f80  apps/desktop/main/secure-secret-store.ts
cdc2d5a81ad9c0ff73b36071af09893db22b04f0208e796b4c3b6fddcddd7e53  apps/desktop/preload/index.ts
bf4128d1ce7d81bb780bdf2b5c3981ab51dddd0a3a16fd2bb861c705b93e73d9  apps/desktop/shared/contracts.ts
35372224b15c1cdceb8334b68e60edb6870bd534dfabea04773d0fd2e67aa2b0  apps/desktop/renderer/src/App.tsx
6cde739e60a78e3dc4cd1d0fe38376a2edb2cdc77052e5a743e356fb2f8c6c45  apps/desktop/renderer/src/styles.css
c54e8949d10fa8d4717f1c4dcd909dfbcc5021d343ead3f44fb11e29795ebafb  tests/profiles/test_resume_versions.py
01e1ffbf7e5e46389d74fb9414e5d1bab453a0d6c9b7b99e353aed87666e812d  tests/profiles/test_resume_migration.py
e78ee2e225b1aaea1cef93a595f0a688273615ccdc19dc7730f4ef5ff8bfbe48  tests/security/test_analysis_copy.py
652bdedc36a5ab31411f2f2b73d5a9a481867842d3329661cabf13cc32b532bc  tests/models/test_gateway.py
d704f9989da18c7590091a90700f33963dd569c1a889657d6101c3ea6688646e  tests/desktop_api/test_app.py
```

注：以上哈希覆盖阶段 B 生成/修改的实现文件，其中多数文件仍处于未跟踪或未提交状态。审查时应直接读取共享工作区，不只使用 `git diff`。

## 调度补充
基线 commit：d720f37f57444b2b03c640d9c12032992e09b15c
目标为上述文件哈希定位的当前未提交内容。tracked diff 见 D03-D08-review-tracked.diff；新增文件直接读取哈希清单。仅允许写 D03-D08-review.md，其余只读；不调用真实模型、不访问用户账号/简历/密钥、不改状态或提交发布。
