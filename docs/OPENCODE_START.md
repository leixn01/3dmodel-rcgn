# 在 SolidWorks 电脑上使用 OpenCode

## 准备与 skill 加载

1. 按 README 拉取仓库并解压测试模型，在仓库根目录启动 `opencode`。
2. 项目规则位于 `AGENTS.md`；三个 skill 位于 `.opencode/skills/<名称>/SKILL.md`，由 OpenCode 默认发现，相关任务按需加载。
3. 不需要自定义 skill 路径、复制到全局目录，也不需要把所有 SKILL.md 加到 `instructions`。显式使用时直接告诉 Agent“加载 cad-intake”等。

若未发现 skill，先确认工作目录、文件名大小写、frontmatter 的 name/description 和客户端 skill 权限；检查同名全局 skill 或额外配置是否覆盖项目定义。

## 现在就能做：离线模型体检

告诉 OpenCode：

```text
加载 cad-intake，检查仓库内的升降机测试模型，报告输入内容和文本扫描限制。
```

这会使用已有的 `python -m cadkin inspect ...`，不连接 SolidWorks。需要 Python 3.10+，在仓库根目录运行无需安装本项目。

## 接下来开发：连接与 MCP

在 SolidWorks 中手动打开 `outputs/three_servo_lift/temp/3X Lift Assembly.STEP`，保留窗口。将下面的任务交给 OpenCode：

```text
读取 AGENTS.md，加载 solidworks-connect，按 docs/DEVELOPMENT_PLAN.md 完成第一步。
这台 Windows 电脑已经安装 SolidWorks，我已打开测试 STEP。
先实现并实测只读连接和活动文档读取，再用本地 stdio MCP 暴露同一组工具。
按本机 OpenCode 版本配置 MCP，并从 Agent 发起实际调用验证。
工具、COM 适配器和 MCP 入口分开，skill 里只保留流程。
不要启动空实例来伪装成功，不要修改或关闭当前模型。记录未完成和未实测项。
```

第一步通过后，另起任务：“加载 assembly-inventory，完成开发计划第二步的组件树工具，导出 JSON 并与实际模型树核对。”

## MCP 配置版本

**当前没有 MCP 实现和启用配置**；先完成服务，再根据 `opencode --version` 和对应官方文档添加配置，避免启动不存在的程序。

| 客户端配置格式 | 本地服务位置 | 开关 |
| --- | --- | --- |
| V1 | `mcp.<服务名>` | `enabled: true` |
| V2 原生 | `mcp.servers.<服务名>` | `disabled: false`，也可省略 |

两者的本地服务都使用 `type: "local"` 和 `command` 参数数组。启动命令应指向装好依赖的 Windows Python 解释器，并验证工作目录。V2 官方说明兼容受支持的 V1 配置，不要求仅为加载 skill 升级客户端；不要把 V2 专有配置交给 V1 使用。

只加载 skill 不会建立 SolidWorks 连接。必须实现并启动 MCP、注册工具，再检查 `opencode mcp list` 和 Agent 实际可用工具。

代码与说明进入 Git；结果、截图和模型工作副本留在 `outputs/`。测试模型的实际导入类型、连接和组件读取仍需在目标电脑验收。

参考：[Skills](https://opencode.ai/docs/skills/)、[MCP](https://opencode.ai/docs/mcp-servers/)、[版本迁移](https://opencode.ai/docs/migrate-v1/)。
