from __future__ import annotations

import aiohttp

import argparse
from pathlib import Path
import asyncio
from typing import TYPE_CHECKING

from .__version__ import __version__

if TYPE_CHECKING:
    from typing import Optional


HOME_PATH = Path(__file__).parent.resolve()
REPO_URL = "https://raw.githubusercontent.com/ren3104/pycryptoex"

CLASS_NAME_MAP = {
    "kucoin": "KuCoin"
}

IMPORT_TMPL = "from .{name} import {class_name}"
INIT_TMPL = """
{imports}


__all__ = [
    {class_names}
]
""".strip()


async def download_client_from_github(name: str, version: str) -> Optional[str]:
    async with aiohttp.request(
        method="GET",
        url=f"{REPO_URL}/{version}/clients/{name}.py"
    ) as response:
        if response.ok:
            with open(HOME_PATH / f"{name}.py", "w") as f:
                f.write(await response.text())
            return name


async def main(args: argparse.Namespace) -> None:
    client_names = [
        str(n.name).replace(".py", "", 1)
        for n in HOME_PATH.glob("[!_]*.py")
    ]

    new_client_names = await asyncio.gather(*[
        download_client_from_github(name.lower(), args.version)
        for name in args.names
        if args.update or name.lower() not in client_names
    ])

    class_names = []
    imports_tmpls = []
    for client_name in set(client_names + new_client_names):
        if client_name is None:
            continue
        class_name = CLASS_NAME_MAP.get(client_name, client_name.capitalize())
        class_names.append(class_name)
        imports_tmpls.append(IMPORT_TMPL.format(
            name=client_name,
            class_name=class_name
        ))

    with open(HOME_PATH / "__init__.py", "w") as f:
        f.write(INIT_TMPL.format(
            imports="\n".join(imports_tmpls),
            class_names=",\n    ".join(class_names)
        ))


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", type=str, nargs="+")
    parser.add_argument("-u", "--update", action="store_true")
    # -d --delete
    parser.add_argument("-v", "--version", default=f"v{__version__}")
    args = parser.parse_args()

    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
