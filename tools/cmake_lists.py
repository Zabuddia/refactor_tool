from __future__ import annotations
from pathlib import Path
from typing import Iterable
from io import StringIO

def _block_set(var: str, items: Iterable[str]) -> str:
    items = [Path(p).as_posix() for p in items]
    buf = StringIO()
    buf.write(f"set({var}\n")
    for it in items:
        buf.write(f"  {it}\n")
    buf.write(")\n\n")
    return buf.getvalue()

def write_cmakelists(
    project_name: str,
    c_files: Iterable[str],
    cpp_files: Iterable[str],
    output: str = "CMakeLists.txt",
) -> None:
    out = StringIO()

    # Header & options
    out.write(
        "cmake_minimum_required(VERSION 3.24)\n\n"
        f"project({project_name}\n"
        "  VERSION 0.1.0\n"
        "  LANGUAGES C CXX\n"
        ")\n\n"
        "set(CMAKE_C_STANDARD 11)\n"
        "set(CMAKE_C_STANDARD_REQUIRED ON)\n"
        "set(CMAKE_C_EXTENSIONS OFF)\n\n"
        "set(CMAKE_CXX_STANDARD 17)\n"
        "set(CMAKE_CXX_STANDARD_REQUIRED ON)\n"
        "set(CMAKE_CXX_EXTENSIONS OFF)\n\n"
        'option(BUILD_TESTING                "Enable CTest & test targets"              ON)\n'
        'option(ENABLE_WARNINGS_AS_ERRORS    "Treat warnings as errors for *your* code" OFF)\n'
        'option(ENABLE_IPP                   "Link Intel oneAPI IPP if found"           ON)\n'
        'option(ENABLE_LTO                   "Enable link-time optimization (IPO)"      OFF)\n'
        'option(ENABLE_ASAN_UBSAN            "Enable ASan+UBSan on non-MSVC Debug"      OFF)\n'
        'option(ENABLE_COVERAGE              "Enable coverage flags on GNU/Clang"       OFF)\n\n'
        f"set(MAIN_TARGET {project_name}-test)\n\n"
    )

    # Sources
    out.write(_block_set("SRC_C", c_files))
    out.write(_block_set("SRC_CXX", cpp_files))
    out.write("add_executable(${MAIN_TARGET} ${SRC_C} ${SRC_CXX})\n\n")

    # Compile defs / includes
    out.write(
        "target_compile_definitions(${MAIN_TARGET} PRIVATE _USE_MATH_DEFINES)\n"
        "target_include_directories(${MAIN_TARGET} PRIVATE\n"
        "  ${CMAKE_SOURCE_DIR}\n"
        "  ${CMAKE_SOURCE_DIR}/mathvec\n"
        ")\n\n"
    )

    # Warnings function
    out.write(
        "function(enable_project_warnings tgt)\n"
        "  if (MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL \"MSVC\")\n"
        "    target_compile_options(${tgt} PRIVATE /W4 /permissive- /EHsc)\n"
        "    if (ENABLE_WARNINGS_AS_ERRORS)\n"
        "      target_compile_options(${tgt} PRIVATE /WX)\n"
        "    endif()\n"
        "  else()\n"
        "    target_compile_options(${tgt} PRIVATE\n"
        "      -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion\n"
        "      -Wno-unused-parameter -Wno-missing-field-initializers)\n"
        "    if (ENABLE_WARNINGS_AS_ERRORS)\n"
        "      target_compile_options(${tgt} PRIVATE -Werror)\n"
        "    endif()\n"
        "  endif()\n"
        "endfunction()\n\n"
        "enable_project_warnings(${MAIN_TARGET})\n\n"
    )

    # IPO/LTO
    out.write(
        "if (ENABLE_LTO)\n"
        "  include(CheckIPOSupported)\n"
        "  check_ipo_supported(RESULT _ipo_ok OUTPUT _ipo_msg)\n"
        "  if (_ipo_ok)\n"
        "    set_property(TARGET ${MAIN_TARGET} PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)\n"
        "  else()\n"
        "    message(STATUS \"IPO/LTO not supported: ${_ipo_msg}\")\n"
        "  endif()\n"
        "endif()\n\n"
    )

    # Sanitizers / coverage
    out.write(
        "if (ENABLE_ASAN_UBSAN AND NOT MSVC AND CMAKE_BUILD_TYPE STREQUAL \"Debug\")\n"
        "  target_compile_options(${MAIN_TARGET} PRIVATE -fsanitize=address,undefined)\n"
        "  target_link_options(${MAIN_TARGET}    PRIVATE -fsanitize=address,undefined)\n"
        "endif()\n\n"
        "if (ENABLE_COVERAGE AND CMAKE_BUILD_TYPE STREQUAL \"Debug\")\n"
        "  if (CMAKE_CXX_COMPILER_ID MATCHES \"GNU|Clang\")\n"
        "    target_compile_options(${MAIN_TARGET} PRIVATE --coverage)\n"
        "    target_link_options(${MAIN_TARGET}    PRIVATE --coverage)\n"
        "  endif()\n"
        "endif()\n\n"
    )

    # IPP
    out.write(
        "if (ENABLE_IPP)\n"
        "  find_package(IPP CONFIG QUIET)\n"
        "  if (IPP_FOUND)\n"
        "    target_link_libraries(${MAIN_TARGET} PRIVATE IPP::ipps IPP::ippcore IPP::ippvm)\n"
        "    if (UNIX)\n"
        "      get_target_property(_ipps_loc IPP::ipps IMPORTED_LOCATION)\n"
        "      if (_ipps_loc)\n"
        "        get_filename_component(_ipp_dir \"${_ipps_loc}\" DIRECTORY)\n"
        "        set_property(TARGET ${MAIN_TARGET} APPEND PROPERTY BUILD_RPATH   \"${_ipp_dir}\")\n"
        "        set_property(TARGET ${MAIN_TARGET} APPEND PROPERTY INSTALL_RPATH \"${_ipp_dir}\")\n"
        "      endif()\n"
        "    endif()\n"
        "  else()\n"
        "    message(STATUS \"IPP not found; building without IPP (set ENABLE_IPP=OFF to silence)\")\n"
        "    target_compile_definitions(${MAIN_TARGET} PRIVATE MATHVEC_NO_IPP)\n"
        "  endif()\n"
        "endif()\n\n"
    )

    # GoogleTest + CTest
    out.write(
        "include(FetchContent)\n"
        "FetchContent_Declare(\n"
        "  googletest\n"
        "  URL https://github.com/google/googletest/archive/refs/tags/v1.17.0.zip\n"
        "  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)\n"
        "set(FETCHCONTENT_UPDATES_DISCONNECTED ON)\n"
        "FetchContent_MakeAvailable(googletest)\n\n"
        "include(CheckCXXCompilerFlag)\n"
        "check_cxx_compiler_flag(\"-Wno-character-conversion\" HAS_WNO_CHAR_CONV)\n"
        "target_link_libraries(${MAIN_TARGET} PRIVATE GTest::gtest_main)\n"
        "foreach(tgt gtest gtest_main gmock gmock_main)\n"
        "  if (TARGET ${tgt})\n"
        "    if (MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL \"MSVC\")\n"
        "      target_compile_options(${tgt} PRIVATE /WX-)\n"
        "    else()\n"
        "      target_compile_options(${tgt} PRIVATE -Wno-error)\n"
        "    endif()\n"
        "    if (CMAKE_CXX_COMPILER_ID STREQUAL \"Clang\" AND HAS_WNO_CHAR_CONV)\n"
        "      target_compile_options(${tgt} PRIVATE -Wno-character-conversion)\n"
        "    endif()\n"
        "  endif()\n"
        "endforeach()\n\n"
        "include(CTest)\n"
        "if (BUILD_TESTING)\n"
        "  add_test(NAME ${MAIN_TARGET} COMMAND ${MAIN_TARGET} --gtest_color=yes)\n"
        "endif()\n"
    )

    Path(output).write_text(out.getvalue(), encoding="utf-8")
    print(f"[cmake] wrote -> {output}")