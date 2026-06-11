# air_robot_gt_projects 自主运行包

本目录是 RabbitBot 在 HaiSong-orin 上的自主运行项目根目录，默认路径为：

```bash
/mnt/ssd/navgation/projects/air_robot_gt_projects
```

当前仓库同时保留两条运行路径：

- `legacy`：延续现场已验证的 air 自包含目录和旧式宿主依赖。
- `portable`：面向全新 Orin 的可迁移路径，目标是通过 GitHub 源码、最小宿主初始化和可拉取/可构建镜像完成冷启动。

## 目录内容

- `rabbitbot-dev-ros2-master`：主项目、控制台、workflow、portable Docker 定义与启动脚本。
- `models`：离线模型目录；portable 路径默认不要求 VLM 模型预置，按需下载。
- `custom_action_ws`：Humble 自定义 action 工作区源码和 legacy 运行时 install。
- `unitree_slam_example_new`：Unitree 导航、手臂 action server 和 28180 bridge 相关源码与脚本。
- `unitree_sdk2`：Unitree SDK2，用于导航节点和本体 TTS 桥接构建。
- `vln`、`pyorbbecsdk-v2-py310`：Robot Agent 和 workflow 运行依赖。
- `humble_robot_agent_bridge.py`：Humble 28180 bridge 应用。
- `third_party/manifest.lock`：Git 之外运行依赖、镜像来源和模型下载策略清单。

## portable 路径推荐流程

### 1. 宿主初始化

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/bootstrap_host.sh
```

如需同时写入机器人 DDS 网卡配置：

```bash
APPLY_ROBOT_NETWORK=1 bash deploy/bootstrap_host.sh
```

该步骤会：

- 检查 `git`、`docker`、`docker compose`、`python3`
- 更新 `rabbitbot-dev-ros2-master/runtime/portable.env`
- 创建控制台轻量虚拟环境
- 按需调用 `deploy/setup_robot_network.sh`

### 2. 准备 portable 镜像

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/build_or_pull_images.sh
```

默认行为：

- 优先拉取 `portable core` 成品镜像
- 优先本地构建 `portable nav` 镜像
- 当前若缺少 `unitree_sdk2` / `custom_action_ws` / 导航源码目录，会明确报错并要求先恢复依赖

### 3. 按需准备模型

默认 `workflow` 冷启动不要求 VLM ready。

- 若只跑当前主流程，可先不下载大模型。
- 若启用 VLM / Embedding / STT，可运行：

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/ensure_models.sh
```

也可显式指定模型键：

```bash
bash deploy/ensure_models.sh qwen_vlm qwen_embedding
```

### 4. 启动 portable 基础服务

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/start_portable_stack.sh
```

### 5. 安装 systemd 服务

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/install_air_project.sh
```

安装后，`rabbitbot-loop.service` 会通过 `runtime/portable.env` 决定使用 portable 还是 legacy 入口；默认当前模板为 portable。

## 一键检查

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/check_air_project.sh
```

当前检查会同时覆盖：

- legacy 目录结构与关键运行文件
- portable 依赖清单、portable env、portable Docker 文件
- 关键脚本语法、Python 编译、sudoers 模板
- 运行脚本旧路径硬编码与关键未环境变量化的固定 IP / 网卡配置

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

- `portable core` 当前仍默认建立在 `rabbitbot-unified-runtime:20260518` 基础镜像之上，完整历史构建链尚未全部公开重建。
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
