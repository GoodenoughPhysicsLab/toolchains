#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import psutil
import shutil
import sys
from math import floor
from importlib import import_module


def run_command(command: str) -> None:
    print(command)
    assert os.system(command) == 0, f'Command "{command}" failed.'


lib_list = ("libxml2", "zlib")
dylib_option_list = {
    "LLVM_LINK_LLVM_DYLIB": "ON",
    "LLVM_BUILD_LLVM_DYLIB": "ON",
    "CLANG_LINK_CLANG_DYLIB": "ON",
}
llvm_option_list = {
    "CMAKE_BUILD_TYPE": "Release",
    "LLVM_TARGETS_TO_BUILD": '"X86;AArch64;WebAssembly;RISCV;ARM;LoongArch"',
    "LLVM_ENABLE_PROJECTS": '"clang;clang-tools-extra;lld;compiler-rt"',
    # "LLVM_ENABLE_RUNTIMES": '"libcxx;libcxxabi;libunwind"',
    "LLVM_ENABLE_WARNINGS": "OFF",
    "LLVM_INCLUDE_TESTS": "OFF",
    "LLVM_ENABLE_LTO": "Thin",
    "CLANG_DEFAULT_CXX_STDLIB": "libc++",
    "CLANG_DEFAULT_LINKER": "lld",
    "CLANG_DEFAULT_RTLIB": "compiler-rt",
    "CLANG_DEFAULT_UNWINDLIB": "libunwind",
    "CLANG_INCLUDE_TESTS": "OFF",
    "BENCHMARK_INSTALL_DOCS": "OFF",
    "LLVM_ENABLE_LLD": "ON",
    "LLVM_INCLUDE_BENCHMARKS": "OFF",
    "LIBCXX_CXX_ABI": "libcxxabi",
    "LIBCXX_INCLUDE_BENCHMARKS": "OFF",
}
target_list = (
    "x86_64-linux-gnu",
    "i386-linux-gnu",
    "aarch64-linux-gnu",
    "riscv64-linux-gnu",
    "loongarch64-linux-gnu",
    "x86_64-w64-mingw32",
    "i386-w64-mingw32",
)
llvm_lib_list = ("compiler-rt", "libunwind", "libcxxabi", "libcxx")
subproject_list = llvm_lib_list + ("llvm",)


def get_cmake_option(**kwargs) -> list[str]:
    option_list: list[str] = []
    for key, value in kwargs.items():
        option_list.append(f"-D{key}={value}")
    return option_list


def gnu_to_llvm(target: str) -> str:
    if target.count("-") == 2:
        index = target.find("-")
        result = target[:index]
        result += "-unknown"
        result += target[index:]
        return result
    else:
        return target


class environment:
    major_version: str  # < LLVM的主版本号
    host: str  # < host平台
    name_without_version: str  # < 不带版本号的工具链名
    name: str  # < 工具链名
    home_dir: str  # < 源代码所在的目录，默认为$HOME
    prefix: str  # < 工具链安装位置
    num_cores: int  # < 编译所用线程数
    current_dir: str  # < toolchains项目所在目录
    lib_dir_list: dict[str, str]  # < 所有库所在目录
    bin_dir: str  # < 安装后可执行文件所在目录
    llvm_dir: str  # < llvm所在目录
    subproject_dir: dict[str, str]  # < 子项目目录
    build_dir: dict[str, str]  # < 构建目录

    def __init__(self, major_version: str, host: str) -> None:
        self.major_version = major_version
        self.host = host
        self.name_without_version = f"{self.host}-clang"
        self.name = self.name_without_version + major_version
        self.home_dir = ""
        for option in sys.argv:
            if option.startswith("--home="):
                self.home_dir = option[7:]
                break
        if self.home_dir == "":
            self.home_dir = os.environ["HOME"]
        self.prefix = os.path.join(self.home_dir, self.name)
        self.num_cores = floor(psutil.cpu_count() * 1.5)
        self.current_dir = os.path.abspath(os.path.dirname(__file__))
        self.toolchain_file = os.path.join(self.current_dir, f"{self.name_without_version}.cmake")
        self.bin_dir = os.path.join(self.prefix, "bin")
        self.llvm_dir = os.path.join(self.home_dir, "llvm")
        self.subproject_dir = {}
        for lib in subproject_list:
            self.subproject_dir[lib] = os.path.join(self.llvm_dir, lib)
        self.build_dir = {}
        for lib, dir in self.subproject_dir.items():
            self.build_dir[lib] = os.path.join(dir, "build")
        self.lib_dir_list = {}
        for lib in lib_list:
            lib_dir = os.path.join(self.home_dir, lib)
            assert os.path.exists(lib_dir), f'Cannot find lib "{lib}" in directory "{lib_dir}"'
            self.lib_dir_list[lib] = lib_dir
        # 将自身注册到环境变量中
        self.register_in_env()

    def register_in_env(self) -> None:
        """注册安装路径到环境变量"""
        os.environ["PATH"] = f"{self.bin_dir}:{os.environ['PATH']}"

    def register_in_bashrc(self) -> None:
        """注册安装路径到用户配置文件"""
        with open(os.path.join(self.home_dir, ".bashrc"), "a") as bashrc_file:
            bashrc_file.write(f"export PATH={self.bin_dir}:$PATH\n")

    def get_compiler(self, target: str) -> list[str]:
        assert target in target_list
        compiler_list = ("CMAKE_C", "CMAKE_CXX", "CMAKE_ASM")
        sysroot = ""
        if target != self.host:
            gcc = import_module(f"x86_64_linux_gnu_host_{target.replace('-', '_')}_target_gcc")
            sysroot = f"--sysroot={gcc.env.prefix}"
        command_list: list[str] = []
        for compiler in compiler_list:
            command_list.append(f"-D{compiler}_COMPILER={'clang++' if 'CXX' in compiler else 'clang'}")
            command_list.append(f'-D{compiler}_FLAGS="--target={target} {sysroot}"')
        return command_list

    def config(self, subproject: str, target: str, *command_list, **cmake_option_list) -> None:
        assert subproject in subproject_list, f'"{subproject}" is not in subproject_list'
        command = f"cmake -G Ninja --install-prefix {self.prefix} -B {self.build_dir[subproject]} -S {self.subproject_dir[subproject]} "
        command += " ".join(self.get_compiler(target) + get_cmake_option(**cmake_option_list)) + " "
        match subproject:
            case "llvm":
                command += " ".join(get_cmake_option(**llvm_option_list))
        run_command(command)

    def build(self, subproject: str) -> None:
        run_command(f"ninja -C {self.build_dir[subproject]} -j{self.num_cores}")

    def install(self, subproject: str) -> None:
        run_command(f"ninja -C {self.build_dir[subproject]} install/strip -j{self.num_cores}")

    def copy_readme(self) -> None:
        """复制工具链说明文件"""
        readme_path = os.path.join(self.current_dir, "..", "readme", f"{self.name_without_version}.md")
        target_path = os.path.join(self.prefix, "README.md")
        shutil.copyfile(readme_path, target_path)

    def package(self) -> None:
        """打包工具链"""
        self.copy_readme()
        os.chdir(self.home_dir)
        run_command(f"tar -cf {self.name}.tar {self.name}")
        memory_MB = psutil.virtual_memory().available // 1048576 + 3072
        run_command(f"xz -fev9 -T 0 --memlimit={memory_MB}MiB {self.name}.tar")
