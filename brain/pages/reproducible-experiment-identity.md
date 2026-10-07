---
id: reproducible-experiment-identity
title: "可复现实验身份规则深化"
category: decision
status: active
tags: [architecture, identity, calibration]
created: "2026-10-03T23:05:54"
updated: "2026-10-08T07:44:31"
---

<!-- compiled_truth -->
## 决定与理由

配置语义与 report-to-measurement 身份核验集中在纯领域 module，静态配置从准备 workload 的 seam 投影。共享语义不等于合并公开 wire class，也不等于所有消费者使用同一种匹配政策；兼容性和可追溯性优先于形式上的统一。

## 长期约束

- 保留 AnalysisInferenceConfig 与 CalibrationInferenceConfig 的独立类型、公开位置和版本化 JSON 契约；共同字段声明不得成为合并两种 wire model 的理由。
- 身份仍限于既有十字段。active_sequences 记录派生后的有效值，不新增 active_sequences_override、active_sequences_source 或 safety_margin_ratio 等持久化身份字段。
- 保留 unavailable / mismatch / partial / verified 与 unknown 判定；缺失信息不猜测、不补默认身份，也不规范化字符串或指纹。诊断顺序不得在集中逻辑时漂移。
- report 比较可按共同已知指纹核验；fit 仍要求更严格的 exact scope。比较已 verified 不能替代拟合范围相同的检查。
- scope key、candidate/review/runner 的 ID 与 digest 各有用途，不为代码统一而改其 payload、算法或顺序；保留样本顺序和敏感信息边界。
- 内部 seam 为有类型、无 I/O 的 in-process interface；不引入插件、缓存或后端依赖，domain 不反向导入 calibration/engines。

## 关联

静态接入见 [[static-target-analysis-deepening]]；产物与安装验证见 [[calibration-installation-contract]]；保留 [[phase-10b-local-runner-boundary]] 的执行边界。


## Timeline

- time: 2026-10-03T23:05:54
  kind: decision
  summary: "Created this page: 可复现实验身份规则深化"
  source: "用户在①合入main后请求②的文件化实施提示词"
  affects: [reproducible-experiment-identity]

- time: 2026-10-03T23:05:54
  kind: decision
  summary: "记录②的实施交接及行为兼容、投影复用、④协调约束"
  source: "本轮②实施提示词"
  affects: [reproducible-experiment-identity]

- time: 2026-10-08T07:44:31
  kind: decision
  summary: "移除已结束的实施安排，保留长期决策、理由与兼容/验证边界"
  source: "用户确认按Brain保留与归档建议整理"
  affects: [reproducible-experiment-identity]
