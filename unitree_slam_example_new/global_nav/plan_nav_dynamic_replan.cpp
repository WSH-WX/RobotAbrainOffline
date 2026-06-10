#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Config {
  std::string map_path;
  std::string obstacles_json;
  std::string output_path;
  double start_x = 0.0;
  double start_y = 0.0;
  double goal_x = 0.0;
  double goal_y = 0.0;
  double goal_yaw = 0.0;
  double max_segment = 10.0;
  double dyn_margin = 0.10;
  double cooldown = 1.0;
  int confirm_frames = 3;
};

struct Map2D {
  int width = 0;
  int height = 0;
  double origin_x = 0.0;
  double origin_y = 0.0;
  double resolution = 0.1;
  std::vector<uint8_t> occ;
};

struct Node {
  int x;
  int y;
};

struct DynObstacle {
  double x;
  double y;
  double r;
};

struct DynFrame {
  double t = 0.0;
  std::vector<DynObstacle> obstacles;
};

struct ReplanEvent {
  double t = 0.0;
  int trigger_idx = 0;
  int remaining_waypoints_after_replan = 0;
  int num_dyn_obstacles = 0;
};

static void PrintUsage() {
  std::cout << "Usage:\n"
            << "  plan_nav_dynamic_replan_cpp --map <map.txt> --start <x> <y> --goal <x> <y> "
               "--obstacles-json <obs.json> --output <path.json> "
               "[--goal-yaw 0.0] [--max-segment 10.0] [--dyn-margin 0.10] [--cooldown 1.0] [--confirm-frames 3]\n";
}

static bool ParseArgs(int argc, char** argv, Config& cfg) {
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto need = [&](const std::string& n) {
      if (i + 1 >= argc) throw std::runtime_error("Missing value for " + n);
      return std::string(argv[++i]);
    };

    if (a == "--map") cfg.map_path = need(a);
    else if (a == "--obstacles-json") cfg.obstacles_json = need(a);
    else if (a == "--output") cfg.output_path = need(a);
    else if (a == "--start") {
      cfg.start_x = std::stod(need(a));
      cfg.start_y = std::stod(need(a));
    } else if (a == "--goal") {
      cfg.goal_x = std::stod(need(a));
      cfg.goal_y = std::stod(need(a));
    } else if (a == "--goal-yaw") cfg.goal_yaw = std::stod(need(a));
    else if (a == "--max-segment") cfg.max_segment = std::stod(need(a));
    else if (a == "--dyn-margin") cfg.dyn_margin = std::stod(need(a));
    else if (a == "--cooldown") cfg.cooldown = std::stod(need(a));
    else if (a == "--confirm-frames") cfg.confirm_frames = std::stoi(need(a));
    else {
      std::cerr << "Unknown arg: " << a << "\n";
      return false;
    }
  }

  return !cfg.map_path.empty() && !cfg.output_path.empty() && !cfg.obstacles_json.empty();
}

static size_t Key(int x, int y) { return (static_cast<size_t>(y) << 32) ^ static_cast<uint32_t>(x); }

static bool InBounds(const Map2D& m, int x, int y) {
  return x >= 0 && x < m.width && y >= 0 && y < m.height;
}

static bool IsFree(const Map2D& m, int x, int y) {
  return InBounds(m, x, y) && m.occ[(size_t)y * m.width + x] == 0;
}

static Node WorldToGrid(const Map2D& m, double x, double y) {
  int gx = static_cast<int>(std::floor((x - m.origin_x) / m.resolution));
  int gy = static_cast<int>(std::floor((y - m.origin_y) / m.resolution));
  return {gx, gy};
}

static std::pair<double, double> GridToWorld(const Map2D& m, int gx, int gy) {
  double x = m.origin_x + (gx + 0.5) * m.resolution;
  double y = m.origin_y + (gy + 0.5) * m.resolution;
  return {x, y};
}

static bool LoadMap(const std::string& path, Map2D& m) {
  std::ifstream ifs(path);
  if (!ifs) return false;

  ifs >> m.width >> m.height;
  ifs >> m.origin_x >> m.origin_y >> m.resolution;
  std::string row;
  std::getline(ifs, row);

  m.occ.assign((size_t)m.width * m.height, 0);
  for (int y = 0; y < m.height; ++y) {
    if (!std::getline(ifs, row)) return false;
    if ((int)row.size() < m.width) return false;
    for (int x = 0; x < m.width; ++x) {
      m.occ[(size_t)y * m.width + x] = (row[x] == '1') ? 1 : 0;
    }
  }
  return true;
}

