# Wi-Fi 模块说明

## 常见掉线范围

Wi-Fi 掉线问题常见于自动信道切换、DFS 检测、弱信号、驱动重启和 station table 清理。

## 自动信道切换

如果日志中同时出现 `channel switch` 和 `station disconnected`，优先检查信道切换完成事件前是否清理了 station table。

正常流程应先通知客户端或进入信道切换阶段，等待驱动完成切换，再更新 station 状态。过早清理 station table 会使客户端在重关联窗口前被强制断开。

## DFS 与驱动重启

DFS 雷达事件可能触发强制换信道，应区分法规要求导致的正常切换与状态机缺陷。若出现 firmware crash、driver reset 或接口重新创建，需要沿驱动恢复链路排查，而不是只看 hostapd 的断开日志。

## 弱信号与现场排查

单个客户端掉线应结合 RSSI、重试率和漫游日志；同一时间大量客户端掉线更可能与信道切换、驱动重启或 AP 状态变化有关。

回归测试需要覆盖自动信道优化、DFS、2.4G/5G 双频、Mesh 回程和多客户端持续连接。
