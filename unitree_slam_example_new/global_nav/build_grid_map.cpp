#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
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

struct GroundCellStats {
  int count = 0;
  double min_z = std::numeric_limits<double>::infinity();
};

static constexpr double kGroundCellSizeM = 0.20;
static constexpr int kGroundMinCellPoints = 2;
static constexpr double kGroundHistBinSizeM = 0.05;

static void PrintUsage() {
  std::cout << "Usage:\n"
            << "  build_grid_map_cpp --input <map.pcd|map.ply> --output <map.txt> "
               "[--resolution 0.1] [--z-min -0.2] [--z-max 1.5] [--inflation-radius 0.45]\n";
  std::cout << "  --z-min/--z-max are heights relative to the estimated ground plane.\n";
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

static double Percentile(const std::vector<double>& sorted_values, double percentile) {
  if (sorted_values.empty()) {
    throw std::runtime_error("Cannot compute percentile of empty values");
  }
  const double pos = (percentile / 100.0) * (double)(sorted_values.size() - 1);
  const size_t lo = (size_t)std::floor(pos);
  const size_t hi = (size_t)std::ceil(pos);
  if (lo == hi) return sorted_values[lo];
  const double ratio = pos - (double)lo;
  return sorted_values[lo] * (1.0 - ratio) + sorted_values[hi] * ratio;
}

static double Median(std::vector<double> values) {
  if (values.empty()) {
    throw std::runtime_error("Cannot compute median of empty values");
  }
  std::sort(values.begin(), values.end());
  const size_t mid = values.size() / 2;
  if (values.size() % 2 == 1) return values[mid];
  return (values[mid - 1] + values[mid]) * 0.5;
}

static double EstimateGroundZ(const pcl::PointCloud<pcl::PointXYZ>& cloud) {
  double min_x = std::numeric_limits<double>::infinity();
  double min_y = std::numeric_limits<double>::infinity();
  size_t finite_points = 0;
  for (const auto& p : cloud.points) {
    if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) continue;
    min_x = std::min(min_x, (double)p.x);
    min_y = std::min(min_y, (double)p.y);
    ++finite_points;
  }
  if (finite_points == 0) {
    throw std::runtime_error("Cannot estimate ground height from empty point cloud");
  }

  std::unordered_map<int64_t, GroundCellStats> cells;
  cells.reserve(finite_points / 4 + 1);
  for (const auto& p : cloud.points) {
    if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) continue;
    const int64_t gx = (int64_t)std::floor(((double)p.x - min_x) / kGroundCellSizeM);
    const int64_t gy = (int64_t)std::floor(((double)p.y - min_y) / kGroundCellSizeM);
    const int64_t key = (gy << 32) ^ (gx & 0xffffffffLL);
    auto& cell = cells[key];
    ++cell.count;
    cell.min_z = std::min(cell.min_z, (double)p.z);
  }

  std::vector<double> candidates;
  candidates.reserve(cells.size());
  std::vector<double> all_cell_mins;
  all_cell_mins.reserve(cells.size());
  for (const auto& kv : cells) {
    all_cell_mins.push_back(kv.second.min_z);
    if (kv.second.count >= kGroundMinCellPoints) candidates.push_back(kv.second.min_z);
  }
  if (candidates.empty()) {
    candidates = all_cell_mins;
    std::cout << "INFO Ground estimation fallback: using all lower-envelope cells\n";
  }
  if (candidates.empty()) {
    throw std::runtime_error("No lower-envelope cells available for ground estimation");
  }

  std::sort(candidates.begin(), candidates.end());
  const double lo = Percentile(candidates, 1.0);
  const double hi = Percentile(candidates, 99.0);
  std::vector<double> trimmed;
  trimmed.reserve(candidates.size());
  for (double z : candidates) {
    if (z >= lo && z <= hi) trimmed.push_back(z);
  }
  if (trimmed.empty()) trimmed = candidates;

  const double min_z = *std::min_element(trimmed.begin(), trimmed.end());
  const double max_z = *std::max_element(trimmed.begin(), trimmed.end());
  const double bin_start = std::floor(min_z / kGroundHistBinSizeM) * kGroundHistBinSizeM;
  const int bin_count = std::max(1, (int)std::ceil((max_z - bin_start) / kGroundHistBinSizeM) + 1);
  std::vector<int> hist((size_t)bin_count, 0);
  for (double z : trimmed) {
    int bin = (int)std::floor((z - bin_start) / kGroundHistBinSizeM);
    bin = std::max(0, std::min(bin_count - 1, bin));
    ++hist[(size_t)bin];
  }

  const int best_bin = (int)std::distance(hist.begin(), std::max_element(hist.begin(), hist.end()));
  const double mode_lo = bin_start + (double)best_bin * kGroundHistBinSizeM;
  const double mode_hi = mode_lo + kGroundHistBinSizeM;
  std::vector<double> mode_values;
  for (double z : trimmed) {
    if (z >= mode_lo && z < mode_hi) mode_values.push_back(z);
  }

  const double ground_z = Median(mode_values.empty() ? trimmed : mode_values);
  std::cout << "INFO Estimated ground_z=" << ground_z << " from lower envelope cells=" << all_cell_mins.size()
            << " candidates=" << candidates.size() << " mode_bin=[" << mode_lo << ", " << mode_hi << ")\n";
  return ground_z;
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
  if (cfg.z_min > cfg.z_max) {
    std::cerr << "Invalid height range: --z-min must be <= --z-max\n";
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

  std::cout << "INFO Build occupancy map input=" << cfg.input_path << ", output=" << cfg.output_path
            << ", resolution=" << cfg.resolution << ", relative_z_min=" << cfg.z_min
            << ", relative_z_max=" << cfg.z_max << ", inflation_radius=" << cfg.inflation_radius << "\n";

  double ground_z = 0.0;
  try {
    ground_z = EstimateGroundZ(cloud);
  } catch (const std::exception& e) {
    std::cerr << "Failed to estimate ground height for " << cfg.input_path << ": " << e.what() << "\n";
    return 1;
  }
  const double abs_z_min = ground_z + cfg.z_min;
  const double abs_z_max = ground_z + cfg.z_max;
  std::cout << "INFO Applying ground-relative height filter ground_z=" << ground_z
            << ", relative_z=[" << cfg.z_min << ", " << cfg.z_max << "]"
            << ", absolute_z=[" << abs_z_min << ", " << abs_z_max << "]\n";

  std::vector<pcl::PointXYZ> pts;
  pts.reserve(cloud.size());
  for (const auto& p : cloud.points) {
    if (p.z >= abs_z_min && p.z <= abs_z_max) pts.push_back(p);
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
  std::cout << "Estimated ground z: " << ground_z << "\n";
  std::cout << "Absolute z filter: (" << abs_z_min << ", " << abs_z_max << ")\n";

  return 0;
}
