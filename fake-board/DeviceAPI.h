//
// And abstract interface for basic interactions with a device
// containing a region of memory.
//
// 

class Device {
  public:
    Device() = default;
    virtual ~Device() = default;

    virtual int initialize() = 0;

    virtual const std::string_view name() const = 0;
    virtual size_t size() const = 0;

    // Only a single memory location can be accessed.
    virtual int read(size_t offset, uint64_t *valp) const = 0;
    virtual int write(size_t offset, uint64_t val) = 0;
};
