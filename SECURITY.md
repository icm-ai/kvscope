# Security Policy

## Supported versions

KVScope is under active development. Security fixes are currently targeted at
the latest `main` branch and the latest published release.

## Reporting a vulnerability

请不要在公开 issue 中披露可能影响用户安全的细节。请通过 GitHub
Security Advisories 联系维护者；如果仓库尚未启用该功能，请先创建一个不
包含敏感细节的 issue，请求私下沟通渠道。

请尽可能提供：

- 受影响的版本或 commit；
- 可复现步骤或最小示例；
- 潜在影响；
- 建议的缓解方式。

KVScope 的设计要求包括不执行远程模型代码、不默认加载模型权重，以及不
上传用户机器信息。任何偏离这些约束的修改都需要在 review 中明确说明。
