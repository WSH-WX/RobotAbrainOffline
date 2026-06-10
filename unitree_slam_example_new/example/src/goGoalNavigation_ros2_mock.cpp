/**
 * @file goGoalNavigation_ros2_mock.cpp
 * @brief ROS2-only mock navigation node for testing topics and actions without robot hardware.
 *
 * This executable keeps the same ROS2 surface as goGoalNavigation_ros2.cpp but does not
 * initialize Unitree network channels, does not call the robot SDK, and does not load PCD maps.
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/u_int8.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>

#include <custom_action_interfaces/action/navi_forward.hpp>
#include <custom_action_interfaces/action/navi_rotate.hpp>
#include <custom_action_interfaces/action/navi_way_point.hpp>

#include "json.hpp"

#include <atomic>
#include <chrono>
#include <cmath>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <algorithm>
#include <iostream>
#include <thread>

namespace {

constexpr double kPi = 3.14159265358979323846;

struct PoseData
{
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float q_x = 0.0f;
    float q_y = 0.0f;
    float q_z = 0.0f;
    float q_w = 1.0f;
    float speed = -1.0f;
    int mode = 1;
};

bool isNear(double a, double b, double eps = 0.05)
{
    return std::fabs(a - b) <= eps;
}

bool isMidTransitionPoint(const PoseData& goal)
{
    return (isNear(goal.x, 2.9386) && isNear(goal.y, -4.9274)) ||
           (isNear(goal.x, 16.8283) && isNear(goal.y, 7.5128)) ||
           (isNear(goal.x, 11.7036) && isNear(goal.y, 16.2018));
}

double yawFromQuat(const PoseData& p)
{
    const double siny_cosp = 2.0 * (static_cast<double>(p.q_w) * static_cast<double>(p.q_z) +
                                    static_cast<double>(p.q_x) * static_cast<double>(p.q_y));
    const double cosy_cosp = 1.0 - 2.0 * (static_cast<double>(p.q_y) * static_cast<double>(p.q_y) +
                                          static_cast<double>(p.q_z) * static_cast<double>(p.q_z));
    return std::atan2(siny_cosp, cosy_cosp);
}

void setQuatFromYaw(PoseData& p, double yaw)
{
    p.q_x = 0.0f;
    p.q_y = 0.0f;
    p.q_z = static_cast<float>(std::sin(yaw * 0.5));
    p.q_w = static_cast<float>(std::cos(yaw * 0.5));
}

PoseData poseFromJson(const std::string& payload, float defaultNavSpeed)
{
    const auto jsonData = nlohmann::json::parse(payload);
    const auto& data = jsonData.contains("data") ? jsonData.at("data") : jsonData;

    PoseData goal;
    goal.x = data.value("x", 0.0f);
    goal.y = data.value("y", 0.0f);
    goal.z = data.value("z", 0.0f);
    goal.q_x = data.value("ox", 0.0f);
    goal.q_y = data.value("oy", 0.0f);
    goal.q_z = data.value("oz", 0.0f);
    goal.q_w = data.value("ow", 1.0f);
    goal.mode = data.value("mode", 1);
    goal.speed = data.value("speed", defaultNavSpeed);
    return goal;
}

nlohmann::json poseToJson(const PoseData& pose)
{
    nlohmann::json poseJson;
    poseJson["x"] = pose.x;
    poseJson["y"] = pose.y;
    poseJson["z"] = pose.z;
    poseJson["ox"] = pose.q_x;
    poseJson["oy"] = pose.q_y;
    poseJson["oz"] = pose.q_z;
    poseJson["ow"] = pose.q_w;
    poseJson["mode"] = pose.mode;
    if (pose.speed > 0.0f) {
        poseJson["speed"] = pose.speed;
    }
    return poseJson;
}

void printGoalToTerminal(const rclcpp::Logger& logger, const std::string& source, const PoseData& goal)
{
    const std::string goalJson = poseToJson(goal).dump();
    RCLCPP_INFO(logger, "========== Mock Navigation Goal Received ==========");
    RCLCPP_INFO(logger, "source: %s", source.c_str());
    RCLCPP_INFO(logger, "target: x=%.4f y=%.4f z=%.4f", goal.x, goal.y, goal.z);
    RCLCPP_INFO(logger, "orientation: ox=%.4f oy=%.4f oz=%.4f ow=%.4f",
                goal.q_x, goal.q_y, goal.q_z, goal.q_w);
    RCLCPP_INFO(logger, "mode=%d speed=%.4f", goal.mode, goal.speed);
    RCLCPP_INFO(logger, "json: %s", goalJson.c_str());
    RCLCPP_INFO(logger, "==================================================");

    std::cout << "\n========== Mock Navigation Goal Received ==========" << std::endl;
    std::cout << "source: " << source << std::endl;
    std::cout << "target: x=" << goal.x << " y=" << goal.y << " z=" << goal.z << std::endl;
    std::cout << "orientation: ox=" << goal.q_x << " oy=" << goal.q_y
              << " oz=" << goal.q_z << " ow=" << goal.q_w << std::endl;
    std::cout << "mode=" << goal.mode << " speed=" << goal.speed << std::endl;
    std::cout << "json: " << goalJson << std::endl;
    std::cout << "==================================================" << std::endl;
}

} // namespace

class MockHybridNavigationNode : public rclcpp::Node
{
private:
    using NaviForward = custom_action_interfaces::action::NaviForward;
    using NaviRotate = custom_action_interfaces::action::NaviRotate;
    using NaviWayPoint = custom_action_interfaces::action::NaviWayPoint;

    using GoalHandleNaviForward = rclcpp_action::ServerGoalHandle<NaviForward>;
    using GoalHandleNaviRotate = rclcpp_action::ServerGoalHandle<NaviRotate>;
    using GoalHandleNaviWayPoint = rclcpp_action::ServerGoalHandle<NaviWayPoint>;

public:
    MockHybridNavigationNode(float defaultNavSpeed, std::chrono::milliseconds navigationDelay)
        : Node("hybrid_navigation_node"),
          defaultNavSpeed_(defaultNavSpeed),
          navigationDelay_(navigationDelay)
    {
        goalSub_ = create_subscription<std_msgs::msg::String>(
            "/go_goal_pose", 10,
            std::bind(&MockHybridNavigationNode::goalCallback, this, std::placeholders::_1));

        cmdSub_ = create_subscription<std_msgs::msg::String>(
            "/slam_cmd", 10,
            std::bind(&MockHybridNavigationNode::cmdCallback, this, std::placeholders::_1));

        statusPub_ = create_publisher<std_msgs::msg::String>("/nav_status", 10);
        posePub_ = create_publisher<std_msgs::msg::String>("/current_pose", 10);
        lioPosePub_ = create_publisher<geometry_msgs::msg::PoseStamped>("/lio_pose", 10);
        kuavoNavStatePub_ = create_publisher<std_msgs::msg::UInt8>("/kuavo_navigation_state", 10);

        naviForwardServer_ = rclcpp_action::create_server<NaviForward>(
            this,
            "navi_forward",
            [this](const rclcpp_action::GoalUUID&, std::shared_ptr<const NaviForward::Goal> goal) {
                RCLCPP_INFO(get_logger(), "[MockAction] navi_forward goal distance=%.3f", goal->distance);
                return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
            },
            [this](const std::shared_ptr<GoalHandleNaviForward>) {
                cancelCurrentNavigation("navi_forward canceled");
                return rclcpp_action::CancelResponse::ACCEPT;
            },
            [this](const std::shared_ptr<GoalHandleNaviForward> goalHandle) {
                std::thread(&MockHybridNavigationNode::executeForward, this, goalHandle).detach();
            });

        naviRotateServer_ = rclcpp_action::create_server<NaviRotate>(
            this,
            "navi_rotate",
            [this](const rclcpp_action::GoalUUID&, std::shared_ptr<const NaviRotate::Goal> goal) {
                RCLCPP_INFO(get_logger(), "[MockAction] navi_rotate goal theta=%.3f", goal->theta);
                return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
            },
            [this](const std::shared_ptr<GoalHandleNaviRotate>) {
                cancelCurrentNavigation("navi_rotate canceled");
                return rclcpp_action::CancelResponse::ACCEPT;
            },
            [this](const std::shared_ptr<GoalHandleNaviRotate> goalHandle) {
                std::thread(&MockHybridNavigationNode::executeRotate, this, goalHandle).detach();
            });

        naviWayPointServer_ = rclcpp_action::create_server<NaviWayPoint>(
            this,
            "navi_way_point",
            [this](const rclcpp_action::GoalUUID&, std::shared_ptr<const NaviWayPoint::Goal> goal) {
                RCLCPP_INFO(get_logger(), "[MockAction] navi_way_point goal x=%.3f y=%.3f z=%.3f",
                            goal->position_x, goal->position_y, goal->position_z);
                return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
            },
            [this](const std::shared_ptr<GoalHandleNaviWayPoint>) {
                cancelCurrentNavigation("navi_way_point canceled");
                return rclcpp_action::CancelResponse::ACCEPT;
            },
            [this](const std::shared_ptr<GoalHandleNaviWayPoint> goalHandle) {
                std::thread(&MockHybridNavigationNode::executeWayPoint, this, goalHandle).detach();
            });

        poseTimer_ = create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&MockHybridNavigationNode::publishCurrentPose, this));

        publishStatus("ready");
        publishNavState(2);
        publishCurrentPose();

        RCLCPP_INFO(get_logger(), "===========================================");
        RCLCPP_INFO(get_logger(), "Hybrid Navigation Node MOCK (ROS2 only)");
        RCLCPP_INFO(get_logger(), "No Unitree network interface, no PCD loading, no robot SDK calls.");
        RCLCPP_INFO(get_logger(), "Topics: /go_goal_pose, /slam_cmd, /nav_status, /current_pose, /lio_pose, /kuavo_navigation_state");
        RCLCPP_INFO(get_logger(), "Actions: navi_forward, navi_rotate, navi_way_point");
        RCLCPP_INFO(get_logger(), "Mock navigation delay: %.3f s", navigationDelay_.count() / 1000.0);
        if (defaultNavSpeed_ > 0.0f) {
            RCLCPP_INFO(get_logger(), "Default nav speed: %.3f m/s", defaultNavSpeed_);
        }
        RCLCPP_INFO(get_logger(), "===========================================");
    }

private:
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr goalSub_;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr cmdSub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr statusPub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr posePub_;
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr lioPosePub_;
    rclcpp::Publisher<std_msgs::msg::UInt8>::SharedPtr kuavoNavStatePub_;
    rclcpp::TimerBase::SharedPtr poseTimer_;

    rclcpp_action::Server<NaviForward>::SharedPtr naviForwardServer_;
    rclcpp_action::Server<NaviRotate>::SharedPtr naviRotateServer_;
    rclcpp_action::Server<NaviWayPoint>::SharedPtr naviWayPointServer_;

    std::mutex poseMutex_;
    PoseData currentPose_;
    std::atomic<bool> isNavigating_{false};
    std::atomic<uint64_t> navigationGeneration_{0};
    float defaultNavSpeed_ = -1.0f;
    std::chrono::milliseconds navigationDelay_{500};

    PoseData getCurrentPose()
    {
        std::lock_guard<std::mutex> lock(poseMutex_);
        return currentPose_;
    }

    void setCurrentPose(const PoseData& pose)
    {
        {
            std::lock_guard<std::mutex> lock(poseMutex_);
            currentPose_ = pose;
        }
        publishCurrentPose();
    }

    void publishStatus(const std::string& status)
    {
        auto msg = std_msgs::msg::String();
        msg.data = status;
        statusPub_->publish(msg);
        RCLCPP_INFO(get_logger(), "[MockStatus] %s", status.c_str());
    }

    void publishNavState(uint8_t state)
    {
        auto msg = std_msgs::msg::UInt8();
        msg.data = state;
        kuavoNavStatePub_->publish(msg);
    }

    void publishCurrentPose()
    {
        const PoseData pose = getCurrentPose();

        auto poseMsg = std_msgs::msg::String();
        poseMsg.data = poseToJson(pose).dump();
        posePub_->publish(poseMsg);

        auto lioPoseMsg = geometry_msgs::msg::PoseStamped();
        lioPoseMsg.header.stamp = now();
        lioPoseMsg.header.frame_id = "map";
        lioPoseMsg.pose.position.x = pose.x;
        lioPoseMsg.pose.position.y = pose.y;
        lioPoseMsg.pose.position.z = pose.z;
        lioPoseMsg.pose.orientation.x = pose.q_x;
        lioPoseMsg.pose.orientation.y = pose.q_y;
        lioPoseMsg.pose.orientation.z = pose.q_z;
        lioPoseMsg.pose.orientation.w = pose.q_w;
        lioPosePub_->publish(lioPoseMsg);
    }

    void cancelCurrentNavigation(const std::string& reason)
    {
        navigationGeneration_.fetch_add(1);
        isNavigating_.store(false);
        publishStatus("preempted");
        publishNavState(2);
        RCLCPP_INFO(get_logger(), "[MockNavigation] %s", reason.c_str());
    }

    bool simulateNavigation(
        const PoseData& goal,
        const std::string& source,
        const std::function<bool()>& isCanceling)
    {
        const uint64_t generation = navigationGeneration_.fetch_add(1) + 1;
        isNavigating_.store(true);
        publishStatus("navigating");
        publishNavState(1);

        RCLCPP_INFO(get_logger(), "[MockNavigation] %s start: x=%.3f y=%.3f z=%.3f q=(%.3f %.3f %.3f %.3f)",
                    source.c_str(), goal.x, goal.y, goal.z, goal.q_x, goal.q_y, goal.q_z, goal.q_w);

        const auto deadline = std::chrono::steady_clock::now() + navigationDelay_;
        while (rclcpp::ok() && std::chrono::steady_clock::now() < deadline) {
            if (isCanceling() || navigationGeneration_.load() != generation) {
                isNavigating_.store(false);
                publishStatus("preempted");
                publishNavState(2);
                RCLCPP_INFO(get_logger(), "[MockNavigation] %s preempted", source.c_str());
                return false;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }

        if (!rclcpp::ok() || isCanceling() || navigationGeneration_.load() != generation) {
            isNavigating_.store(false);
            publishStatus("preempted");
            publishNavState(2);
            return false;
        }

        setCurrentPose(goal);
        isNavigating_.store(false);
        publishStatus(isMidTransitionPoint(goal) ? "mid_arrived" : "arrived");
        publishNavState(2);
        RCLCPP_INFO(get_logger(), "[MockNavigation] %s arrived", source.c_str());
        return true;
    }

    void goalCallback(const std_msgs::msg::String::SharedPtr msg)
    {
        RCLCPP_INFO(get_logger(), "[MockGoal] %s", msg->data.c_str());

        if (isNavigating_.load()) {
            cancelCurrentNavigation("new /go_goal_pose received");
        }

        try {
            const PoseData goal = poseFromJson(msg->data, defaultNavSpeed_);
            printGoalToTerminal(get_logger(), "/go_goal_pose", goal);
            std::thread([this, goal]() {
                simulateNavigation(goal, "/go_goal_pose", []() { return false; });
            }).detach();
        } catch (const std::exception& e) {
            RCLCPP_ERROR(get_logger(), "[MockGoal] JSON error: %s", e.what());
            publishStatus("goal_parse_error");
        }
    }

    void cmdCallback(const std_msgs::msg::String::SharedPtr msg)
    {
        RCLCPP_INFO(get_logger(), "[MockCMD] %s", msg->data.c_str());

        try {
            const auto cmd = nlohmann::json::parse(msg->data);
            const std::string cmdType = cmd.value("cmd", "");

            if (cmdType == "start_mapping") {
                publishStatus("mapping_started_mock");
            } else if (cmdType == "end_mapping") {
                publishStatus("mapping_finished_mock");
                RCLCPP_INFO(get_logger(), "[MockCMD] PCD path ignored in mock mode");
            } else if (cmdType == "start_relocation") {
                PoseData pose = getCurrentPose();
                pose.x = cmd.value("x", pose.x);
                pose.y = cmd.value("y", pose.y);
                pose.z = cmd.value("z", pose.z);
                pose.q_x = cmd.value("ox", pose.q_x);
                pose.q_y = cmd.value("oy", pose.q_y);
                pose.q_z = cmd.value("oz", pose.q_z);
                pose.q_w = cmd.value("ow", pose.q_w);
                setCurrentPose(pose);
                publishStatus("relocated_mock");
                publishNavState(2);
                RCLCPP_INFO(get_logger(), "[MockCMD] Relocation accepted without PCD loading");
            } else if (cmdType == "pause_nav") {
                publishStatus("paused");
            } else if (cmdType == "resume_nav") {
                publishStatus("resumed");
            } else if (cmdType == "stop_nav") {
                cancelCurrentNavigation("stop_nav command");
                publishStatus("stopped");
            } else if (cmdType == "stop_node") {
                publishStatus("stop_node_ignored_mock");
            } else {
                RCLCPP_WARN(get_logger(), "[MockCMD] Unknown command: %s", cmdType.c_str());
                publishStatus("unknown_cmd");
            }
        } catch (const std::exception& e) {
            RCLCPP_ERROR(get_logger(), "[MockCMD] JSON error: %s", e.what());
            publishStatus("cmd_parse_error");
        }
    }

    void executeForward(const std::shared_ptr<GoalHandleNaviForward> goalHandle)
    {
        const auto goal = goalHandle->get_goal();
        PoseData target = getCurrentPose();
        const double yaw = yawFromQuat(target);
        target.x += static_cast<float>(goal->distance * std::cos(yaw));
        target.y += static_cast<float>(goal->distance * std::sin(yaw));
        printGoalToTerminal(get_logger(), "navi_forward", target);

        const bool ok = simulateNavigation(target, "navi_forward", [goalHandle]() {
            return goalHandle->is_canceling();
        });

        auto result = std::make_shared<NaviForward::Result>();
        result->delta = goal->distance;
        if (goalHandle->is_canceling()) {
            goalHandle->canceled(result);
        } else if (ok) {
            goalHandle->succeed(result);
        } else {
            goalHandle->abort(result);
        }
    }

    void executeRotate(const std::shared_ptr<GoalHandleNaviRotate> goalHandle)
    {
        const auto goal = goalHandle->get_goal();
        PoseData target = getCurrentPose();
        const double nextYaw = yawFromQuat(target) + goal->theta * kPi / 180.0;
        setQuatFromYaw(target, nextYaw);
        printGoalToTerminal(get_logger(), "navi_rotate", target);

        const bool ok = simulateNavigation(target, "navi_rotate", [goalHandle]() {
            return goalHandle->is_canceling();
        });

        auto result = std::make_shared<NaviRotate::Result>();
        result->delta = goal->theta;
        if (goalHandle->is_canceling()) {
            goalHandle->canceled(result);
        } else if (ok) {
            goalHandle->succeed(result);
        } else {
            goalHandle->abort(result);
        }
    }

    void executeWayPoint(const std::shared_ptr<GoalHandleNaviWayPoint> goalHandle)
    {
        const auto actionGoal = goalHandle->get_goal();
        PoseData goal;
        goal.x = actionGoal->position_x;
        goal.y = actionGoal->position_y;
        goal.z = actionGoal->position_z;
        goal.q_x = actionGoal->orientation_x;
        goal.q_y = actionGoal->orientation_y;
        goal.q_z = actionGoal->orientation_z;
        goal.q_w = actionGoal->orientation_w;
        goal.speed = defaultNavSpeed_;
        printGoalToTerminal(get_logger(), "navi_way_point", goal);

        const bool ok = simulateNavigation(goal, "navi_way_point", [goalHandle]() {
            return goalHandle->is_canceling();
        });

        auto result = std::make_shared<NaviWayPoint::Result>();
        result->position_x_delta = 0.0f;
        result->position_y_delta = 0.0f;
        result->position_z_delta = 0.0f;
        result->orientation_x_delta = 0.0f;
        result->orientation_y_delta = 0.0f;
        result->orientation_z_delta = 0.0f;
        result->orientation_w_delta = 0.0f;

        if (goalHandle->is_canceling()) {
            goalHandle->canceled(result);
        } else if (ok) {
            goalHandle->succeed(result);
        } else {
            goalHandle->abort(result);
        }
    }
};

int main(int argc, char* argv[])
{
    rclcpp::init(argc, argv);

    float navSpeed = -1.0f;
    double delaySeconds = 0.5;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const std::string navSpeedPrefix = "--nav_speed=";
        const std::string speedPrefix = "--speed=";
        const std::string delayPrefix = "--delay=";

        try {
            if (arg == "--help" || arg == "-h") {
                std::cout << "Usage: " << argv[0] << " [ignored_network_or_pcd_args] [--nav_speed=MPS] [--delay=SECONDS]" << std::endl;
                rclcpp::shutdown();
                return 0;
            }
            if (arg.rfind(navSpeedPrefix, 0) == 0) {
                navSpeed = std::stof(arg.substr(navSpeedPrefix.size()));
            } else if (arg.rfind(speedPrefix, 0) == 0) {
                navSpeed = std::stof(arg.substr(speedPrefix.size()));
            } else if (arg.rfind(delayPrefix, 0) == 0) {
                delaySeconds = std::stod(arg.substr(delayPrefix.size()));
            }
        } catch (const std::exception& e) {
            std::cerr << "Invalid argument: " << arg << " (" << e.what() << ")" << std::endl;
            rclcpp::shutdown();
            return 1;
        }
    }

    const auto delayMs = std::chrono::milliseconds(
        static_cast<int64_t>(std::max(0.0, delaySeconds) * 1000.0));
    auto node = std::make_shared<MockHybridNavigationNode>(navSpeed, delayMs);
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
