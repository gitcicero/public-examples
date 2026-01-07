//
// Instead of using make(1), the progam can be manually compiled.
//
// On macOS, build and run using:
//
// c++ -std=c++20 -c -o Board.o Board.cc && c++ -std=c++20 -o main main.cc Board.o && ./main
//
// Or, consult the Makefile.
//

// Instead of using something like CxxTest, just use assert().
#include <cassert>

#include <cerrno>
#include <cstring>
#include <format>
#include <iostream>
#include <memory>
#include <string_view>

#include "Board.h"

namespace {
    constexpr uint32_t ROM_ID = 0U;

    constexpr uint32_t BETA_ID = 1U;
    constexpr uint32_t BETA_VERSION = 3U;

    // This is for unit tests.
    constexpr uint32_t BASE_INVALID_ID = 11U;
}

static void test_good_init()
{
    constexpr std::string_view label{ "good_init" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    const auto err = board->initialize();
    assert(err == 0);

    std::format_to(out, "{} PASSED\n\n", label);
}

static void test_bad_init()
{
    constexpr std::string_view label{ "bad_init" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BASE_INVALID_ID + 1));

    const auto err = board->initialize();

    assert(err == ENXIO);
    std::format_to(out, "{} initialization failed: {}\n", label, std::strerror(err));

    std::format_to(out, "{} PASSED\n\n", label);
}

static void test_happy_paths()
{
    constexpr std::string_view label { "happy_paths" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    auto err = board->initialize();
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

    std::format_to(out, "{} PASSED\n\n", label);
}

static void test_put_readonly()
{
    constexpr std::string_view label{ "put_readonly" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    auto err = board->initialize();
    assert(err == 0);

    std::string_view rom_name;
    err = board->device_name(ROM_ID, rom_name);
    assert(err == 0);

    err = board->device_put(ROM_ID, 1, 123);
    assert(err == EPERM);
    std::format_to(out, "{} {} put failed: {}\n", label, rom_name, std::strerror(err));

    size_t size;
    err = board->device_size(ROM_ID, &size);
    assert(err == 0);

    // Out of range.
    err = board->device_put(ROM_ID, size + 1, 123);
    assert(err == EINVAL);
    std::format_to(out, "{} {} put failed: {}\n", label, rom_name, std::strerror(err));

    //
    // Simple and fine place for invalid device tests. Less chatter
    // and only emit one message.
    //
    uint64_t value;
    std::string_view name;
    constexpr auto invalid_id { BASE_INVALID_ID + 11 };

    err = board->device_name(invalid_id, name);
    assert(err == ENODEV);
    err = board->device_size(invalid_id + 1, &size);
    assert(err == ENODEV);
    err = board->device_get(invalid_id + 2, 1, &value);
    assert(err == ENODEV);
    err = board->device_put(invalid_id + 3, 1, 456);
    assert(err == ENODEV);
    std::format_to(out, "{} {} put failed: {}\n", label, rom_name, std::strerror(err));

    std::format_to(out, "{} PASSED\n\n", label);
}

static void test_read_mem_errors()
{
    constexpr std::string_view label{ "read_mem_errors" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    auto err = board->initialize();
    assert(err == 0);

    size_t size;
    err = board->device_size(BETA_ID, &size);
    assert(err == 0);

    std::string_view beta_name;
    err = board->device_name(BETA_ID, beta_name);
    assert(err == 0);

    uint64_t value;
    err = board->device_get(BASE_INVALID_ID, size + 8, &value);
    assert(err == ENODEV);
    std::format_to(out, "{} {} get failed: {}\n", label, beta_name, std::strerror(err));

    err = board->device_get(BETA_ID, size + 8, &value);
    assert(err == EINVAL);
    std::format_to(out, "{} {} get failed: {}\n", label, beta_name, std::strerror(err));

    std::format_to(out, "{} PASSED\n\n", label);
}

static void test_write_mem_errors()
{
    constexpr std::string_view label{ "write_mem_errors" };
    std::ostream_iterator<char> out(std::cout);

    std::format_to(out, "Test {}...\n", label);

    std::unique_ptr<Board> board(new Board(BETA_VERSION));

    auto err = board->initialize();
    assert(err == 0);

    size_t size;
    err = board->device_size(BETA_ID, &size);
    assert(err == 0);

    std::string_view beta_name;
    err = board->device_name(BETA_ID, beta_name);
    assert(err == 0);

    uint64_t value = 0xcafe;
    err = board->device_put(BASE_INVALID_ID, size + 8, value);
    assert(err == ENODEV);
    std::format_to(out, "{} {} put failed: {}\n", label, beta_name, std::strerror(err));

    err = board->device_put(BETA_ID, size + 8, value);
    assert(err == EINVAL);
    std::format_to(out, "{} {} put failed: {}\n", label, beta_name, std::strerror(err));

    std::format_to(out, "{} PASSED\n\n", label);
}

int main(__attribute__((unused))int argc, __attribute__((unused))char **argv)
{
    test_good_init();
    test_bad_init();
    test_happy_paths();
    test_put_readonly();
    test_read_mem_errors();
    test_write_mem_errors();
}
