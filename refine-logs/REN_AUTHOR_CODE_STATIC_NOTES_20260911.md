# Ren 作者代码静态对照

2026-09-11，只读源代码，未 import/执行作者程序、pickle、模型或RUL。GitHub API核验当前提交为 8a71f99d9e25adbd722708199438a89ff739d2a5；下载固定commit的README和preprocess源码到ignored staging，按文本处理。

来源：[README](https://github.com/GlimmerR/SCs/blob/8a71f99d9e25adbd722708199438a89ff739d2a5/README.md)、[preprocess.py](https://github.com/GlimmerR/SCs/blob/8a71f99d9e25adbd722708199438a89ff739d2a5/preprocess.py)。代码将无双下划线文件视为主文件，并依次读取 __1、__2 等分片。主文件先读step/cycle，续片从第一个sheet继续。源码存在广义except后停止读sheet的行为，不能将这种停止方式用于本项目完整性判断。

作者默认电容推导路径使用固定放电电流20 mA、工步时间及电压差，且构造对象时调用固定阈值的life设置。它不能代替本项目对电流、时间、端点、删失及阈值的独立核验。因此不直接执行/复用作者预处理结果，也不把其life当ground truth。

本地字节证据（均ignored）：

- data/raw/ren_scs/author_source_20260911/preprocess.py.txt；SHA-256 4c3a1b071464021393a31fece4531cdd01e139f524fdd02f9b71d58b44719d29。
- data/raw/ren_scs/author_source_20260911/README.md.txt；SHA-256 94f2230b7e3c1be5f49bd5884423a9d312669b473b06bbd40d93c4ecbf19ac38。

与本项目已落盘schema的对照（不是作者声明）：233文件匹配该分片命名规则；113主文件含step/cycle，其余120文件仅record表；53组单文件、60组三文件；每组分片编号完整。四批候选组数28/25/30/30。该对应只建立来源命名候选组，尚未验证行级连续性和物理设备身份。不能立即用于whole-unit LOCO。

下步应验证每组记录编号、cycle/step/status和时间在sheet及文件边界的关系，记录重复/缺口/归零，不能通过排序、补零、丢弃最后一行或filename-only身份假设来制造PASS。
