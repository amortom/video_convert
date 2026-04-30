BK7258 Video Converter v1.0.0
=============================

用途:
将客户提供的 MP4(H.264) 视频转换为 BK7258 终端可播放的 MP4(MJPEG) 视频。

使用方法:
1. 解压整个文件夹。
2. 双击 BK7258VideoConverter.exe。
3. 选择客户提供的输入 MP4 文件。
4. 输出路径会自动生成，也可以手动选择。
5. 保持默认终端参数，点击 Convert。
6. 将生成的 MP4 文件拷贝到终端播放。

默认输出格式:
- 封装: MP4
- 视频编码: MJPEG
- JPEG: Baseline, non-progressive
- 采样格式: YUV 4:2:2
- 像素格式: yuvj422p
- 分辨率: 480x480
- 帧率: 25fps，可设置 20-25fps
- 音频: 无
- 缩放: fit，黑边填充，不裁剪主体画面
- 单帧 JPEG 上限: 96KB

交付注意:
不要只复制 BK7258VideoConverter.exe。请保持整个文件夹完整，
包括 _internal 文件夹和 BK7258ConverterWorker.exe。

本工具为离线版本，客户电脑不需要安装 Python。
