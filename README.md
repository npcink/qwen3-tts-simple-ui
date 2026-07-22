# qwen3-tts-simple-ui

一个面向本地 Qwen3-TTS 服务的简化中文 UI，提供预设声音、授权声线克隆和可选的日语 ASR 辅助流程。

这是非官方社区项目，与 Qwen、阿里巴巴或阿里云没有隶属或背书关系。仓库只包含 UI、队列和本地服务适配代码，不包含模型权重、声音样本、SoX、CUDA 运行时或 Qwen3-TTS 本身。

当前版本为 0.1.0-alpha.1，以公开源码 Alpha 的方式提供，适合在受控本地环境中验证、学习和继续开发。Windows 11 与 NVIDIA GeForce RTX 4090 的一组目标配置已完成真机端到端验收，但本项目仍不是生产级或公网服务。

## 项目状态

- 源码状态：公开 Alpha
- Windows/GPU 运行兼容性：Windows 11 / NVIDIA GeForce RTX 4090 目标配置已验证
- 公网服务与生产可用性：不支持
- 模型与第三方运行时：不随本仓库分发

## 架构边界

默认端口：

- 18001：本 UI
- 18000：外部 CustomVoice Gradio 后端
- 18002：外部 Base 声线克隆后端
- 18003：可选的本地日语 ASR 服务

三个后端默认都应仅监听 127.0.0.1。UI 默认同样只监听回环地址；如果显式开放到局域网，必须由反向代理或其他访问层提供身份认证。

## 安装

推荐 Python 3.12。

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -e .
    Copy-Item .env.example .env

需要本地 ASR 时：

    python -m pip install -e ".[asr]"

本项目不会自动下载 Qwen3-TTS 模型。请单独准备兼容的 CustomVoice 和 Base 服务，并通过 .env 配置端点。

## 启动

启动 UI：

    .\scripts\windows\run-simple-ui.ps1 -Python .\.venv\Scripts\python.exe

启动可选 ASR：

    .\scripts\windows\run-asr.ps1 -Python .\.venv\Scripts\python.exe

仓库还提供通用的 Qwen 后端启动模板：

- scripts/windows/run-qwen-custom-voice.ps1
- scripts/windows/run-qwen-base.ps1

使用它们前设置 QWEN_TTS_RUNTIME_ROOT，并确认模型目录、qwen-tts-demo.exe 和可选 SoX 路径。启动模板不会安装或分发这些第三方组件。

## 运行数据

默认运行目录是 .runtime/，其中可能出现：

- 生成音频与试听缓存
- 临时上传文件
- ASR 模型缓存
- 服务日志
- 只含摘要的克隆授权审计记录

这些内容全部被 Git 忽略。上传的参考录音会在请求完成或失败后删除；生成音频默认保留 24 小时。

## 测试

    python -m compileall -q app.py asr_service.py audio_validation.py request_security.py gpu_lock.py tests
    python -m unittest discover -s tests -v

默认测试不加载模型、不调用 GPU，也不访问真实 Qwen 或 ASR 后端。已验证配置的脱敏证据见 [Windows/GPU 验收结果](docs/WINDOWS_GPU_ACCEPTANCE_RESULT.md)；其他配置在宣称受支持前，仍需按照 [Windows/GPU 验收清单](docs/WINDOWS_GPU_ACCEPTANCE.md) 使用授权样本完成端到端验证。样本和输出不得进入仓库。

源码公开审查、威胁模型、格式兼容证据和运行时待办记录在 [docs/PUBLIC_RELEASE_REVIEW.md](docs/PUBLIC_RELEASE_REVIEW.md)。为什么把源码公开与运行时验收分开，见 [ADR-002](docs/decisions/ADR-002-public-source-alpha.md)。

## 参与开发

提交改动前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不要在 Issue 中附加真实声音样本、生成的模仿音频、凭据或主机信息。

## 使用约束

声线克隆只能处理你本人或已经取得明确授权的声音。前端确认框不是完整的法律或身份授权系统；部署者仍需限制访问、制定留存规则并处理滥用投诉。详见 docs/USAGE_POLICY.md 与 SECURITY.md。

## License

本仓库代码采用 Apache License 2.0。Qwen3-TTS、模型、SoX 和其他第三方组件分别适用其自身许可证。