static bool LineIsFree(const Map2D& m, Node a, Node b) {
  int x0 = a.x, y0 = a.y;
  int x1 = b.x, y1 = b.y;
  int dx = std::abs(x1 - x0), dy = std::abs(y1 - y0);
  int sx = (x0 < x1) ? 1 : -1;
  int sy = (y0 < y1) ? 1 : -1;
  int err = dx - dy;

  int x = x0, y = y0;
  while (true) {
    if (!IsFree(m, x, y)) return false;
    if (x == x1 && y == y1) break;
    int e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      x += sx;
    }
    if (e2 < dx) {
      err += dx;
      y += sy;
    }
  }
  return true;
}

static std::vector<Node> AStar(const Map2D& m, Node start, Node goal) {
  if (!IsFree(m, start.x, start.y)) throw std::runtime_error("Start is occupied/out-of-bounds");
  if (!IsFree(m, goal.x, goal.y)) throw std::runtime_error("Goal is occupied/out-of-bounds");

  struct QN {
    double f;
    Node n;
    bool operator<(const QN& o) const { return f > o.f; }
  };

  auto h = [](Node a, Node b) { return std::hypot((double)a.x - b.x, (double)a.y - b.y); };
  const int dxs[8] = {-1, 1, 0, 0, -1, -1, 1, 1};
  const int dys[8] = {0, 0, -1, 1, -1, 1, -1, 1};
  const double cst[8] = {1.0, 1.0, 1.0, 1.0, std::sqrt(2.0), std::sqrt(2.0), std::sqrt(2.0), std::sqrt(2.0)};

  std::priority_queue<QN> pq;
  std::unordered_map<size_t, double> g;
  std::unordered_map<size_t, Node> parent;
  std::unordered_map<size_t, bool> closed;

  g[Key(start.x, start.y)] = 0.0;
  pq.push({h(start, goal), start});

  while (!pq.empty()) {
    Node cur = pq.top().n;
    pq.pop();
    size_t ck = Key(cur.x, cur.y);
    if (closed[ck]) continue;
    closed[ck] = true;

    if (cur.x == goal.x && cur.y == goal.y) {
      std::vector<Node> path;
      Node t = goal;
      path.push_back(t);
      while (!(t.x == start.x && t.y == start.y)) {
        t = parent.at(Key(t.x, t.y));
        path.push_back(t);
      }
      std::reverse(path.begin(), path.end());
      return path;
    }

    for (int k = 0; k < 8; ++k) {
      int nx = cur.x + dxs[k], ny = cur.y + dys[k];
      Node nxt{nx, ny};
      if (!IsFree(m, nx, ny)) continue;
      if (dxs[k] != 0 && dys[k] != 0) {
        if (!IsFree(m, cur.x + dxs[k], cur.y) || !IsFree(m, cur.x, cur.y + dys[k])) continue;
      }

      size_t nk = Key(nx, ny);
      double ng = g[ck] + cst[k];
      auto it = g.find(nk);
      if (it == g.end() || ng < it->second) {
        g[nk] = ng;
        parent[nk] = cur;
        pq.push({ng + h(nxt, goal), nxt});
      }
    }
  }

  throw std::runtime_error("No path found");
}

static std::vector<Node> Sparsify(const Map2D& m, const std::vector<Node>& path, double max_seg_m) {
  if (path.size() <= 2) return path;
  const double max_cells = max_seg_m / m.resolution;
  std::vector<Node> out;
  out.push_back(path.front());

  size_t i = 0;
  while (i + 1 < path.size()) {
    size_t best = i + 1;
    for (size_t j = i + 1; j < path.size(); ++j) {
      double dx = (double)path[j].x - path[i].x;
      double dy = (double)path[j].y - path[i].y;
      if (std::hypot(dx, dy) > max_cells) break;
      if (LineIsFree(m, path[i], path[j])) best = j;
      else break;
    }
    out.push_back(path[best]);
    i = best;
  }
  return out;
}

