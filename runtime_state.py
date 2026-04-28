# coding=utf-8

from dataclasses import dataclass, field


@dataclass
class RuntimeState:
    fileName: str = ''
    projectDirectory: str = ''
    importDirectory: str = ''
    wellDirectory: str = ''
    recentFileList: list[str] = field(default_factory=list)
