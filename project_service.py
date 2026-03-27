# coding=utf-8

from dataclasses import dataclass

from qgis.PyQt.QtCore import QFile, QIODevice, QTextStream


@dataclass
class ProjectReadResult:
    success: bool
    plainText: str = ''
    errorText: str = ''


@dataclass
class ProjectWriteResult:
    success: bool
    xmlText: str = ''
    errorText: str = ''


class ProjectService:
    def readProjectText(self, fileName):
        qFile = QFile(fileName)
        if not qFile.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            return ProjectReadResult(success=False, errorText=qFile.errorString())

        stream = QTextStream(qFile)
        plainText = stream.readAll()
        qFile.close()
        return ProjectReadResult(success=True, plainText=plainText)

    def buildProjectXml(self, survey, projectDirectory=None, useRelativePaths=False, indent=4):
        if useRelativePaths:
            survey.makeWellPathsRelative(projectDirectory)
        return survey.toXmlString(indent)

    def writeProjectXml(self, fileName, survey, projectDirectory=None, useRelativePaths=False, indent=4):
        xmlText = self.buildProjectXml(survey, projectDirectory, useRelativePaths, indent)

        qFile = QFile(fileName)
        if not qFile.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Truncate):
            return ProjectWriteResult(success=False, xmlText=xmlText, errorText=qFile.errorString())

        _ = QTextStream(qFile) << xmlText
        qFile.close()
        return ProjectWriteResult(success=True, xmlText=xmlText)