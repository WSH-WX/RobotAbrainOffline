#include <fcntl.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace {

volatile sig_atomic_t g_stop_requested = 0;
std::vector<pid_t> g_children;
std::vector<std::string> g_child_names;

void SignalHandler(int) {
  g_stop_requested = 1;
}

pid_t SpawnChild(const std::string &exe_path,
                 const std::vector<std::string> &args,
                 bool silent_output) {
  pid_t pid = fork();
  if (pid < 0) {
    perror("fork");
    return -1;
  }

  if (pid == 0) {
    if (silent_output) {
      int null_fd = open("/dev/null", O_WRONLY);
      if (null_fd >= 0) {
        dup2(null_fd, STDOUT_FILENO);
        dup2(null_fd, STDERR_FILENO);
        close(null_fd);
      }
    }

    std::vector<char *> argv;
    argv.reserve(args.size() + 2);
    argv.push_back(const_cast<char *>(exe_path.c_str()));
    for (const auto &arg : args) {
      argv.push_back(const_cast<char *>(arg.c_str()));
    }
    argv.push_back(nullptr);

    execv(exe_path.c_str(), argv.data());
    perror("execv");
    _exit(127);
  }

  return pid;
}

void TerminateChildren() {
  for (size_t i = 0; i < g_children.size(); ++i) {
    pid_t pid = g_children[i];
    if (pid > 0) {
      kill(pid, SIGINT);
      std::cout << "[integrated] sent SIGINT to " << g_child_names[i]
                << " (pid=" << pid << ")" << std::endl;
    }
  }

  for (size_t i = 0; i < g_children.size(); ++i) {
    pid_t pid = g_children[i];
    if (pid > 0) {
      int status = 0;
      waitpid(pid, &status, 0);
      std::cout << "[integrated] " << g_child_names[i]
                << " stopped (pid=" << pid << ")" << std::endl;
    }
  }
}

}  // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0] << " <network_interface> [pcd_path]" << std::endl;
    return -1;
  }

  const std::string network_interface = argv[1];
  const std::string pcd_path = (argc >= 3) ? argv[2] : "";

  std::filesystem::path self_path = std::filesystem::absolute(argv[0]);
  std::filesystem::path bin_dir = self_path.parent_path();

  const std::string go_goal_path = (bin_dir / "goGoalNavigation").string();
  const std::string gesture_bridge_path = (bin_dir / "gestureTopicBridge").string();
  const std::string arm_action_path = (bin_dir / "g1Arm7DIYActionExample").string();

  std::cout << "[integrated] launcher started" << std::endl;
  std::cout << "[integrated] network_interface=" << network_interface << std::endl;
  if (!pcd_path.empty()) {
    std::cout << "[integrated] pcd_path=" << pcd_path << std::endl;
  }

  signal(SIGINT, SignalHandler);
  signal(SIGTERM, SignalHandler);

  {
    std::vector<std::string> args{network_interface};
    if (!pcd_path.empty()) {
      args.push_back(pcd_path);
    }
    pid_t p = SpawnChild(go_goal_path, args, true);
    if (p <= 0) {
      std::cerr << "[integrated] failed to start goGoalNavigation" << std::endl;
      TerminateChildren();
      return -1;
    }
    g_children.push_back(p);
    g_child_names.push_back("goGoalNavigation");
    std::cout << "[integrated] started goGoalNavigation (pid=" << p << ")" << std::endl;
  }

  {
    std::vector<std::string> args{network_interface};
    pid_t p = SpawnChild(gesture_bridge_path, args, true);
    if (p <= 0) {
      std::cerr << "[integrated] failed to start gestureTopicBridge" << std::endl;
      TerminateChildren();
      return -1;
    }
    g_children.push_back(p);
    g_child_names.push_back("gestureTopicBridge");
    std::cout << "[integrated] started gestureTopicBridge (pid=" << p << ")" << std::endl;
  }

  {
    std::vector<std::string> args{network_interface};
    pid_t p = SpawnChild(arm_action_path, args, true);
    if (p <= 0) {
      std::cerr << "[integrated] failed to start g1Arm7DIYActionExample" << std::endl;
      TerminateChildren();
      return -1;
    }
    g_children.push_back(p);
    g_child_names.push_back("g1Arm7DIYActionExample");
    std::cout << "[integrated] started g1Arm7DIYActionExample (pid=" << p << ")" << std::endl;
  }

  while (!g_stop_requested) {
    int status = 0;
    pid_t exited = waitpid(-1, &status, WNOHANG);
    if (exited > 0) {
      std::cerr << "[integrated] detected child exit (pid=" << exited
                << "), shutting down all children" << std::endl;
      g_stop_requested = 1;
      break;
    }
    usleep(100 * 1000);
  }

  TerminateChildren();
  return 0;
}
