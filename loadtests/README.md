# 队列接口压测

安装独立压测依赖：

```bash
python -m pip install -r requirements-loadtest.txt
```

先启动 API、Redis 和 Worker，再执行无界面压测：

```bash
BUG_AGENT_LOADTEST_API_KEY=<raw-api-key> \
locust -f loadtests/locustfile.py \
  --headless --host http://127.0.0.1:8000 \
  --users 10 --spawn-rate 2 --run-time 5m \
  --csv run/loadtest/bug-agent
```

重点观察：

- `POST /v1/jobs` 的 p95 与失败率；
- 队列深度和任务等待时间；
- Worker CPU、内存与模型加载开销；
- LLM 超时、JSON fallback 和 RAG 检索耗时；
- 任务完成、超时、取消及待复核状态比例。

压测数据必须使用合成日志，不得把生产工单放入脚本或 CSV。
