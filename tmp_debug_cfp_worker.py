from test.plugin_loader import loadPluginModule
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from qgis.PyQt.QtCore import QPointF, QRectF

workerThreadsModule = loadPluginModule('worker_threads')
CfpFromTraceTableWorker = workerThreadsModule.CfpFromTraceTableWorker
CfpFromTraceTableRequest = workerThreadsModule.CfpFromTraceTableRequest


class SignalCollector:
    def __init__(self):
        self.values = []

    def emit(self, value):
        self.values.append(value)


class SurveyStub:
    def __init__(self):
        self.errorText = 'cfp trace-table failed'
        self.progress = SignalCollector()
        self.message = SignalCollector()
        self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
        self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))
        self.xmlString = None
        self.createArrays = None

    def fromXmlString(self, xmlString, createArrays):
        self.xmlString = xmlString
        self.createArrays = createArrays


analysisRows = np.zeros((5, 16), dtype=np.float32)
analysisRows[0, 2] = 1.0
analysisRows[0, 3] = 1.0
analysisRows[0, 4] = 1.0
analysisRows[0, 6] = 1.0
analysisRows[0, 7] = 1.0
analysisRows[2, 2] = 1.0
analysisRows[2, 3] = 50.0
analysisRows[2, 4] = 50.0
analysisRows[2, 6] = 50.0
analysisRows[2, 7] = 50.0
analysisRows[3, 2] = 1.0
analysisRows[3, 3] = 3.0
analysisRows[3, 4] = 3.0
analysisRows[3, 6] = 3.0
analysisRows[3, 7] = 3.0
analysisRows[4, 2] = 1.0
analysisRows[4, 3] = 4.0
analysisRows[4, 4] = 4.0
analysisRows[4, 6] = 40.0
analysisRows[4, 7] = 40.0

with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
    worker = CfpFromTraceTableWorker(
        CfpFromTraceTableRequest(
            xmlString='<survey />',
            analysisRows=analysisRows,
            focalX=0.0,
            focalY=0.0,
            focalZ=-10.0,
            maxDipDegrees=45.0,
            vint=2500.0,
            chunkSize=2,
        )
    )

    resultEvents = []
    worker.resultReady.connect(resultEvents.append)
    worker.run()

result = resultEvents[0]
print('success:', result.success)
print('errorText:', result.errorText)
print('chunkCount:', result.chunkCount)
print('totalTraceCount:', result.totalTraceCount)
print('contributingTraceCount:', result.contributingTraceCount)
print('source shape:', None if result.sourceBeamImage is None else result.sourceBeamImage.shape)
print('receiver shape:', None if result.receiverBeamImage is None else result.receiverBeamImage.shape)
print('resolution shape:', None if result.resolutionImage is None else result.resolutionImage.shape)
print('radon source shape:', None if result.radonSourceBeamImage is None else result.radonSourceBeamImage.shape)
print('radon receiver shape:', None if result.radonReceiverBeamImage is None else result.radonReceiverBeamImage.shape)
print('radon avp shape:', None if result.radonAvpImage is None else result.radonAvpImage.shape)
