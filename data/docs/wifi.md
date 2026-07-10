# Wi-Fi 模块说明

Wi-Fi 掉线问题常见于自动信道切换、DFS 检测、弱信号、驱动重启和 station table 清理。

如果日志中同时出现 `channel switch` 和 `station disconnected`，优先检查信道切换完成事件前是否清理了 station table。
