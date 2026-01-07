#include <cerrno>
#include <cstring>
#include <format>
#include <iostream>
#include <string_view>

#include "Board.h"

//
// A few notes on this demo example:
//
// 1. The "goto out" pattern is used since even in C++, a single exit
//    point is cleaner. It's less relevant when object destruction
//    will release resources when an object goes out of scope. For
//    resources not wrapped by a class, for example a raw file
//    descriptor, a pthread_mutex_t, etc., it is better to also have a
//    single point where resources are released. The "goto out"
//    pattern is also future proof. If a variable does contain a
//    resource needing explicit releasing, then there is no need to
//    track down all of the "return" statements and update the code
//    prior to them. But, I certainly would follow coding standards
//    and conventions when different.
//
// 2. Error number choices were for distinguishing specific
//    errors. Using EINVAL for everything doesn't make for a good
//    demo.
//
// 3. There are likely more modern C++XX specific features that could
//    be used, but I'm not sufficiently aware at this time.
//
// 4. The output messages exist purely for the purpose of the
//    demo. These could be log messages in some real
//    drivers. Likewise, failures could, or would, be logged in some
//    of these methods in addition to returning an error code.
//
// 5. An actual board with attached devices would have the board and
//    device implememtations in separate files.
//

//----------------------------------------------------------------------
//  RomConfig - readonly example
//
class RomConfig : public Device
{
  public:
    RomConfig(const std::string_view name);
    ~RomConfig() override = default;

    const std::string_view name() const override;
    int initialize() override;

    size_t size() const override;
    int read(size_t offset, uint64_t *valp) const override;
    int write(size_t offset, const uint64_t val) override;

  private:
    const std::string name_;

    static constexpr size_t MEM_SIZE_ = 5;
    uint64_t memory_[MEM_SIZE_];
};

RomConfig::RomConfig(const std::string_view name)
    : name_{ name }
{
    //
    // The ctor wouldn't touch the hardware ... but we need to have a
    // loaded ROM.
    //
    for (size_t i = 0; i < MEM_SIZE_; ++i) {
	memory_[i] = i;
    }
}

int
RomConfig::initialize()
{
    std::ostream_iterator<char> out(std::cout);
    
    std::format_to(out, "Initializing device {}...\n", name_);

    return 0;
}

const std::string_view
RomConfig::name() const
{
    return name_;
}

size_t
RomConfig::size() const
{
    return MEM_SIZE_;
}

//
// *valp could be set to a well-known value instead of untouched on
// error.
//
int
RomConfig::read(size_t offset, uint64_t *valp) const
{
    auto err = 0;

    if (offset >= MEM_SIZE_) {
	err = EINVAL;
	goto out;
    }

    *valp = memory_[offset];

out:

    return err;
}

int
RomConfig::write(size_t offset, __attribute__((unused))uint64_t val)
{
    auto err = 0;

    if (offset >= MEM_SIZE_) {
	err = EINVAL;
	goto out;
    }
    
    err = EPERM;

out:

    return err;
}

//----------------------------------------------------------------------
// Store - read/write example

class Store : public Device
{
  public:
    Store(const std::string_view name, int version);
    ~Store() override = default;

    const std::string_view name() const override;
    int initialize() override;

    size_t size() const override;
    int read(size_t offset, uint64_t *valp) const override;
    int write(size_t offset, uint64_t val) override;

  private:
    const std::string name_;
    const int version_;

    static constexpr size_t MEM_SIZE_ = 10;
    uint64_t memory_[MEM_SIZE_];
};

Store::Store(const std::string_view name, int version)
    : name_{ std::string{ name } + "." + std::to_string(version) },
      version_{ version }
{
    //
    // The ctor wouldn't touch the hardware and error checks are
    // deferred until initialize.
    //
}

const std::string_view
Store::name() const
{
    return name_;
}

int
Store::initialize()
{
    auto err = 0;
    std::ostream_iterator<char> out(std::cout);
    
    std::format_to(out, "Initializing {}...\n", name_);

    // Handle deferred error checking.
    if (version_ > 3) {
	err = ENXIO;
	goto out;
    }

    // A real device would have more complex initialization.
    (void) memset(memory_, 0, sizeof memory_);

out:

    return err;
}

size_t
Store::size() const
{
    return MEM_SIZE_;
}

//
// *valp could be set to a well-known value instead of untouched on
// error.
//
int
Store::read(size_t offset, uint64_t *valp) const
{
    int err = 0;

    if (offset >= MEM_SIZE_) {
	err = EINVAL;
	goto out;
    }

    *valp = memory_[offset];

out:

    return err;
}

int
Store::write(size_t offset, uint64_t val)
{
    int err = 0;

    if (offset >= MEM_SIZE_) {
	err = EINVAL;
	goto out;
    }
    
    memory_[offset] = val;

out:

    return err;
}

//----------------------------------------------------------------------
//
// A board with 2 devices
//

namespace {
    const uint32_t NUM_DEVICES = 2U;
}

Board::Board(int version_b)
    : version_b_(version_b),
      count_(0)
{
}

int
Board::initialize()
{
    std::ostream_iterator<char> out(std::cout);
    
    std::format_to(out, "Initializing board...\n");

    //
    // A specific board knows which devices are present.
    //
    count_ = NUM_DEVICES;

    devices_.push_back(std::unique_ptr<Device>(new RomConfig("Acme ROM")));
    devices_.push_back(std::unique_ptr<Device>(new Store(
						   "Beta Memory",
						   version_b_)));

    int err = 0;
    for (auto& device : devices_) {
	err = device->initialize();
        if (err != 0) {
            std::format_to(out, "{} initialization failed\n", device->name());
            break;
        }
    }

    return err;
}

int
Board::device_name(uint32_t id, std::string_view& name) const
{
    int err = 0;

    if (id > count_) {
        err = ENODEV;
        goto out;
    }

    name = devices_[id]->name();

out:

    return err;
}

int
Board::device_size(uint32_t id, size_t *sizep) const
{
    int err = 0;

    if (id > count_) {
        err = ENODEV;
        goto out;
    }

    *sizep = devices_[id]->size();

out:

    return err;
}

int
Board::device_get(uint32_t id, size_t offset, uint64_t *valp) const
{
    int err = 0;

    if (id > count_) {
        err = ENODEV;
        goto out;
    }

    err = devices_[id]->read(offset, valp);

out:

    return err;
}

int
Board::device_put(uint32_t id, size_t offset, uint64_t val)
{
    int err = 0;

    if (id > count_) {
        err = ENODEV;
        goto out;
    }

    err = devices_[id]->write(offset, val);

out:

    return err;
}
