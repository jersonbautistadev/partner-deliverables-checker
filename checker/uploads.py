from django.core.files.uploadhandler import FileUploadHandler, StopUpload

from checker.engine import MAX_FILE_BYTES


class BoundedUploadHandler(FileUploadHandler):
    """Abort oversized streams before the default handler buffers them."""

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > MAX_FILE_BYTES:
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None
