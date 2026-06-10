# air_robot_gt_projects 自主运行包

本目录是 RabbitBot 在 HaiSong-orin 上的自主运行项目根目录，默认路径为：

```bash
/mnt/ssd/navgation/projects/air_robot_gt_projects
```

## 目录内容

- `rabbitbot-dev-ros2-master`：主项目、控制台、workflow、虚拟环境和启动脚本。
- `models`：离线模型目录，已全量包含。
- `custom_action_ws`：Humble 自定义 action 工作区，运行时使用 `install/setup.bash`。
- `unitree_slam_example_new`：Unitree 导航、手臂 action server 和 28180 bridge 启动目录。
- `unitree_sdk2`：Unitree SDK2，用于本体 TTS 桥接构建和运行。
- `vln`、`pyorbbecsdk-v2-py310`：Robot Agent 和 workflow 所需运行依赖。
- `humble_robot_agent_bridge.py`：宿主 Humble 28180 bridge 应用。

## 一键检查

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/check_air_project.sh
```

## 安装 systemd 和控制台授权

该步骤会安装 `rabbitbot-loop.service`、`rabbitbot-control-console.service` 和控制台 sudoers 授权，但不会启动导航主程序，也不会启用开机自启。

```bash
cd /mnt/ssd/navgation/projects/air_robot_gt_projects
bash deploy/install_air_project.sh
```

如只安装不重启控制台：

```bash
RESTART_CONTROL_CONSOLE=0 bash deploy/install_air_project.sh
```

## 启动控制台

```bash
sudo systemctl start rabbitbot-control-console.service
```

浏览器访问：

```text
http://192.168.101.90:8080
```

## 启动和停止导航主程序

控制台网页中点击“开始程序”会启动：

```bash
sudo systemctl start rabbitbot-loop.service
```

停止导航主程序：

```bash
sudo systemctl stop rabbitbot-loop.service
```

两个服务默认保持非开机自启。如需查看状态：

```bash
systemctl status rabbitbot-control-console.service --no-pager -l
systemctl status rabbitbot-loop.service --no-pager -l
```

## 回滚到旧项目路径

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

- Docker 镜像 `rabbitbot-unified-runtime:20260518` 没有打包进本目录，仍依赖宿主机已存在该镜像。
- `/opt/ros/humble`、`/opt/ros/foxy` 和系统动态库仍是宿主运行时前置条件。
- `/home/unitree/test9.pcd` 是机器人本体侧路径，不属于 Orin 项目目录。
- HaiSong 的 `eno1` 当前应保持 `192.168.123.222/24`，不要与 AGX 同时接入同一机器人网络使用相同地址。

## GitHub 提交边界

当前目录仍然保留完整运行依赖，可以通过移动硬盘直接在 HaiSong-orin 上自主运行；但 Git 仓库只提交代码、配置、部署脚本和交接文档。

以下运行依赖保留在本机目录内，不提交到 GitHub：

- `models/`
- `rabbitbot-dev-ros2-master/py38/`
- `rabbitbot-dev-ros2-master/py310/`
- `custom_action_ws/install/`
- `unitree_slam_example_new/example/build/`
- `unitree_sdk2/`
- `vln/`
- `pyorbbecsdk-v2-py310/`
- `dfx_inspire_service/`

如果后续需要把项目迁移到新机器，应继续使用移动硬盘或单独的离线依赖包同步上述目录；不要依赖 GitHub 仓库恢复完整运行环境。

