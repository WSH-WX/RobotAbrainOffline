# air_robot_gt_projects 自主运行包

本目录是 RabbitBot 在 HaiSong-orin 上的自主运行项目根目录，默认路径为：

```bash
/mnt/ssd/navgation/projects/air_robot_gt_projects
```

当前仓库同时保留两条运行路径：

- `legacy`：延续现场已验证的 air 自包含目录和旧式宿主依赖。
- `portable`：面向全新 Orin 的可迁移路径。本阶段镜像暂不发布远端仓库，改为在构建机本地构建**自包含** `core`/`nav` 镜像，并通过 `docker save/load` 交付；全新 Orin 只需 GitHub 拉源码、导入这两个镜像、执行最小宿主初始化即可冷启动，运行期不再要求宿主存在 `py38/py310/vln/pyorbbecsdk/unitree_sdk2` 等目录。

## 目录内容

- `rabbitbot-dev-ros2-master`：主项目、控制台、workflow、portable Docker 定义与启动脚本。
- `models`：离线模型目录；portable 路径默认不要求 VLM 模型预置，按需下载。
- `custom_action_ws`：Humble 自定义 action 工作区源码和 legacy 运行时 install。
- `unitree_slam_example_new`：Unitree 导航、手臂 action server 和 28180 bridge 相关源码与脚本。
- `unitree_sdk2`：Unitree SDK2，用于导航节点和本体 TTS 桥接构建。
- `vln`、`pyorbbecsdk-v2-py310`：Robot Agent 和 workflow 运行依赖。
- `humble_robot_agent_bridge.py`：Humble 28180 bridge 应用。
- `third_party/manifest.lock`：Git 之外运行依赖、镜像来源和模型下载策略清单。

## portable 路径：两条流程

portable 路径分为「构建机生成镜像」和「全新 Orin 导入镜像冷启动」两段，互不重叠。

### 流程 A：构建机生成自包含镜像

构建机需要本机存在 `rabbitbot-unified-runtime:20260518` 基础镜像，以及 `unitree_sdk2`、`custom_action_ws/src`、`unitree_slam_example_new/example`、`py38`、`py310`、`vln`、`pyorbbecsdk-v2-py310` 等外部构建源。

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects

# 1) 构建机自检：要求外部构建源齐全
PORTABLE_CHECK_MODE=builder bash deploy/check_air_project.sh

# 2) 本地构建自包含 core/nav 镜像
#    core: FROM unified-runtime，并烤入 py38/py310/vln/pyorbbecsdk 与源码
#    nav : 容器内编译并固化 unitree_sdk2、导航二进制、Humble bridge、custom_action_interfaces
MODE=build bash deploy/build_or_pull_images.sh

# 3) 导出离线镜像 tar + sha256 + lock（默认输出 outputs/portable-images）
bash deploy/export_portable_images.sh
```

导出产物：`rabbitbot-core-portable.tar`、`rabbitbot-nav-portable.tar`、`images.sha256`、`images.lock.json`。把整个输出目录拷贝到全新 Orin 即可。

### 流程 B：全新 Orin 导入镜像冷启动

全新 Orin 的最小宿主前置：JetPack、Docker、NVIDIA runtime、Git、机器人网络配置能力。**不需要** `py38/py310/models/unitree_sdk2/vln/pyorbbecsdk/dfx`，也不需要旧 `rabbitbot-unified-runtime:20260518`。

```bash
# 1) GitHub 拉源码
git clone <repo> air_robot_gt_projects
cd air_robot_gt_projects
git checkout feature/portable-deploy

# 2) 导入 portable 镜像（先校验 sha256 再 docker load）
IMAGE_DIR=/path/to/portable-images bash deploy/import_portable_images.sh

# 3) 最小宿主初始化（检查工具、生成 portable.env、创建控制台轻量 venv）
bash deploy/bootstrap_host.sh
#    如需同时写入机器人 DDS 网卡配置：
#    APPLY_ROBOT_NETWORK=1 bash deploy/bootstrap_host.sh

# 4) 全新 Orin 自检：外部目录可缺失，转而要求镜像/初始化结果/地图路径配置
PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh

# 5) 校验本地镜像存在（不访问远端仓库）
MODE=check bash deploy/build_or_pull_images.sh

# 6) 启动 portable 基础服务（portable 模式会为 py38/py310/vln/pyorbbecsdk 注入从 core 镜像 seed 的依赖卷）
bash deploy/start_portable_stack.sh

