#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include <pcl/io/pcd_io.h>
#include <pcl/io/ply_io.h>
#include <pcl/point_types.h>

struct Config {
  std::string input_path;
  std::string output_path;
  double resolution = 0.10;
  double z_min = -0.20;
  double z_max = 1.50;
  double inflation_radius = 0.45;
};

static void PrintUsage() {
  std::cout << "Usage:\n"
            << "  build_grid_map_cpp --input <map.pcd|map.ply> --output <map.txt> "
               "[--resolution 0.1] [--z-min -0.2] [--z-max 1.5] [--inflation-radius 0.45]\n";
}

static bool ParseArgs(int argc, char** argv, Config& cfg) {
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto need = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) {
        throw std::runtime_error("Missing value for " + name);
      }
      return argv[++i];
    };

    if (a == "--input") cfg.input_path = need(a);
    else if (a == "--output") cfg.output_path = need(a);
    else if (a == "--resolution") cfg.resolution = std::stod(need(a));
    else if (a == "--z-min") cfg.z_min = std::stod(need(a));
    else if (a == "--z-max") cfg.z_max = std::stod(need(a));
    else if (a == "--inflation-radius") cfg.inflation_radius = std::stod(need(a));
    else {
      std::cerr << "Unknown arg: " << a << "\n";
      return false;
    }
  }

  return !cfg.input_path.empty() && !cfg.output_path.empty();
}

int main(int argc, char** argv) {
  Config cfg;
  try {
    if (!ParseArgs(argc, argv, cfg)) {
      PrintUsage();
      return 1;
    }
  } catch (const std::exception& e) {
    std::cerr << e.what() << "\n";
    PrintUsage();
    return 1;
  }

  pcl::PointCloud<pcl::PointXYZ> cloud;
  const auto ext = std::filesystem::path(cfg.input_path).extension().string();
  int ret = -1;
  if (ext == ".pcd") {
    ret = pcl::io::loadPCDFile(cfg.input_path, cloud);
  } else if (ext == ".ply") {
    ret = pcl::io::loadPLYFile(cfg.input_path, cloud);
  } else {
    std::cerr << "Unsupported input extension: " << ext << "\n";
    return 1;
  }

  if (ret < 0 || cloud.empty()) {
    std::cerr << "Failed to load point cloud: " << cfg.input_path << "\n";
    return 1;
  }

  std::vector<pcl::PointXYZ> pts;
  pts.reserve(cloud.size());
  for (const auto& p : cloud.points) {
    if (p.z >= cfg.z_min && p.z <= cfg.z_max) pts.push_back(p);
  }

  if (pts.empty()) {
    std::cerr << "No points after z filter, relax --z-min/--z-max\n";
    return 1;
  }

  double min_x = pts[0].x, max_x = pts[0].x;
  double min_y = pts[0].y, max_y = pts[0].y;
  for (const auto& p : pts) {
    min_x = std::min(min_x, (double)p.x);
    max_x = std::max(max_x, (double)p.x);
    min_y = std::min(min_y, (double)p.y);
    max_y = std::max(max_y, (double)p.y);
  }

  const int width = (int)std::ceil((max_x - min_x) / cfg.resolution) + 1;
  const int height = (int)std::ceil((max_y - min_y) / cfg.resolution) + 1;
  std::vector<uint8_t> occ((size_t)width * height, 0);

  auto idx = [width](int x, int y) { return (size_t)y * width + x; };

  for (const auto& p : pts) {
    int gx = (int)std::floor((p.x - min_x) / cfg.resolution);
    int gy = (int)std::floor((p.y - min_y) / cfg.resolution);
    if (gx >= 0 && gx < width && gy >= 0 && gy < height) {
      occ[idx(gx, gy)] = 1;
    }
  }

  const int inflate_cells = (int)std::ceil(cfg.inflation_radius / cfg.resolution);
  if (inflate_cells > 0) {
    auto inflated = occ;
    for (int y = 0; y < height; ++y) {
      for (int x = 0; x < width; ++x) {
        if (occ[idx(x, y)] == 0) continue;
        int y0 = std::max(0, y - inflate_cells);
        int y1 = std::min(height - 1, y + inflate_cells);
        int x0 = std::max(0, x - inflate_cells);
        int x1 = std::min(width - 1, x + inflate_cells);
        for (int yy = y0; yy <= y1; ++yy) {
          for (int xx = x0; xx <= x1; ++xx) {
            int dx = xx - x;
            int dy = yy - y;
            if (dx * dx + dy * dy <= inflate_cells * inflate_cells) {
              inflated[idx(xx, yy)] = 1;
            }
          }
        }
      }
    }
    occ.swap(inflated);
  }

  std::filesystem::create_directories(std::filesystem::path(cfg.output_path).parent_path());
  std::ofstream ofs(cfg.output_path);
  if (!ofs) {
    std::cerr << "Cannot write: " << cfg.output_path << "\n";
    return 1;
  }

  // Custom map text format:
  // line1: width height
  // line2: origin_x origin_y resolution
  // line3+: each row as 0/1 chars
  ofs << width << " " << height << "\n";
  ofs << min_x << " " << min_y << " " << cfg.resolution << "\n";
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) ofs << (occ[idx(x, y)] ? '1' : '0');
    ofs << "\n";
  }

  std::cout << "Saved map: " << cfg.output_path << "\n";
  std::cout << "Grid size: " << width << " x " << height << "\n";
  std::cout << "Origin: (" << min_x << ", " << min_y << "), resolution=" << cfg.resolution << "\n";

  return 0;
}
