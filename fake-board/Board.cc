#include <cerrno>
#include <cstdlib>
#include <iostream>

#include "Board.h"

//
// A few notes on this demo example:
//
// 1. The "goto out" pattern is used since even in C++, a single exit
//    point is cleaner. It's less relevant when object destruction
//    will release resources when an object goes out of scope. For
//    resources not wrapped by a class, for example a raw file
//    descriptor, like a pthread_mutex_t, etc., it is better to also
//    have a single point where resources are released. The "goto out"
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
// 3. There are likely more C++11 specific features that could be
//    used, but I'm not sufficiently aware at this time. I'm not sure
//    whether "auto" function returns are good style, so I didn't even
//    try to use them anywhere.
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
    RomConfig(const std::string& name);
    virtual ~RomConfig() = default;

    virtual const std::string& name() const;
    virtual int initialize();

    virtual size_t size() const;
    virtual int read(uint32_t offset, uint64_t *valp) const;
    virtual int write(uint32_t offset, const uint64_t val);

  private:
    const std::string name_;

    static const size_t MEM_SIZE_ = 5;
    uint64_t memory_[MEM_SIZE_];
};

RomConfig::RomConfig(const std::string& name)
    : name_(name)
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
    std::cout << "Initializing device " << name_ << "...\n";

    return 0;
}

const std::string&
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
RomConfig::read(uint32_t offset, uint64_t *valp) const
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
RomConfig::write(uint32_t offset, uint64_t val)
{
    int err = 0;

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
    Store(const std::string& name, int version);
    virtual ~Store() = default;

    virtual const std::string& name() const;
    virtual int initialize();

    virtual size_t size() const;
    virtual int read(uint32_t offset, uint64_t *valp) const;
    virtual int write(uint32_t offset, uint64_t val);

  private:
    const std::string name_;
    const int version_;

    static const size_t MEM_SIZE_ = 10;
    uint64_t memory_[MEM_SIZE_];
};

Store::Store(const std::string& name, int version)
    : name_(name + "." + std::to_string(version)),
      version_(version)
{
    //
    // The ctor wouldn't touch the hardware and error checks are
    // deferred until initialize.
    //
}

const std::string&
Store::name() const
{
    return name_;
}

int
Store::initialize()
{
    int err = 0;

    std::cout << "Initializing " << name_ << "...\n";

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
Store::read(uint32_t offset, uint64_t *valp) const
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
Store::write(uint32_t offset, uint64_t val)
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
    std::cout << "Initializing board...\n";

    //
    // A specific board knows which devices are present.
    //
    count_ = NUM_DEVICES;

    devices_.push_back(std::unique_ptr<Device>(new RomConfig("Acme ROM")));
    devices_.push_back(std::unique_ptr<Device>(new Store(
						   "Beta Memory",
						   version_b_)));

    int err = 0;
    for (auto device = devices_.begin(); device != devices_.end(); ++device) {
	err = (*device)->initialize();
        if (err != 0) {
	    std::cout << (*device)->name() << " initialization failed\n";
	    break;
        }
    }

    return err;
}

int
Board::device_name(uint32_t id, std::string& name) const
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
Board::device_get(uint32_t id, uint32_t offset, uint64_t *valp) const
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
Board::device_put(uint32_t id, uint32_t offset, uint64_t val)
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
