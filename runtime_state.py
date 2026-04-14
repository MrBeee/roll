# coding=utf-8

from dataclasses import dataclass


@dataclass
class RuntimeState:
    projectDirectory: str = ''
    importDirectory: str = ''
