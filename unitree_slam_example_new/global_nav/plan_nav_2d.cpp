#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Config {
  std::string map_path;
  std::string output_path;
  double start_x = 0.0;
  double start_y = 0.0;
  double goal_x = 0.0;
  double goal_y = 0.0;
  double goal_yaw = 0.0;
  double max_segment = 10.0;
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

static void PrintUsage() {
  std::cout << "Usage:\n"
            << "  plan_nav_2d_cpp --map <map.txt> --start <x> <y> --goal <x> <y> "
               "--output <path.json> [--goal-yaw 0.0] [--max-segment 10.0]\n";
}

static bool ParseArgs(int argc, char** argv, Config& cfg) {
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto need = [&](const std::string& n) {
      if (i + 1 >= argc) throw std::runtime_error("Missing value for " + n);
      return std::string(argv[++i]);
    };

    if (a == "--map") cfg.map_path = need(a);
    else if (a == "--output") cfg.output_path = need(a);
    else if (a == "--start") {
      cfg.start_x = std::stod(need(a));
      cfg.start_y = std::stod(need(a));
    } else if (a == "--goal") {
      cfg.goal_x = std::stod(need(a));
      cfg.goal_y = std::stod(need(a));
    } else if (a == "--goal-yaw") cfg.goal_yaw = std::stod(need(a));
    else if (a == "--max-segment") cfg.max_segment = std::stod(need(a));
    else {
      std::cerr << "Unknown arg: " << a << "\n";
      return false;
    }
  }
  return !cfg.map_path.empty() && !cfg.output_path.empty();
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
  std::getline(ifs, row);  // consume trailing newline

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
  int dx = std::abs(x1 - x0);
  int dy = std::abs(y1 - y0);
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

  size_t sk = Key(start.x, start.y);
  g[sk] = 0.0;
  pq.push({h(start, goal), start});

  std::unordered_map<size_t, bool> closed;

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
      int nx = cur.x + dxs[k];
      int ny = cur.y + dys[k];
      Node nxt{nx, ny};
      if (!IsFree(m, nx, ny)) continue;

      // avoid corner cutting
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
      double dist = std::hypot(dx, dy);
      if (dist > max_cells) break;
      if (LineIsFree(m, path[i], path[j])) best = j;
      else break;
    }
    out.push_back(path[best]);
    i = best;
  }

  return out;
}

int main(int argc, char** argv) {
  Config cfg;
  try {
    if (!ParseArgs(argc, argv, cfg)) {
      PrintUsage();
      return 1;
    }

    Map2D map;
    if (!LoadMap(cfg.map_path, map)) {
      throw std::runtime_error("Failed to load map text file: " + cfg.map_path);
    }

    Node s = WorldToGrid(map, cfg.start_x, cfg.start_y);
    Node g = WorldToGrid(map, cfg.goal_x, cfg.goal_y);

    auto dense = AStar(map, s, g);
    auto sparse = Sparsify(map, dense, cfg.max_segment);

    std::filesystem::create_directories(std::filesystem::path(cfg.output_path).parent_path());
    std::ofstream ofs(cfg.output_path);
    if (!ofs) throw std::runtime_error("Cannot write output json");

    ofs << "{\n";
    ofs << "  \"map\": \"" << cfg.map_path << "\",\n";
    ofs << "  \"start\": {\"x\": " << cfg.start_x << ", \"y\": " << cfg.start_y << "},\n";
    ofs << "  \"goal\": {\"x\": " << cfg.goal_x << ", \"y\": " << cfg.goal_y << ", \"yaw\": " << cfg.goal_yaw << "},\n";
    ofs << "  \"max_segment\": " << cfg.max_segment << ",\n";
    ofs << "  \"num_waypoints\": " << sparse.size() << ",\n";
    ofs << "  \"waypoints\": [\n";

    for (size_t i = 0; i < sparse.size(); ++i) {
      auto [wx, wy] = GridToWorld(map, sparse[i].x, sparse[i].y);
      double qx = 0.0, qy = 0.0, qz = 0.0, qw = 1.0;

      if (i + 1 < sparse.size()) {
        auto [nx, ny] = GridToWorld(map, sparse[i + 1].x, sparse[i + 1].y);
        double yaw = std::atan2(ny - wy, nx - wx);
        qz = std::sin(yaw * 0.5);
        qw = std::cos(yaw * 0.5);
      } else {
        qz = std::sin(cfg.goal_yaw * 0.5);
        qw = std::cos(cfg.goal_yaw * 0.5);
      }

      ofs << "    {\"index\": " << i << ", \"x\": " << wx << ", \"y\": " << wy
          << ", \"z\": 0.0, \"qx\": " << qx << ", \"qy\": " << qy
          << ", \"qz\": " << qz << ", \"qw\": " << qw << "}";
      if (i + 1 < sparse.size()) ofs << ",";
      ofs << "\n";
    }

    ofs << "  ]\n";
    ofs << "}\n";

    std::cout << "Path saved: " << cfg.output_path << "\n";
    std::cout << "Dense nodes: " << dense.size() << ", sparse waypoints: " << sparse.size() << "\n";

  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }

  return 0;
}
