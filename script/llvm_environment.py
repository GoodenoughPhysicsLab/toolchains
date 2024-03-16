#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import psutil
import shutil
import sys
from math import floor


def run_command(command: str) -> None:
    print(command)
    assert os.system(command) == 0, f'Command "{command}" failed.'


lib_list = ("libxml2", "zlib")
system_list: dict[str, str] = {
    # "x86_64-linux-gnu": "Linux",
    # "i686-linux-gnu": "Linux",
    # "aarch64-linux-gnu": "Linux",
    # "riscv64-linux-gnu": "Linux",
    # "loongarch64-linux-gnu": "Linux",
    "x86_64-w64-mingw32": "Windows",
    "i686-w64-mingw32": "Windows",
}
subproject_list = ("llvm", "runtimes")


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


def overwrite_copy(src: str, dst: str):
    if os.path.exists(dst):
        os.remove(dst)
    shutil.copyfile(src, dst)


class environment:
    major_version: str  # < LLVM的主版本号
    host: str  # < host平台
    build: str  # build平台
    name_without_version: str  # < 不带版本号的工具链名
    name: str  # < 工具链名
    home_dir: str  # < 源代码所在的目录，默认为$HOME
    prefix: dict[str, str] = {}  # < 工具链安装位置
    num_cores: int  # < 编译所用线程数
    current_dir: str  # < toolchains项目所在目录
    lib_dir_list: dict[str, str]  # < 所有库所在目录
    bin_dir: str  # < 安装后可执行文件所在目录
    source_dir: dict[str, str] = {}  # < 源代码所在目录
    build_dir: dict[str, str] = {}  # < 构建时所在目录
    stage: int = 1  # < 自举阶段
    compiler_list = ("C", "CXX", "ASM")  # < 编译器列表
    sysroot_dir: str  # < sysroot所在路径
    dylib_option_list: dict[str, str] = {
        "LLVM_LINK_LLVM_DYLIB": "ON",
        "LLVM_BUILD_LLVM_DYLIB": "ON",
        "CLANG_LINK_CLANG_DYLIB": "ON",
    }
    dylib_option_list_windows: dict[str, str] = {"BUILD_SHARED_LIBS": "ON"}
    llvm_option_list_1: dict[str, str] = {
        "CMAKE_BUILD_TYPE": "Release",
        "LLVM_BUILD_DOCS": "OFF",
        "LLVM_BUILD_EXAMPLES": "OFF",
        "LLVM_INCLUDE_BENCHMARKS": "OFF",
        "LLVM_INCLUDE_EXAMPLES": "OFF",
        "LLVM_INCLUDE_TESTS": "OFF",
        "LLVM_TARGETS_TO_BUILD": '"X86;AArch64;WebAssembly;RISCV;ARM;LoongArch"',
        "LLVM_ENABLE_PROJECTS": '"clang;lld"',
        "LLVM_ENABLE_RUNTIMES": '"libcxx;libcxxabi;libunwind;compiler-rt"',
        "LLVM_ENABLE_WARNINGS": "OFF",
        "LLVM_INCLUDE_TESTS": "OFF",
        "CLANG_INCLUDE_TESTS": "OFF",
        "BENCHMARK_INSTALL_DOCS": "OFF",
        "LLVM_INCLUDE_BENCHMARKS": "OFF",
        "CLANG_DEFAULT_LINKER": "lld",
        "LLVM_ENABLE_LLD": "ON",
        "CMAKE_BUILD_WITH_INSTALL_RPATH": "ON",
        "LLVM_INSTALL_TOOLCHAIN_ONLY": "ON",
        "LIBCXX_INCLUDE_BENCHMARKS": "OFF",
        "LIBCXX_USE_COMPILER_RT": "ON",
        "LIBCXX_CXX_ABI": "libcxxabi",
        "COMPILER_RT_DEFAULT_TARGET_ONLY": "ON",
        "COMPILER_RT_BUILD_BUILTINS": "ON",
        "COMPILER_RT_USE_LIBCXX": "ON",
    }
    llvm_option_list_w64_1: dict[str, str] = {
        **llvm_option_list_1,
        "LLVM_ENABLE_RUNTIMES": '"libcxx;libunwind;compiler-rt"',
        "LIBCXX_CXX_ABI": "libsupc++",
    }
    llvm_option_list_w32_1: dict[str, str] = {**llvm_option_list_w64_1}
    llvm_option_list_la_1: dict[str, str] = {
        **llvm_option_list_1,
        "LLVM_ENABLE_LLD": "OFF",
    }
    llvm_option_list_2: dict[str, str] = {
        **llvm_option_list_1,
        "LLVM_ENABLE_PROJECTS": '"clang;clang-tools-extra;lld;compiler-rt"',
        "LLVM_ENABLE_LTO": "Thin",
        "CLANG_DEFAULT_CXX_STDLIB": "libc++",
        "CLANG_DEFAULT_RTLIB": "compiler-rt",
        "CLANG_DEFAULT_UNWINDLIB": "libunwind",
        "LIBUNWIND_USE_COMPILER_RT": "ON",
    }
    llvm_option_list_w64_2: dict[str, str] = {}
    llvm_option_list_w32_2: dict[str, str] = {}
    llvm_option_list_la_2: dict[str, str] = {
        **llvm_option_list_2,
        "LLVM_ENABLE_LLD": "OFF",
    }
    compiler_rt_dir: str  # < compiler-rt所在路径

    def __init__(self, major_version: str, build: str, host: str = "") -> None:
        self.major_version = major_version
        self.build = build
        self.host = host if host != "" else self.build
        self.name_without_version = f"{self.host}-clang"
        self.name = self.name_without_version + major_version
        self.home_dir = ""
        for option in sys.argv:
            if option.startswith("--home="):
                self.home_dir = option[7:]
            elif option.startswith("--stage="):
                value = option[8:]
                assert value.isdigit(), 'Option "--stage=" needs an integer'
                self.stage = int(value)
                assert 1 <= self.stage <= 2, "Stage should be 1 or 2"
        if self.home_dir == "":
            self.home_dir = os.environ["HOME"]
        self.prefix["llvm"] = os.path.join(self.home_dir, self.name)
        self.prefix["runtimes"] = os.path.join(self.prefix["llvm"], "install")
        self.num_cores = floor(psutil.cpu_count() * 1.5)
        self.current_dir = os.path.abspath(os.path.dirname(__file__))
        self.toolchain_file = os.path.join(self.current_dir, f"{self.name_without_version}.cmake")
        self.bin_dir = os.path.join(self.prefix["llvm"], "bin")
        for project in subproject_list:
            self.source_dir[project] = os.path.join(self.home_dir, "llvm", project)
            self.build_dir[project] = os.path.join(self.source_dir[project], f"build-{self.host}")
        self.sysroot_dir = os.path.join(self.home_dir, "sysroot")
        include_dir = os.path.join(self.sysroot_dir, "x86_64-w64-mingw32/include/c++")
        include_dir = os.path.join(include_dir, os.listdir(include_dir)[0])
        self.llvm_option_list_w64_1["LIBCXX_CXX_ABI_INCLUDE_PATHS"] = include_dir
        include_dir = os.path.join(self.sysroot_dir, "i686-w64-mingw32/include/c++")
        include_dir = os.path.join(include_dir, os.listdir(include_dir)[0])
        self.llvm_option_list_w32_1["LIBCXX_CXX_ABI_INCLUDE_PATHS"] = include_dir
        self.llvm_option_list_w64_2 = {**self.llvm_option_list_2, **self.llvm_option_list_w64_1}
        self.llvm_option_list_w32_2 = {**self.llvm_option_list_2, **self.llvm_option_list_w32_1}
        self.compiler_rt_dir = os.path.join(self.prefix["llvm"], "lib", "clang", self.major_version, "lib")
        # 将自身注册到环境变量中
        self.register_in_env()

    def get_compiler_path(self) -> dict[str, str]:
        """获取编译器路径

        Returns:
            dict[str,str]: 编译器路径表
        """
        if self.stage == 1:
            return {"C": "clang", "CXX": "clang++", "ASM": "clang"}
        else:
            return {
                "C": f'{os.path.join(self.bin_dir, "clang")}',
                "CXX": f'{os.path.join(self.bin_dir, "clang++")}',
                "ASM": f'{os.path.join(self.bin_dir, "clang")}',
            }

    def register_in_env(self) -> None:
        """注册安装路径到环境变量"""
        os.environ["PATH"] = f"{self.bin_dir}:{os.environ['PATH']}"

    def register_in_bashrc(self) -> None:
        """注册安装路径到用户配置文件"""
        with open(os.path.join(self.home_dir, ".bashrc"), "a") as bashrc_file:
            bashrc_file.write(f"export PATH={self.bin_dir}:$PATH\n")

    def get_compiler(self, target: str, *command_list_in) -> list[str]:
        assert target in system_list
        gcc = f"--gcc-toolchain={os.path.join(self.home_dir, 'sysroot')}"
        command_list: list[str] = []
        compiler_path = self.get_compiler_path()
        no_warning = "-Wno-unused-command-line-argument"
        for compiler in self.compiler_list:
            command_list.append(f'-DCMAKE_{compiler}_COMPILER="{compiler_path[compiler]}"')
            if target != self.build:
                command_list.append("-DCMAKE_CROSSCOMPILING=TRUE")
            command_list.append(f"-DCMAKE_{compiler}_COMPILER_TARGET={target}")
            command_list.append(f'-D{compiler}_FLAGS="{no_warning} {gcc} {" ".join(command_list_in)}"')
            command_list.append(f"-DCMAKE_{compiler}_COMPILER_WORKS=ON")
        if target != self.build:
            command_list.append(f"-DCMAKE_SYSTEM_NAME={system_list[target]}")
            command_list.append(f"-DCMAKE_SYSTEM_PROCESSOR={target[: target.find('-')]}")
            command_list.append(f"-DCMAKE_SYSROOT='{self.sysroot_dir}'")
        command_list.append(f"-DLLVM_RUNTIMES_TARGET={target}")
        command_list.append(f"-DLLVM_DEFAULT_TARGET_TRIPLE={target}")
        command_list.append(f"-DLLVM_HOST_TRIPLE={gnu_to_llvm(self.host)}")
        return command_list

    def config(self, project: str, target: str, *command_list, **cmake_option_list) -> None:
        assert project in subproject_list
        prefix = self.prefix[project]
        command = f"cmake -G Ninja --install-prefix {prefix} -B {self.build_dir[project]} -S {self.source_dir[project]} "
        command += " ".join(self.get_compiler(target, *command_list) + get_cmake_option(**cmake_option_list))
        run_command(command)

    def make(self, target: str) -> None:
        run_command(f"ninja -C {self.build_dir[target]} -j{self.num_cores}")

    def install(self, target: str) -> None:
        run_command(f"ninja -C {self.build_dir[target]} install/strip -j{self.num_cores}")

    def remove_build_dir(self, target: str) -> None:
        assert target in subproject_list
        dir = self.build_dir[target]
        if os.path.exists(dir):
            shutil.rmtree(dir)
        if target == "runtimes":
            dir = self.prefix[target]
            if os.path.exists(dir):
                shutil.rmtree(dir)

    def build_sysroot(self, target: str) -> None:
        prefix = self.prefix["runtimes"]
        for dir in os.listdir(prefix):
            src_dir = os.path.join(prefix, dir)
            match dir:
                case "bin":
                    dst_dir = os.path.join(self.sysroot_dir, target, "lib")
                    for file in os.listdir(src_dir):
                        if file.endswith("dll"):
                            overwrite_copy(os.path.join(src_dir, file), os.path.join(dst_dir, file))
                case "lib":
                    dst_dir = os.path.join(self.sysroot_dir, target, "lib")
                    for item in os.listdir(src_dir):
                        if item == system_list[target].lower():
                            item = item.lower()
                            rt_dir = os.path.join(self.compiler_rt_dir, item)
                            if not os.path.exists(rt_dir):
                                os.mkdir(rt_dir)
                            for file in os.listdir(os.path.join(src_dir, item)):
                                overwrite_copy(os.path.join(src_dir, item, file), os.path.join(rt_dir, file))
                            continue
                        overwrite_copy(os.path.join(src_dir, item), os.path.join(dst_dir, item))
                case "include":
                    dst_dir = os.path.join(self.sysroot_dir, target, "include")
                    overwrite_copy(os.path.join(src_dir, "c++", "v1", "__config_site"), os.path.join(dst_dir, "__config_site"))

    def copy_readme(self) -> None:
        """复制工具链说明文件"""
        readme_path = os.path.join(self.current_dir, "..", "readme", f"{self.name_without_version}.md")
        target_path = os.path.join(self.prefix["llvm"], "README.md")
        shutil.copyfile(readme_path, target_path)

    def package(self) -> None:
        """打包工具链"""
        self.copy_readme()
        os.chdir(self.home_dir)
        run_command(f"tar -cf {self.name}.tar {self.name}")
        memory_MB = psutil.virtual_memory().available // 1048576 + 3072
        run_command(f"xz -fev9 -T 0 --memlimit={memory_MB}MiB {self.name}.tar")
