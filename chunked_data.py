import numpy as np


class ChunkedData:
    """Provides a view into a large dataset by accessing only chunks at a time."""

    def __init__(self, data, chunkSize=100_000):
        """
        Initialize with the source data and chunk size

        Args:
            data: A numpy array or memmap
            chunkSize: Number of rows in each chunk
        """
        self.data = data
        self.chunkSize = chunkSize
        self.currentChunk = 0
        self.totalChunks = int(np.ceil(data.shape[0] / chunkSize))
        self.columns = data.shape[1] if len(data.shape) > 1 else 1

    def getCurrentChunk(self):
        """Returns the current chunk of data"""
        start = self.currentChunk * self.chunkSize
        end = min(start + self.chunkSize, self.data.shape[0])
        return self.data[start:end]

    def nextChunk(self):
        """Move to next chunk if available"""
        if self.currentChunk < self.totalChunks - 1:
            self.currentChunk += 1
            return True
        return False

    def previousChunk(self):
        """Move to previous chunk if available"""
        if self.currentChunk > 0:
            self.currentChunk -= 1
            return True
        return False

    def gotoChunk(self, chunkIndex):
        """Jump to a specific chunk"""
        if 0 <= chunkIndex < self.totalChunks:
            self.currentChunk = chunkIndex
            return True
        return False

    def getRowCount(self):
        """Get number of rows in current chunk"""
        start = self.currentChunk * self.chunkSize
        end = min(start + self.chunkSize, self.data.shape[0])
        return end - start

    def getItem(self, row, column):
        """Get a specific item from the current chunk"""
        actualRow = self.currentChunk * self.chunkSize + row
        if actualRow < self.data.shape[0] and column < self.columns:
            return self.data[actualRow, column]
        return None

    def getTotalRows(self):
        """Get total number of rows in the entire dataset"""
        return self.data.shape[0]
