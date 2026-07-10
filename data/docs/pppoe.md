# PPPoE 模块说明

PPPoE 拨号失败常见原因包括账号认证失败、WAN link flap、认证重试定时器未启动、MTU 配置错误。

出现 `pppoe: auth failed` 时，需要结合 WAN 口 link 状态和 retry timer 日志判断是账号问题还是状态机问题。
