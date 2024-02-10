//
// A Makefile is an unnecessary complication.
//
// On macOS I built and ran using:
//
// c++ -std=c++11 -c -o Board.o Board.cc && c++ -std=c++11 -o main main.cc Board.o && ./main
//

// Instead of using something like CxxTest, just use assert().
#include <cassert>

#include <cerrno>
#include <cstring>
#include <iostream>
#include <memory>

#include "Board.h"

namespace {
    const uint32_t ROM_ID = 0U;

    const uint32_t BETA_ID = 1U;
    const uint32_t BETA_VERSION = 3U;
}

void test_good_init()
{
    std::string label("good_init");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    const int err = board->initialize();
    assert(err == 0);

    std::cout << label << " PASSED\n\n";
}

void test_bad_init()
{
    const std::string label("bad_init");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(12));

    const int err = board->initialize();

    assert(err == ENXIO);
    std::cout << label << " initialization failed: " << std::strerror(err)
	      << "\n";

    std::cout << label << " PASSED\n\n";
}

void test_happy_paths()
{
    const std::string label("happy_paths");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    int err = board->initialize();
    assert(err == 0);

    uint64_t value;
    err = board->device_get(ROM_ID, 3, &value);
    assert(err == 0);
    assert(value == 3);

    size_t dev2_size;
    err = board->device_size(BETA_ID, &dev2_size);
    assert(err == 0);

    for (decltype(dev2_size) i = 0; i < dev2_size; ++i) {
	value = 0xfeedface;
	err = board->device_get(BETA_ID, i, &value);
	assert(err == 0);
	assert(value == 0);
    }

    value = 0x12345678;
    err = board->device_put(BETA_ID, 7, value);
    assert(err == 0);

    uint64_t fetched;
    err = board->device_get(BETA_ID, 7, &fetched);
    assert(err == 0);
    assert(value == fetched);

    std::cout << label << " PASSED\n\n";
}

void test_put_readonly()
{
    const std::string label("put_readonly");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    int err = board->initialize();
    assert(err == 0);

    std::string rom_name;
    err = board->device_name(ROM_ID, rom_name);
    assert(err == 0);

    err = board->device_put(ROM_ID, 1, 123);
    assert(err == EPERM);
    std::cout << label << " " << rom_name << " put failed: "
	      << std::strerror(err) << "\n";

    size_t size;
    err = board->device_size(ROM_ID, &size);
    assert(err == 0);

    // Out of range.
    err = board->device_put(ROM_ID, size + 1, 123);
    assert(err == EINVAL);
    std::cout << label << " " << rom_name << " put failed: "
	      << std::strerror(err) << "\n";

    //
    // Simple and fine place for an invalid device tests.  Less
    // chatter and only emit one message.
    //
    uint64_t value;
    std::string name;

    err = board->device_name(11, name);
    assert(err == ENODEV);
    err = board->device_size(12, &size);
    assert(err == ENODEV);
    err = board->device_get(13, 1, &value);
    assert(err == ENODEV);
    err = board->device_put(14, 1, 456);
    assert(err == ENODEV);
    std::cout << label << " " << rom_name << " put failed: "
	      << std::strerror(err) << "\n";

    std::cout << label << " PASSED\n\n";
}

void test_read_mem_errors()
{
    const std::string label("read_mem_errors");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    int err = board->initialize();
    assert(err == 0);

    size_t size;
    err = board->device_size(BETA_ID, &size);
    assert(err == 0);

    std::string beta_name;
    err = board->device_name(BETA_ID, beta_name);
    assert(err == 0);

    uint64_t value;
    err = board->device_get(6, size + 8, &value);
    assert(err == ENODEV);
    std::cout << label << " " <<  beta_name << " get failed: "
	      << std::strerror(err) << "\n";

    err = board->device_get(BETA_ID, size + 8, &value);
    assert(err == EINVAL);
    std::cout << label << " " << beta_name << " get failed: "
	      << std::strerror(err) << "\n";

    std::cout << label << " PASSED\n\n";
}

void test_write_mem_errors()
{
    const std::string label("write_mem_errors");

    std::cout << "Test " << label << "...\n";

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    int err = board->initialize();
    assert(err == 0);

    size_t size;
    err = board->device_size(BETA_ID, &size);
    assert(err == 0);

    std::string beta_name;
    err = board->device_name(BETA_ID, beta_name);
    assert(err == 0);

    uint64_t value = 0xcafe;
    err = board->device_put(6, size + 8, value);
    assert(err == ENODEV);
    std::cout << label << " " <<  beta_name << " put failed: "
	      << std::strerror(err) << "\n";

    err = board->device_put(BETA_ID, size + 8, value);
    assert(err == EINVAL);
    std::cout << label << " " << beta_name << " put failed: "
	      << std::strerror(err) << "\n";

    std::cout << label << " PASSED\n\n";
}

int main(int argc, char **argv)
{
    test_good_init();
    test_bad_init();
    test_happy_paths();
    test_put_readonly();
    test_read_mem_errors();
    test_write_mem_errors();
}
