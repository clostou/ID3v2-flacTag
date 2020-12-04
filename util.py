import os.path
from struct import calcsize, unpack_from

__all__ = ['AudioContext','AudioContextBuffer','bytes_to_file','copy_file']

class AudioContext():
    """The abstract base class for all audio context classes."""
    tag = ''
    _buffer = None
    _define = ()

    def __init__(self, filepath):
        self.path = filepath
        self._tagcheck()
        self.size = self._getsize()

    def _tagcheck(self):
        '''Check if the tag type of audio file correspond to subclass.
        '''
        pass

    def _getsize(self):
        '''Return size of the whole tag.
        This reads original file directly.
        '''
        return 0

    def _createlabels(self):
        '''Set labels to AudioContextBuffer object according to pre-define,
        at the same time create a list, self.table, containing all label names
        which have been set.
        This's for easier searching to get specific contexet field or pointer.
        '''
        pass

    def __call__(self):
        '''An sample implementation of __call__.
        '''
        return f"[{self.tag}]Audio Context of {self.path}"

class AudioContextBuffer():
    """Buffered I/O implementation using an in-memory bytes buffer."""
    _buf = None
    
    def __init__(self, initial_bytes=None):
        buf = bytearray()
        if initial_bytes is not None:
            buf += initial_bytes
        self._buf = buf
        self._pos = 0
        self._index = {}

    def __setitem__(self, key, offset):
        '''Set modified label to a part of stream between pointer and
        the offset.
        '''
        if not isinstance(key, str):
            raise TypeError(f"{key!r} is not a str")
        try:
            offset_index = offset.__index__
        except AttributeError:
            raise TypeError(f"{offset!r} is not an integer")
        else:
            offset = offset_index()
        if offset >= 0:
            self._index[key] = (self._pos, self._pos + offset)
        else:
            self._index[key] = (max(0, self._pos + offset), self._pos)

    def __getitem__(self, key):
        '''Get specific bytes stream by a label.
        '''
        try:
            p1, p2 = self._index[key]
        except KeyError:
            raise KeyError(f"tabel {key!r} doesn't exist")
        b = self._buf[p1 : p2]
        return bytes(b)

    def getvalue(self):
        '''Return the bytes value (contents) of the buffer.
        '''
        return bytes(self._buf)

    def getbuffer(self):
        '''Return a readable and writable view of the buffer.
        '''
        return memoryview(self._buf)

    def flush(self):
        if self._buf is not None:
            self._buf.clear()

    def read(self, size=-1):
        '''Read and return up to size bytes, where size is an int,
        and returns an empty bytes array on EOF.
        '''
        if size is None:
            size = -1
        else:
            try:
                size_index = size.__index__
            except AttributeError:
                raise TypeError(f"{size!r} is not an integer")
            else:
                size = size_index()
        if len(self._buf) <= self._pos or size == 0:
            return b""
        if size < 0:
            size = len(self._buf)
        newpos = min(len(self._buf), self._pos + size)
        b = self._buf[self._pos : newpos]
        self._pos = newpos
        return bytes(b)

    def read2(self, end=b'\x00'):
        '''Read and check each byte tile meeting given terminator,
        then return.
        Note the end must be 1 byte long byte-object.
        '''
        if not isinstance(end, bytes) or len(end) != 1:
            raise TypeError(f"{end!r} is an invalid terminator")
        endpos = self._pos
        for i in range(len(self._buf) - self._pos):
            if self._buf[self._pos + i] == end[0]:
                endpos = self._pos + i
                break
        b = self._buf[self._pos : endpos]
        self._pos = endpos + 1
        return bytes(b)
            

    def write(self, b):
        '''Write the given bytes buffer to the IO stream.
        Return the number of bytes written, which is always the length of b
        in bytes.
        '''
        if isinstance(b, str):
            raise TypeError("can't write str to binary stream")
        with memoryview(b) as view:
            n = view.nbytes  # Size of any bytes-like object
        if n == 0:
            return 0
        pos = self._pos
        if pos > len(self._buf):
            padding = b'\x00' * (pos - len(self.buf))
            self._buf += padding  # Inserts null bytes between the blanks
        self._buf[pos : pos + n] = b
        self._pos += n
        return n

    def seek(self, pos, whence=0):
        '''Pointer seeking.
        '''
        try:
            pos_index = pos.__index__
        except AttributeError:
            raise TypeError(f"{pos!r} is not an integer")
        else:
            pos = pos_index()
        if whence == 0:
            if pos < 0:
                raise ValueError("negetive seek position %r" % (pos,))
            self._pos = pos
        elif whence == 1:
            self._pos = max(0, self._pos + pos)
        elif whence == 2:
            self._pos = max(0, len(self._buffer) + pos)
        else:
            raise ValueError("unsupported whence value")
        return self._pos

    def labelseek(self, key, back=1):
        '''Pointer seeking by a label.
        '''
        try:
            p1, p2 = self._index[key]
        except KeyError:
            raise KeyError(f"label {key!r} doesn't exist")
        self._pos = p1
        if back == 0:
            return p2
        else:
            return p2 - p1

    def unpack(self, fmt):
        '''Unpack specific bytes stream using struct.unpack.
        '''
        size = calcsize(fmt)
        packet = unpack_from(fmt, self._buf, self._pos)
        self._pos += size
        return packet

    def tell(self):
        return self._pos

    def truncate(self, pos=None):
        if pos is None:
            pos = self._pos
        else:
            try:
                pos_index = pos.__index__
            except AttributeError:
                raise TypeError(f"{pos!r} is not an integer")
            else:
                pos = pos_index()
            if pos < 0:
                raise ValueError("negative truncate position %r" % (pos,))
        del self._buf[pos:]
        return pos
        
def bytes_to_file(path, *stream, exist_ok = False):
    mode = 'wb'
    if os.path.exists(path):
        if exist_ok:
            mode = 'ab'
        else:
            os.remove(path)
    with open(path, mode) as f:
        for cut in stream:
            f.write(cut)

def copy_file(file1, file2, start = 0, ending = -1, exist_ok = False, buffer = 1024):
    if ending >= 0 and ending <= start:
        raise ValueError("invalid start-ending of read")
    mode = 'wb'
    if os.path.exists(file1):
        if exist_ok:
            mode = 'ab'
        else:
            os.remove(file1)
    if ending < 0:
        length = os.path.getsize(file2) - start
    else:
        length = min(os.path.getsize(file2), ending) - start
    with open(file2, 'rb') as f:
        f.seek(start)
        with open(file1, mode) as _f:
            while True:
                _f.write(f.read(buffer))
                length -= buffer
                if length <= 0:
                    break

