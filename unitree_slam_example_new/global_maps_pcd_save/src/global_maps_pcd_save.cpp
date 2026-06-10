#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/client/client.hpp>

#include <chrono>
#include <filesystem>
#include <iostream>
#include <string>
#include <thread>

namespace {
constexpr const char *kServiceName = "slam_operate";
constexpr const char *kApiVersion = "1.0.0.1";
constexpr int32_t kEndMappingApiId = 1802;
constexpr const char *kDefaultPcdPath =
    "/mnt/ssd/navgation/projects/unitree_slam_example_new/global_maps_pcd_save/maps/global_map.pcd";

std::string JsonEscape(const std::string &value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const char ch : value) {
        switch (ch) {
        case '\\':
            escaped += "\\\\";
            break;
        case '"':
            escaped += "\\\"";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            escaped += ch;
            break;
        }
    }
    return escaped;
}

std::string EnsurePcdSuffix(std::string path) {
    if (path.size() < 4 || path.substr(path.size() - 4) != ".pcd") {
        path += ".pcd";
    }
    return path;
}

class SlamOperateClient : public unitree::robot::Client {
public:
    SlamOperateClient() : Client(kServiceName, false) {}

    void Init() override {
        SetApiVersion(kApiVersion);
        UT_ROBOT_CLIENT_REG_API_NO_PROI(kEndMappingApiId);
        SetTimeout(60.0f);
    }

    int32_t SavePcdMap(const std::string &pcd_path, std::string &response) {
        const std::string parameter =
            "{\"data\":{\"address\":\"" + JsonEscape(pcd_path) + "\"}}";

        std::cout << "api_id: " << kEndMappingApiId << std::endl;
        std::cout << "request: " << parameter << std::endl;
        return Call(kEndMappingApiId, parameter, response);
    }
};
} // namespace

int main(int argc, const char **argv) {
    if (argc < 2 || argc > 3) {
        std::cerr << "Usage: " << argv[0] << " <network_interface> [pcd_save_path]" << std::endl;
        std::cerr << "Example: " << argv[0] << " eth0 " << kDefaultPcdPath << std::endl;
        return 2;
    }

    const std::string network_interface = argv[1];
    const std::string pcd_path = EnsurePcdSuffix(argc >= 3 ? argv[2] : kDefaultPcdPath);

    try {
        const auto parent = std::filesystem::path(pcd_path).parent_path();
        if (!parent.empty()) {
            std::filesystem::create_directories(parent);
        }
    } catch (const std::exception &e) {
        std::cerr << "Failed to prepare local directory for " << pcd_path << ": " << e.what()
                  << std::endl;
        return 3;
    }

    unitree::robot::ChannelFactory::Instance()->Init(0, network_interface);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    SlamOperateClient client;
    client.Init();

    std::string response;
    std::cout << "Saving PCD map to: " << pcd_path << std::endl;
    const int32_t status_code = client.SavePcdMap(pcd_path, response);

    std::cout << "statusCode: " << status_code << std::endl;
    std::cout << "data: " << response << std::endl;

    if (status_code != 0) {
        std::cerr << "PCD map save request failed. Confirm mapping is running/ready and the path is valid on the robot."
                  << std::endl;
        return 1;
    }

    std::cout << "PCD map save request sent successfully." << std::endl;
    return 0;
}
