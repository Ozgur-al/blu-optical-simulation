cmake_minimum_required(VERSION 3.18)
project(blu_tracer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

execute_process(
    COMMAND "${Python_EXECUTABLE}" -c "import numpy; print(numpy.get_include())"
    OUTPUT_VARIABLE NUMPY_INCLUDE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

pybind11_add_module(blu_tracer MODULE
    src/blu_tracer.cpp
    src/intersect.cpp
    src/material.cpp
    src/sampling.cpp
    src/bvh.cpp
)

target_include_directories(blu_tracer PRIVATE src ${NUMPY_INCLUDE_DIR})

if(MSVC)
    target_compile_options(blu_tracer PRIVATE /O2 /fp:fast /W3)
endif()

install(TARGETS blu_tracer DESTINATION backlight_sim/sim)
