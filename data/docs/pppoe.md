# PPPoE 模块说明

## 常见故障范围

PPPoE 拨号失败常见原因包括账号认证失败、WAN link flap、认证重试定时器未启动、MTU 配置错误。

## 认证失败

出现 `pppoe: auth failed` 时，需要结合 WAN 口 link 状态和 retry timer 日志判断是账号问题还是状态机问题。

如果 WAN link 一直稳定且服务端明确返回认证拒绝，应优先检查账号、密码和运营商侧状态。如果认证失败发生在 link flap 恢复之后，并伴随 retry timer stopped，则更可能是状态机恢复问题。

## Link flap 与重试定时器

WAN 从 down 恢复到 up 后，PPPoE 状态机应重新进入 discovery/authentication 流程并启动 retry timer。若 link up 事件只恢复接口状态而没有重新创建定时器，第一次认证失败后将不再拨号。

## MTU 与现场排查

PPPoE 常见 MTU 为 1492，配置过大可能导致部分业务访问异常，但通常不会解释“完全不再重拨”。现场排查应同时采集 WAN link、PADI/PADO、认证结果、retry timer 和状态机迁移日志。

修复后需要覆盖线路闪断、认证失败后重试、账号恢复和连续多次 link flap。
