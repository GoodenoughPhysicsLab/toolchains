from typing import Callable
import gcc_environment as gcc
from functools import wraps

# 修改器列表
modifier_list: dict[str, Callable[[gcc.cross_environment], None]] = {}


def register(fn):
    """注册修改器到列表

    Args:
        fn (function): 修改器函数
    """
    name: str = fn.__name__
    field_list = name.split("_")[:-1]
    name = "-".join(field_list)
    modifier_list[name] = fn

    @wraps(fn)
    def wrapper(env: gcc.cross_environment) -> None:
        fn(env)

    return wrapper


@register
def arm_linux_gnueabi_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "arm-sf"


@register
def arm_linux_gnueabihf_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "arm-hf"


@register
def loongarch64_loongnix_linux_gnu_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "loongarch64-loongnix"
    env.libc_option.append("--enable-obsolete-rpc")
    env.gcc_option.append("--disable-libsanitizer")