static void InflateDynamic(Map2D& m, const std::vector<DynObstacle>& obs, double extra_margin) {
  auto occ0 = m.occ;
  auto idx = [&m](int x, int y) { return (size_t)y * m.width + x; };

  for (const auto& o : obs) {
    const int cells = (int)std::ceil((o.r + extra_margin) / m.resolution);
    Node c = WorldToGrid(m, o.x, o.y);

    int y0 = std::max(0, c.y - cells), y1 = std::min(m.height - 1, c.y + cells);
    int x0 = std::max(0, c.x - cells), x1 = std::min(m.width - 1, c.x + cells);

    for (int y = y0; y <= y1; ++y) {
      for (int x = x0; x <= x1; ++x) {
        int dx = x - c.x, dy = y - c.y;
        if (dx * dx + dy * dy <= cells * cells) m.occ[idx(x, y)] = 1;
      }
    }
  }
}

static bool RemainingBlocked(const Map2D& m, const std::vector<Node>& sparse, int from_idx) {
  if (from_idx >= (int)sparse.size() - 1) return false;
  for (int i = from_idx; i < (int)sparse.size() - 1; ++i) {
    if (!LineIsFree(m, sparse[i], sparse[i + 1])) return true;
  }
  return false;
}

static int NearestIndex(const std::vector<Node>& path, const Node& cur) {
  int best = 0;
  double best_d = std::numeric_limits<double>::infinity();
  for (int i = 0; i < (int)path.size(); ++i) {
    double dx = (double)path[i].x - cur.x;
    double dy = (double)path[i].y - cur.y;
    double d = dx * dx + dy * dy;
    if (d < best_d) {
      best_d = d;
      best = i;
    }
  }
  return best;
}

// Minimal JSON parser for expected schema only.
static std::vector<DynFrame> LoadFrames(const std::string& path) {
  std::ifstream ifs(path);
  if (!ifs) throw std::runtime_error("Cannot open obstacles json: " + path);
  std::stringstream buf;
  buf << ifs.rdbuf();
  std::string s = buf.str();

  std::vector<DynFrame> frames;

  std::regex frame_re(R"(\{\s*"t"\s*:\s*([-+0-9.eE]+)\s*,\s*"obstacles"\s*:\s*\[(.*?)\]\s*\})");
  std::regex obs_re(R"(\{\s*"x"\s*:\s*([-+0-9.eE]+)\s*,\s*"y"\s*:\s*([-+0-9.eE]+)(?:\s*,\s*"r"\s*:\s*([-+0-9.eE]+))?\s*\})");

  auto fb = std::sregex_iterator(s.begin(), s.end(), frame_re);
  auto fe = std::sregex_iterator();
  for (auto it = fb; it != fe; ++it) {
    DynFrame f;
    f.t = std::stod((*it)[1].str());
    std::string obs_block = (*it)[2].str();

    auto ob = std::sregex_iterator(obs_block.begin(), obs_block.end(), obs_re);
    auto oe = std::sregex_iterator();
    for (auto oit = ob; oit != oe; ++oit) {
      DynObstacle o;
      o.x = std::stod((*oit)[1].str());
      o.y = std::stod((*oit)[2].str());
      o.r = (*oit)[3].matched ? std::stod((*oit)[3].str()) : 0.3;
      f.obstacles.push_back(o);
    }
    frames.push_back(f);
  }

  std::sort(frames.begin(), frames.end(), [](const DynFrame& a, const DynFrame& b) { return a.t < b.t; });
  return frames;
}

