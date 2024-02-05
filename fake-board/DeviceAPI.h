#include <string>

class Device {
  public:
    Device() = default;
    virtual ~Device() = default;

    virtual int initialize() = 0;

    virtual const std::string& name() const = 0;
    virtual size_t size() const = 0;
    virtual int read(uint32_t offset, uint64_t *valp) const = 0;
    virtual int write(uint32_t offset, uint64_t val) = 0;
};