# 7) 安装 systemd 服务
bash deploy/install_air_project.sh
```

### 按需准备模型（两流程通用）

默认 `workflow` 冷启动不要求 VLM ready。

- 若只跑当前主流程，可先不下载大模型；此时不会等待 `8000/8005/28184`。
- 若启用 VLM / Embedding / STT：

```bash
RABBITBOT_ENABLE_VLM=1 RABBITBOT_ENABLE_STT=1 bash deploy/ensure_models.sh
# 或显式指定模型键：
bash deploy/ensure_models.sh qwen_vlm qwen_embedding
```

`ensure_models.sh` 会按 `third_party/manifest.lock` 下载模型并记录版本、路径与校验信息。

安装后，`rabbitbot-loop.service` 会通过 `runtime/portable.env` 决定使用 portable 还是 legacy 入口；默认当前模板为 portable。

## 一键检查

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
# 构建机模式（默认）
PORTABLE_CHECK_MODE=builder bash deploy/check_air_project.sh
# 全新 Orin 模式
PORTABLE_CHECK_MODE=clean_orin bash deploy/check_air_project.sh
```

两种模式的共享检查：

- portable 依赖清单（无未解决 blocker）、portable env、`.dockerignore`、portable Docker 文件
- 关键脚本语法、Python 编译、sudoers 模板
- 核心源码旧路径硬编码与关键未环境变量化的固定 IP / 网卡配置

模式差异：

- `builder`：额外要求外部构建源（`unitree_sdk2`/`vln`/`pyorbbecsdk`/`py38`/`py310`/导航构建产物/`dfx`）与 `core` 基础镜像存在。
- `clean_orin`：允许上述外部目录缺失，转而要求已导入的 `core`/`nav` 镜像、控制台轻量 venv 与 `RABBITBOT_NAV_MAP_PATH` 配置存在。

## 控制台与主循环

启动控制台：

```bash
sudo systemctl start rabbitbot-control-console.service
```

浏览器访问：

```text
http://192.168.101.90:8080
```

启动和停止导航主程序：

```bash
sudo systemctl start rabbitbot-loop.service
sudo systemctl stop rabbitbot-loop.service
```

两个服务默认保持非开机自启。如需查看状态：

```bash
systemctl status rabbitbot-control-console.service --no-pager -l
systemctl status rabbitbot-loop.service --no-pager -l
```

## legacy 回退路径

旧项目仍位于：

```bash
/mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master
```

如需回滚，重新安装旧项目中的 systemd unit，并重启控制台即可。回滚前建议先停止导航主程序：

```bash
sudo systemctl stop rabbitbot-loop.service
sudo install -m 0644 /mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master/scripts_1/systemd/rabbitbot-loop.service /etc/systemd/system/rabbitbot-loop.service
sudo install -m 0644 /mnt/ssd/navgation/projects/rabbitbot-dev-ros2-master/deploy/rabbitbot-control-console.service /etc/systemd/system/rabbitbot-control-console.service
sudo systemctl daemon-reload
sudo systemctl restart rabbitbot-control-console.service
```

## 注意事项

- `portable core` 现为自包含镜像：以 `rabbitbot-unified-runtime:20260518` 为基础并烤入 `py38/py310/vln/pyorbbecsdk` 与源码。受限于原四个上游镜像（`navid-rabbitbot:stt-tts-audio-ct2cuda-20260511`、`rabbitbot-vllm:20260511`、`foxy-ros-cam-orb-ubuntu20:rabbitbot-20260511`）在本机已不存在（只剩 `neo4j:5.26-community`），暂不追求“不 FROM unified-runtime 的从零重建”；unified-runtime 本身即这四个镜像的合并产物。
- 镜像暂不发布远端仓库：通过 `deploy/export_portable_images.sh` / `deploy/import_portable_images.sh` 以 `docker save/load` 离线交付。全新 Orin 运行期不再需要任何宿主依赖目录。
- `/home/unitree/test9.pcd` 仍是当前默认地图路径，但已改为 `runtime/portable.env` 可配置项。
- HaiSong 的 `eno1` 当前应保持 `192.168.123.222/24`；portable 路径下建议通过 `deploy/setup_robot_network.sh` 固化，而不是手工长期维护。
- 若仅做当前 workflow 冷启动验证，默认不要求 `8000/8005` VLM / Embedding ready。

## GitHub 提交边界

Git 仓库仍只提交：

- 代码
- 配置
- Docker 定义
- 部署脚本
- 自检脚本
- 交接文档
- 依赖清单

以下运行依赖默认不直接提交到 GitHub：

- `models/`
- `rabbitbot-dev-ros2-master/py38/`
- `rabbitbot-dev-ros2-master/py310/`
- `custom_action_ws/install/`
- `unitree_slam_example_new/example/build/`
- `unitree_sdk2/`
- `vln/`
- `pyorbbecsdk-v2-py310/`
- `dfx_inspire_service/`

但从本轮开始，凡是被 `.gitignore` 排除却仍影响运行的目录，都必须在 `third_party/manifest.lock` 中有来源说明；后续不要再引入“仓库外隐形依赖”。
