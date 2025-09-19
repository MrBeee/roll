import numpy as np


class ChunkedData:
    """Provides a view into a large dataset by accessing only chunks at a time."""

    def __init__(self, data, chunk_size=100_000):
        """
        Initialize with the source data and chunk size

        Args:
            data: A numpy array or memmap
            chunk_size: Number of rows in each chunk
        """
        self.data = data
        self.chunk_size = chunk_size
        self.current_chunk = 0
        self.total_chunks = int(np.ceil(data.shape[0] / chunk_size))
        self.columns = data.shape[1] if len(data.shape) > 1 else 1

    def get_current_chunk(self):
        """Returns the current chunk of data"""
        start = self.current_chunk * self.chunk_size
        end = min(start + self.chunk_size, self.data.shape[0])
        return self.data[start:end]

    def next_chunk(self):
        """Move to next chunk if available"""
        if self.current_chunk < self.total_chunks - 1:
            self.current_chunk += 1
            return True
        return False

    def previous_chunk(self):
        """Move to previous chunk if available"""
        if self.current_chunk > 0:
            self.current_chunk -= 1
            return True
        return False

    def goto_chunk(self, chunk_index):
        """Jump to a specific chunk"""
        if 0 <= chunk_index < self.total_chunks:
            self.current_chunk = chunk_index
            return True
        return False

    def get_row_count(self):
        """Get number of rows in current chunk"""
        start = self.current_chunk * self.chunk_size
        end = min(start + self.chunk_size, self.data.shape[0])
        return end - start

    def get_item(self, row, column):
        """Get a specific item from the current chunk"""
        actual_row = self.current_chunk * self.chunk_size + row
        if actual_row < self.data.shape[0] and column < self.columns:
            return self.data[actual_row, column]
        return None

    def get_total_rows(self):
        """Get total number of rows in the entire dataset"""
        return self.data.shape[0]