int main(int argc, char** argv) {
  Config cfg;
  try {
    if (!ParseArgs(argc, argv, cfg)) {
      PrintUsage();
      return 1;
    }

    Map2D static_map;
    if (!LoadMap(cfg.map_path, static_map)) {
      throw std::runtime_error("Failed to load map text file: " + cfg.map_path);
    }

    Node start = WorldToGrid(static_map, cfg.start_x, cfg.start_y);
    Node goal = WorldToGrid(static_map, cfg.goal_x, cfg.goal_y);

    auto dense = AStar(static_map, start, goal);
    auto sparse = Sparsify(static_map, dense, cfg.max_segment);

    auto frames = LoadFrames(cfg.obstacles_json);

    int blocked_count = 0;
    double last_replan_t = -1e9;
    std::vector<ReplanEvent> events;
    int cur_idx = 0;

    for (const auto& f : frames) {
      Map2D dyn = static_map;
      InflateDynamic(dyn, f.obstacles, cfg.dyn_margin);

      if (sparse.empty()) break;
      cur_idx = std::min(cur_idx, (int)sparse.size() - 1);
      cur_idx = NearestIndex(sparse, sparse[cur_idx]);

      bool blocked = RemainingBlocked(dyn, sparse, cur_idx);
      blocked_count = blocked ? (blocked_count + 1) : 0;

      bool should_replan =
          blocked_count >= cfg.confirm_frames &&
          (f.t - last_replan_t) >= cfg.cooldown &&
          cur_idx < (int)sparse.size() - 1;

      if (should_replan) {
        Node repl_start = sparse[cur_idx];
        auto d2 = AStar(dyn, repl_start, goal);
        auto s2 = Sparsify(dyn, d2, cfg.max_segment);

        std::vector<Node> merged;
        for (int i = 0; i < cur_idx; ++i) merged.push_back(sparse[i]);
        if (merged.empty() || (merged.back().x != s2.front().x || merged.back().y != s2.front().y)) {
          merged.insert(merged.end(), s2.begin(), s2.end());
        } else {
          merged.insert(merged.end(), s2.begin() + 1, s2.end());
        }
        sparse.swap(merged);

        events.push_back({f.t, cur_idx, (int)sparse.size() - cur_idx, (int)f.obstacles.size()});
        last_replan_t = f.t;
        blocked_count = 0;
      }

      if (cur_idx < (int)sparse.size() - 1 && LineIsFree(dyn, sparse[cur_idx], sparse[cur_idx + 1])) {
        cur_idx++;
      }
    }

    std::filesystem::create_directories(std::filesystem::path(cfg.output_path).parent_path());
    std::ofstream ofs(cfg.output_path);
    if (!ofs) throw std::runtime_error("Cannot write output json");

    ofs << "{\n";
    ofs << "  \"map\": \"" << cfg.map_path << "\",\n";
    ofs << "  \"start\": {\"x\": " << cfg.start_x << ", \"y\": " << cfg.start_y << "},\n";
    ofs << "  \"goal\": {\"x\": " << cfg.goal_x << ", \"y\": " << cfg.goal_y
        << ", \"yaw\": " << cfg.goal_yaw << "},\n";
    ofs << "  \"max_segment\": " << cfg.max_segment << ",\n";
    ofs << "  \"num_waypoints\": " << sparse.size() << ",\n";
    ofs << "  \"num_replans\": " << events.size() << ",\n";
    ofs << "  \"replan_events\": [\n";
    for (size_t i = 0; i < events.size(); ++i) {
      const auto& e = events[i];
      ofs << "    {\"t\": " << e.t
          << ", \"trigger_idx\": " << e.trigger_idx
          << ", \"remaining_waypoints_after_replan\": " << e.remaining_waypoints_after_replan
          << ", \"num_dyn_obstacles\": " << e.num_dyn_obstacles << "}";
      if (i + 1 < events.size()) ofs << ",";
      ofs << "\n";
    }
    ofs << "  ],\n";

    ofs << "  \"waypoints\": [\n";
    for (size_t i = 0; i < sparse.size(); ++i) {
      auto [wx, wy] = GridToWorld(static_map, sparse[i].x, sparse[i].y);
      double qx = 0.0, qy = 0.0, qz = 0.0, qw = 1.0;
      if (i + 1 < sparse.size()) {
        auto [nx, ny] = GridToWorld(static_map, sparse[i + 1].x, sparse[i + 1].y);
        double yaw = std::atan2(ny - wy, nx - wx);
        qz = std::sin(yaw * 0.5);
        qw = std::cos(yaw * 0.5);
      } else {
        qz = std::sin(cfg.goal_yaw * 0.5);
        qw = std::cos(cfg.goal_yaw * 0.5);
      }

      ofs << "    {\"index\": " << i
          << ", \"x\": " << wx
          << ", \"y\": " << wy
          << ", \"z\": 0.0"
          << ", \"qx\": " << qx
          << ", \"qy\": " << qy
          << ", \"qz\": " << qz
          << ", \"qw\": " << qw << "}";
      if (i + 1 < sparse.size()) ofs << ",";
      ofs << "\n";
    }
    ofs << "  ]\n";
    ofs << "}\n";

    std::cout << "Dynamic path saved: " << cfg.output_path << "\n";
    std::cout << "Final waypoints: " << sparse.size() << ", replans: " << events.size() << "\n";

  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }

  return 0;
}
