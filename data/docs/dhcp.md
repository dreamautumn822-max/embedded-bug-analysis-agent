# DHCP 模块说明

## 启动依赖与时序

DHCP server 依赖 LAN bridge 处于 ready 状态。`netifd reload` 会触发 LAN bridge 重建，bridge 未 ready 时启动 DHCP server 可能出现 `lease allocation failed`。

正常时序应为 bridge 创建、端口进入 forwarding、LAN 接口 ready，最后启动或重启 DHCP server。升级脚本和 netifd reload hook 不应绕过 bridge 状态检查。

## 地址池与配置迁移

DHCP 地址池由起始地址、结束地址、租期和 LAN 子网共同决定。固件升级后需要确认旧配置已映射到 `lan.dhcp.pool_start` 和 `lan.dhcp.pool_end`，否则可能出现地址池为空或 `no free leases`。

配置迁移问题通常持续存在于每次启动；bridge 时序问题更容易表现为升级或 reload 后偶发失败，可通过日志时间线区分。

## 现场排查

排查 DHCP 获取失败时，需要检查：

- 是否出现 `dhcpd: lease allocation failed`
- 是否在同一时间窗口出现 `netifd: interface lan reload`
- 是否出现 `kernel: br-lan port state changed`
- DHCP 地址池是否为空
- bridge ready 事件是否早于 DHCP server restart

## 修复与回归

修复时应在 `br-lan` 进入 forwarding/ready 后启动 DHCP server，并为状态检查增加有限重试和超时。回归测试需要覆盖冷启动、热升级、LAN reload、地址池迁移和多客户端并发获取地址。
