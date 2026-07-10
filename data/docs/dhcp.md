# DHCP 模块说明

DHCP server 依赖 LAN bridge 处于 ready 状态。`netifd reload` 会触发 LAN bridge 重建，bridge 未 ready 时启动 DHCP server 可能出现 `lease allocation failed`。

排查 DHCP 获取失败时，需要检查：

- 是否出现 `dhcpd: lease allocation failed`
- 是否在同一时间窗口出现 `netifd: interface lan reload`
- 是否出现 `kernel: br-lan port state changed`
- DHCP 地址池是否为空
- bridge ready 事件是否早于 DHCP server restart
