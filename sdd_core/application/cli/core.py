import argparse
from typing import Callable, Dict, Any

class CommandRegistry:
    def __init__(self):
        self.commands: Dict[str, Dict[str, Any]] = {}  # type: ignore

    def register(self, name: str, help: str = "") -> Callable:
        """
        装饰器：注册一个子命令。
        被装饰的函数需接收一个参数：`parser: argparse.ArgumentParser`。
        并且需在内部通过 `parser.set_defaults(func=handler)` 绑定该命令的处理函数。
        """
        def decorator(setup_func: Callable[[argparse.ArgumentParser], None]) -> Callable:
            self.commands[name] = {
                "help": help,
                "setup_func": setup_func
            }
            return setup_func
        return decorator

    def build_parsers(self, subparsers: argparse._SubParsersAction) -> None:
        """
        遍历并装载所有注册的子命令到 subparsers 实例中。
        """
        for name, meta in self.commands.items():
            parser = subparsers.add_parser(name, help=meta["help"])
            meta["setup_func"](parser)

registry = CommandRegistry()
