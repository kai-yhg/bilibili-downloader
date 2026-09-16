# B站 MP4Box 下载器

这是一个给 Windows 用的本地 B 站视频下载器。它能读取视频分 P 和账号实际可用的清晰度，分别下载 B 站 DASH 视频轨与音频轨，再交给 MP4Box 无损封装成 MP4。

## 为什么会有这个项目

为了给家产剪cp安利视频，我试过各种浏览器插件下载 B 站视频，看起来都能正常拿到音频和视频，合成出来的 MP4 时长也差不多，但一播放就是音画不同步。有时声音提前一秒多，有时换一种合并方式又变成声音落后。网页播放明明是对的，手机端缓存的两条 M4S 也能对上，唯独下载器合并后的文件不对。

最后确认了对这类 B 站 M4S，直接用 GPAC 的 MP4Box 重建标准 MP4 轨道和 edit list，才得到实际音画同步的结果。

于是我把原来的浏览器插件思路拆掉，vibe 了这个本地应用。它没有继续猜一个固定偏移量，也不重新编码画面和声音，只负责把原始轨道下载完整，再让 MP4Box 做无损封装。

## 功能

- 支持输入 B 站 BV 链接或 BV 号
- 支持多 P 视频选择
- 使用 B 站官方扫码登录，读取账号实际可用的 1080P 等清晰度
- 同一清晰度优先选择高码率视频流和音频流
- 支持主 CDN 与备用 CDN，使用 Range 分段下载
- 下载前可以选择目录并修改最终文件名
- MP4Box 无损合并，不重新编码 H.264/AAC
- 可选择是否保留 `.video.m4s` 和 `.audio.m4s`
- 提供进度、日志与取消操作
- 单文件 Windows EXE，内置 Python 运行环境和 MP4Box

## 直接安装和使用

### 方式一：下载 Release（推荐）

1. 打开本仓库右侧的 **Releases**。
2. 下载最新版 `bilibili-downloader.exe`。
3. 把 EXE 放到一个普通、可写的目录，例如桌面、下载目录或 `D:\Tools`。
4. 双击启动，点右上角“扫码登录”，用哔哩哔哩手机客户端确认登录。
5. 粘贴视频链接，点击“解析”，选择分 P、清晰度、保存目录和文件名。
6. 点击“开始下载”。

EXE 是单文件版本，可以移动到别的目录，也可以复制到另一台 Windows 电脑。程序图标和 MP4Box 都已经内置，不依赖仓库里的 `assets` 或 `vendor` 文件夹。

扫码登录后，程序会在 EXE 所在目录写入：

```text
bili_login_cookies.json
```

这个文件只用于保存本机 B 站登录状态，已被 `.gitignore` 排除。移动程序时想保留登录状态，可以把它和 EXE 一起移动；不带它也没关系，重新扫码即可。不要把这个文件发给别人。

不建议把 EXE 放进 `C:\Program Files`、`C:\Windows` 等通常不可写的目录，否则登录 Cookie 可能无法保存。

### Windows 安全提示

这个 EXE 没有购买代码签名证书。Windows SmartScreen 首次运行时可能显示未知发布者。这不代表程序额外联网安装了什么；你可以从源码自行构建，并对照 Release 页面给出的 SHA-256。

## 从源码运行

需要 Windows 和 Python 3.11 或更新版本：

```powershell
git clone https://github.com/kai-yhg/bilibili-downloader.git
cd bilibili-downloader
python -m pip install -r requirements.txt
python .\src\bili_mp4box_downloader.py
```

源码运行会读取仓库内的 `vendor\MP4Box.exe`。

## 自己构建 EXE

在 PowerShell 中运行：

```powershell
python -m pip install -r requirements.txt
.\build.ps1
```

生成文件位于：

```text
dist\B站 MP4Box 下载器.exe
```

构建脚本使用相对路径，会把 `vendor\MP4Box.exe` 和 `assets\icon.ico` 一起打入 EXE。构建完成后，EXE 不再依赖这些外部文件。

## 关于 M4S 文件

“保留 M4S 文件”默认不勾选。MP4Box 成功生成 MP4 后，程序才会删除两个临时 M4S；如果下载或合并失败，原始 M4S 会保留，方便排查和重试。勾选后会同时保留：

```text
文件名.video.m4s
文件名.audio.m4s
文件名.mp4
```

## 登录、网络与隐私

- 登录使用 B 站官方扫码接口，不要求在应用里输入账号密码。
- Cookie 只保存在本机 EXE 所在目录。
- 视频和音频直接从 B 站返回的 CDN 地址下载。
- 本项目不提供会员权限绕过，也不会伪造账号没有权限访问的清晰度。
- 请只下载你有权保存和使用的内容，并遵守 B 站服务条款及当地法律。

## 技术路线

```text
B站视频链接
  -> view API 解析 aid/cid 和分 P
  -> playurl API 获取 DASH 清晰度与 CDN 地址
  -> Range 分段下载 video.m4s / audio.m4s
  -> MP4Box -add video.m4s#video -add audio.m4s#audio -new output.mp4
```

这里刻意没有做“所有视频统一平移一秒”之类的补偿。不同片源的时间轴并不相同，写死偏移只会让别的视频继续出问题。

## 许可证与第三方组件

本项目源码使用 MIT License。程序内置 GPAC 的 `MP4Box.exe`，它遵循 GPAC 自己的许可证；详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本项目与哔哩哔哩、GPAC 官方均无隶属或背书关系。
