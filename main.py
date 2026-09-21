# -*- coding: utf-8 -*-
"""
main.py — Ponto de entrada sem instalação:

    python main.py --help

Após `pip install -e .`, o comando equivalente é `wiebepy`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from wiebepy.cli.parser import main  # noqa: E402

if __name__ == "__main__":
    main()
