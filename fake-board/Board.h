#include "DeviceAPI.h"

#include <memory>
#include <vector>

class Board {
  public:
    Board(int version_b);

    int initialize();

    int device_name(uint32_t id, std::string& name) const;
    int device_size(uint32_t id, size_t *sizep) const;

    int device_get(uint32_t id, uint32_t offset, uint64_t *valp) const;
    int device_put(uint32_t id, uint32_t offset, uint64_t val);

  private:
    int version_b_;

    uint32_t count_;
    std::vector< std::unique_ptr<Device> > devices_;
};
