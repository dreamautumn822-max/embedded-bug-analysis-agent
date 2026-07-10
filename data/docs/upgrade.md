# 固件升级与配置迁移说明

固件升级后出现网络异常时，需要检查配置迁移规则。旧版本配置 key 如果没有映射到新 schema，可能导致 DHCP 地址池、WAN 账号、Wi-Fi 参数丢失。

DHCP 地址池迁移需要确认 `lan.dhcp.pool_start` 和 `lan.dhcp.pool_end` 已从旧配置正确映射到新配置。
