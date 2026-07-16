#!/usr/bin/env bash

# 修复 RabbitBot 宿主运行目录的所有权与写权限。
# 本文件供 bootstrap_host.sh 与 install_air_project.sh source，不单独执行部署。

ensure_rabbitbot_runtime_permissions() {
    local air_root="$1"
    local service_user="$2"
    local service_group="$3"
    local sudo_cmd=()
    local runtime_dirs=(
        "${air_root}/logs"
        "${air_root}/logs/nav_workflow_control"
        "${air_root}/rabbitbot-dev-ros2-master/runtime"
        "${air_root}/unitree_slam_example_new/example/run_logs"
    )

    if ! id "${service_user}" >/dev/null 2>&1; then
        echo "[ERROR] RabbitBot 服务用户不存在：${service_user}" >&2
        return 1
    fi
    if ! getent group "${service_group}" >/dev/null 2>&1; then
        echo "[ERROR] RabbitBot 服务组不存在：${service_group}" >&2
        return 1
    fi
    if [ "$(id -u)" -ne 0 ]; then
        sudo_cmd=(sudo)
    fi

    echo "[INFO] 修复 RabbitBot 运行目录权限：user=${service_user}, group=${service_group}"
    "${sudo_cmd[@]}" install -d -m 2775 -o "${service_user}" -g "${service_group}" "${runtime_dirs[@]}"
    "${sudo_cmd[@]}" chown -R "${service_user}:${service_group}" "${runtime_dirs[@]}"
    "${sudo_cmd[@]}" chmod -R u+rwX,g+rwX "${runtime_dirs[@]}"
    "${sudo_cmd[@]}" find "${runtime_dirs[@]}" -type d -exec chmod g+s {} +

    local runtime_dir owner group mode
    for runtime_dir in "${runtime_dirs[@]}"; do
        owner="$(stat -c '%U' "${runtime_dir}")"
        group="$(stat -c '%G' "${runtime_dir}")"
        mode="$(stat -c '%A' "${runtime_dir}")"
        if [ "${owner}" != "${service_user}" ] || [ "${group}" != "${service_group}" ]; then
            echo "[ERROR] RabbitBot 运行目录所有权修复失败：path=${runtime_dir}, actual=${owner}:${group}, expected=${service_user}:${service_group}" >&2
            return 1
        fi
        if [ ! -w "${runtime_dir}" ] && [ "$(id -un)" = "${service_user}" ]; then
            echo "[ERROR] RabbitBot 运行目录仍不可写：path=${runtime_dir}, mode=${mode}, user=${service_user}" >&2
            return 1
        fi
        echo "[OK] RabbitBot 运行目录权限正确：path=${runtime_dir}, owner=${owner}:${group}, mode=${mode}"
    done
}
