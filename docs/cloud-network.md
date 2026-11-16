# 云端代理与 RunningHub 网络兼容

适用于 `api.seedance.nz` 的媒体上传和提示词增强请求，包括使用这些公共入口的节点。
节点接口、画布参数、保存字段和输出格式不变；无需修改已有工作流。

## 代理由后端配置

由容器或 RunningHub 运维给 **ComfyUI 后端进程** 配置代理，例如：

```text
HTTPS_PROXY=http://proxy-host:7890
HTTP_PROXY=http://proxy-host:7890
NO_PROXY=localhost,127.0.0.1,::1
```

将示例中的主机和端口换成该机器可访问的代理。HTTPS 请求使用 `HTTPS_PROXY`，
`ALL_PROXY` 可作通用代理；仅设置 `HTTP_PROXY` 不等于给 HTTPS 配置代理。
遵循 Requests 的小写变量优先与 `NO_PROXY` 规则，`NO_PROXY=*` 会绕过所有代理。
这些设置属于后端进程环境，浏览器代理不会传递给节点。不要公开带账号密码的代理 URL。

参见 [Requests 官方代理说明](https://requests.readthedocs.io/en/latest/user/advanced/#proxies)。

## 兼容行为

| 场景 | 行为 |
| --- | --- |
| 对目标明确配置了环境代理，且未被 NO_PROXY 排除 | 首次请求使用代理，HTTPS CONNECT 由 Requests 处理 |
| 没有显式环境代理，或只有桌面系统代理 | 保留原先的先直连策略 |
| NO_PROXY 命中目标 | 按绕过规则直连 |
| 能确认尚未建立连接的底层连接失败 | 在原有最多三次尝试内切换线路，不增加尝试预算 |
| 一般 ConnectionError、代理中途断开、读取超时或流中断 | 不据此盲目重发可能已被接受的生成请求 |
| 其他自定义 OpenAI 兼容接口与海外工坊 | 沿用自己的 Requests 行为，不套用 Seedance 专用线路策略 |
| Strata 本地／私网服务 | 沿用固定目标、直连、不使用代理的现有规则 |

原有 SSL/连接超时和指定网关状态的短重试规则保留。不会关闭 TLS 证书或主机名校验，
也不会把任何一般网络断开都当成可重试。代理返回认证错误等 HTTP 状态仍按原错误处理。
如果代理要求专用 CA，应由运维按 Requests 的受信证书配置提供，而不是关闭验证。

## 截图报错的含义

`Seedance media upload network error: ConnectionError` 来自 Requests 媒体上传链路，
不经过 `StrataClient`。旧策略始终先直连，只有少数异常允许进入环境代理线路；
当容器禁止直连且第一次产生一般 ConnectionError 时，任务会提前结束。
修复优先使用明确配置的环境代理，并识别能够确认未建立连接的底层错误。
不需要给 Strata 增加公网代理或改写它的私网访问规则。

本地验收使用自建 HTTPS 服务与带认证的 CONNECT 代理，保持证书校验开启，覆盖代理必需、
无代理、NO_PROXY、失效代理回退，以及服务接受生成请求后断开而不重发。
这些测试不调用外部模型，也不代表已在每台 RunningHub 机器上完成部署验证。
