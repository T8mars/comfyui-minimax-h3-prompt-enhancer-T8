# Strata 桥接 / Existing-service bridge

适用于 H3、Seedance 2.0、Qwen Image 2.1、Music 3、YuE2、作词和编曲节点，以及现有调用 LLM 的创作工具。它是第三类后端，不替换原 API 或直接 GGUF 路径，不生成视频或音频。

## 怎么用

独立示例：[H3 文本＋共享配置](../example_workflows/strata_h3_text.json)、[Qwen 图像编辑](../example_workflows/strata_qwen_image_edit.json)、[H3 首尾帧＋视频 Hybrid](../example_workflows/strata_h3_hybrid_video.json)。图片/视频占位文件需换成自己的素材，示例没有密钥。

1. 用户先启动自己的 Strata 服务，并在服务中配置模型与视觉能力。
2. 增强节点选 `Strata 本地服务（桥接）`，填写文字，按原方法连接参考图或 VIDEO。默认无需配置节点。
3. 非默认地址或高级设置：添加 `T8 LLM Provider Config`，选 `Strata` 并连到共享配置入口。`AUTO` 使用服务当前模型，不扫描 ComfyUI/models。
4. 共享配置节点点“只读检查 Strata”只请求状态，不生成、不加载模型。正常生成可以触发服务自己已配置的自动加载。

`127.0.0.1` 指 ComfyUI 后端主机。容器/云端填写后端能访问的私网地址，显式允许私网并配置独立认证；不支持公网任意 URL、代理、重定向或带密码 URL。

## 设置边界

| 设置 | 含义 |
| --- | --- |
| 模型 | AUTO、当前正式 ID 或已核验别名；不匹配提示在服务中切换，不代替用户切换 |
| 生成 Token | 默认 0：服务剩余上下文，**不是无限 Token**；输入、视觉、思考、正文共享服务上下文 |
| 思考 | 默认 none，独立于旧 GGUF 选项；low/medium/high 和预算交给服务 |
| 视频模式 | 默认 frames；native 需服务核验，不自动降级或偷偷丢视频 |
| 视频采样 | 默认每段最多 8 个样本、名义 1 fps；保留有效首尾，报告实际时间点和最大间隙 |
| 总超时 | 默认 1800 秒，包含节点排队、生成和既有纠正阶段，不是每阶段重置 |
| 凭据 | Strata 独立别名；无认证本机服务可留空。完整 GitHub 安装支持 STRATA_API_KEY，Registry 安装应使用凭据别名 |

旧 API Key、云端 URL/模型、附加 JSON、GGUF 模型路径/mmproj/上下文/卸载参数不控制 Strata。切回原渠道保留这些旧值。共享配置连接时覆盖节点模式，断开恢复原模式。

图片按原标签/角色传入；视频使用显式 `strata_video` 协议 1，不使用会被忽略的普通 `video_url`。文件、已有帧组件和官方文件拼接列表通过 CPU 有界处理，保留裁剪与时间戳，不整段重编码、不读取音轨。未知 VIDEO 实现提示转换，不静默猜测。

当前服务协议每请求合计最多 64 个视频样本、每选定窗口最多 3600 秒，更小的服务声明优先；资源/上下文不足仍可能拒绝请求。桥接 JSON 上限 64 MiB，响应 16 MiB，本地解码源上限 256 MiB。这些不是原 API/GGUF 模式的新限制。图片会缩放，抽帧不是连续观察，不能声称听到台词、识别 BPM 或覆盖每一帧。

## 失败、取消与恢复

不自动重发 chat POST。503、认证错误、模型变化、超时、空正文或截断给出脱敏错误，不把不完整回答当成完成。原节点明确的质量/语言/结构纠正仍会产生额外请求，报告列出实际次数；这不是网络重试。

预检失败不会覆盖原恢复记录。“恢复上次结果”仍只恢复本 ComfyUI 进程内已保存的完整输出，不查询 Strata 历史任务、不重新生成，重启后缓存可能消失。取消关闭本次连接，不停止服务，也不保证显存立即释放。运行前后核对模型/实例/上下文，但这不是原子模型锁，运行时不要在其他客户端切换模型。

## Compatibility / English

The provider choice is appended. Old defaults, node IDs, main widget arrays, linked-input validation and old workflow bytes remain unchanged. Shared provider config appends eleven optional fields with named old-16/new-27 restoration and host action-tail handling. Old workflows load in the new plugin; new Strata workflows are not promised to work in an older plugin. RunningHub deployment has not been independently verified.

The bridge calls only GET status/models and non-streaming chat POST. It does not own the service lifecycle, download/load GGUF models itself, or analyze audio. Acceptance proves transport/native text/JSON and node queue behavior, not rendered video/music quality. MIT CPU helper provenance and license are included in `strata_vendor`.
