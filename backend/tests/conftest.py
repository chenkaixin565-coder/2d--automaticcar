"""
pytest 全局配置模块。

模块功能：在导入 app 之前固定测试环境变量，让用例不依赖开发机的
本地配置（例如是否装了 scikit-learn、是否配置了操作密钥）。
作者：智能巡检机器人二维仿真系统 V2.3.0 开发组
日期：2026-10-30
版本：V2.3.0
"""

import os
import tempfile

# 日志写到临时目录，避免测试污染项目目录。
os.environ.setdefault("LOG_FILE", os.path.join(tempfile.mkdtemp(), "pytest.log"))
# 异常检测固定用规则基线：ML 有 500 tick 冷启动，会让"tick 后应告警"类用例变得不确定。
os.environ.setdefault("ANOMALY_STRATEGY", "rule")
# 测试环境不连本地大模型，Agent 用例只验证规则解析与执行链路。
os.environ.setdefault("AGENT_LLM_ENABLED", "false")
# 默认开放演示模式（各安全用例会自行 monkeypatch 配置）。
os.environ.setdefault("OPERATOR_KEY", "")
os.environ.setdefault("READONLY_MODE", "false")
