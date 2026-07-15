# 真实故障 Case 接入与评估规范

## 1. 目标与边界

本规范用于把真实网通设备故障工单转换为可重复评估的 Agent case。目标是评估系统在真实分布上的分类、检索、根因、证据引用和人工复核路由，不是把生产工单原文复制到 Git 仓库。

仓库中的 `data/bugs/eval_cases.json` 全部标记为 `case_origin=synthetic`，只能作为可复现功能基线。真实 case 应保存在公司批准的受控位置，通过 `--cases` 参数临时加载；禁止提交设备序列号、客户账号、真实 MAC、内部 IP、公网 IP、邮箱、主机名、工单号和未脱敏堆栈。

## 2. 数据流

```text
故障工单/复盘报告
  -> 生成不可逆 source_ticket_hash
  -> 自动替换敏感字段
  -> 人工逐行脱敏复核
  -> 两名标注人独立标注
  -> 分歧裁决
  -> 按工单哈希、设备族和时间切分
  -> Pydantic 契约与敏感信息扫描
  -> 离线评估和版本对比
```

`source_ticket_hash` 使用环境变量 `BUG_AGENT_CASE_HASH_SALT` 和原始工单稳定 ID 计算 HMAC-SHA256，并只保存 `sha256:<64 hex>`。带盐摘要用于去重和防止同一事件跨 train/dev/test 泄漏，不能保存原工单号，也不能把盐提交到 Git。

## 3. 脱敏规则

推荐替换形式：

| 原始信息 | 替换值 |
| --- | --- |
| MAC 地址 | `<MAC_1>`、`<MAC_2>` |
| IPv4/IPv6 地址 | `<LAN_IP_1>`、`<WAN_IP_1>` |
| 设备序列号 | `<DEVICE_SN>` |
| 客户账号 | `<ACCOUNT_ID>` |
| 内部主机名/ACS 域名 | `<HOST_1>` |
| 工单号 | 不进入正文，只保留不可逆哈希 |

替换值在单个 case 内必须保持一致，以保留“同一地址是否变化”等诊断关系。不要简单删除整行，否则会破坏时序、模块名、错误码和根因证据。

校验器会对 `production_anonymized` case 扫描真实 MAC、邮箱和非文档网段 IPv4。扫描通过不等于脱敏完成，因此 `sanitization_actions` 必须包含 `manual_review`。

## 4. 标注字段

每条 case 必须包含：

- `expected_bug_type`：预期问题分类。
- `expected_root_cause_keywords`：必须在根因标题或描述中出现的最小语义锚点，不应直接复制整段答案。
- `expected_evidence_terms`：期望在最终证据链命中的日志、Bug、文档或代码锚点。
- `expected_review_required`：该输入是否应进入人工复核。
- `label_status`：生产 case 必须为 `adjudicated`。
- `annotator_count`：生产 case 至少为 2。

两名标注人应先独立判断，再由模块 owner 裁决分歧。不能让标注人只参考 Agent 当前输出，否则会把现有模型偏差写进金标准。

## 5. 数据集切分

1. 先按 `source_ticket_hash` 去重，同一故障事件只能出现在一个 split。
2. 同一批量事故、同一固件分支派生工单应整体分组后再切分。
3. 测试集优先采用时间外切分，即使用较新的已关闭工单。
4. 用于 Prompt、规则或知识库调试的 case 标为 `train` 或 `dev`，不能继续计入最终 `test` 指标。
5. 评估报告必须分别列出 synthetic 与 production_anonymized 结果，不能混成一个准确率。

## 6. 接入步骤

原始导入格式参考：

```bash
cp docs/evaluation/real-case-import.example.json /secure/path/raw_cases.json
```

原始文件必须包含至少两条 `annotations`、独立 `adjudication` 和 `manual_review_confirmed=true`。配置随机盐后执行脱敏导入：

```bash
source .venv/bin/activate
export BUG_AGENT_CASE_HASH_SALT='<at-least-16-random-characters>'
python scripts/import_real_cases.py \
  --input /secure/path/raw_cases.json \
  --output run/private_eval/real_eval_cases.json
```

`run/` 已被 Git 忽略。也可以把输出写到仓库之外的公司受控目录；脚本会拒绝写入仓库内除 `run/private_eval/` 以外的位置。导入完成后运行严格校验：

```bash
python scripts/validate_eval_dataset.py \
  --cases run/private_eval/real_eval_cases.json \
  --require-production
```

校验通过后执行规则链基线和真实 LLM 评估：

```bash
python scripts/evaluate.py \
  --cases run/private_eval/real_eval_cases.json \
  --disable-llm

python scripts/evaluate.py \
  --cases run/private_eval/real_eval_cases.json \
  --load-env \
  --repeat 3
```

检索标注需要另行把相关 `chunk_id` 写入检索评估集，再运行 `scripts/evaluate_retrieval.py`。知识库更新后，应检查旧 chunk ID 是否因切分版本变化而失效。

## 7. 上线门槛建议

至少分别观察：

- 分类准确率和各 bug_type 的混淆情况。
- 根因命中率及误导性高置信度错误。
- `Recall@K`、MRR、nDCG 与证据来源覆盖。
- 引用有效性，确保根因只引用实际返回的 evidence ID。
- 复核路由的召回率，重点控制“本应复核却自动通过”的风险。
- LLM 多次运行稳定性、P95 延迟、fallback 比例和单 case 成本。

生产发布应设置当前版本基线和最低阈值，在 CI 或发布流水线中比较新旧版本。阈值必须由真实 case 数量、风险等级和业务容忍度决定，不能沿用本仓库 5 条合成样例的 `1.00` 指标。
