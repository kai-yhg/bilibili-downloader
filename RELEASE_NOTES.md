# v1.0.0

第一个可用版本。

## 主要功能

- 解析 B 站 BV 链接与多 P 视频
- 使用 B 站官方扫码登录，显示账号实际可用的清晰度
- 下载 DASH 视频轨与音频轨，支持 Range 分段和备用 CDN
- 使用内置 GPAC MP4Box 无损合并，避免本项目起因中的音画不同步问题
- 下载前选择目录和文件名
- 可选择是否保留原始 M4S
- 单文件 Windows EXE，不需要单独安装 Python 或 MP4Box

## 下载

下载 `B站 MP4Box 下载器.exe` 后直接运行。建议放在桌面、下载目录或其他普通可写目录。

## 文件校验

```text
SHA-256: 120B962A2BA383963E7B83FE9DF020DA51AAF726A276A06BEEF70D9217DA547D
```

## 注意

- EXE 未购买代码签名证书，Windows SmartScreen 可能提示未知发布者。
- 扫码登录状态保存在 EXE 同目录的 `bili_login_cookies.json`，请勿分享该文件。
- 本项目不会绕过会员或清晰度权限。
