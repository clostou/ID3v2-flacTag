from util import *
import struct

__all__ = ['FlacContext', 'blockInfo', 'blockPic', 'create_Flac_tag']

class FlacContext(AudioContext):
    _define = ("STREAMINFO",
               "PADDING",
               "APPLICATION",
               "SEEKTABLE",
               "VORBIS_COMMENT",
               "CUESHEET",
               "PICTURE")

    def __init__(self, filepath):
        super(FlacContext, self).__init__(filepath)
        with open(self.path, 'rb') as f:
            self._buffer = AudioContextBuffer(f.read(self.size))
        self.blocklist = self._createlabels()

    def BLOCK_STREAMINFO(self):
        # <16>  The minimum block size (in samples) used in the stream.
        # <16>  The maximum block size (in samples) used in the stream.(a fixed-blocksize stream when equals)
        # <24>  The minimum frame size (in bytes) used in the stream
        # <24>  The maximum frame size (in bytes) used in the stream.(0 means unknown)
        # <20>  Sample rate in Hz.(not more than 655350Hz, 0 is invalid)
        # <3>   (number of channels)-1. FLAC supports from 1 to 8 channels
        # <5>   (bits per sample)-1. FLAC supports from 4 to 32 bits per sample.(coder support up to 24)
        # <36>  Total samples in stream.(inter-channel sample, 0 means unknown)
        # <128> MD5 signature of the unencoded audio data.
        self._buffer.labelseek("STREAMINFO")
        info = []
        info.extend(self._buffer.unpack('!2H'))
        a, = self._buffer.unpack('!I')
        self._buffer.seek(-2,1)
        b, = self._buffer.unpack('!I')
        info.extend((a >> 8, b & 0xffffff))
        s, = self._buffer.unpack('!Q')
        info.extend((s >> 44, s >> 41 & 0x07, s >> 36 & 0x1f, s & 0x0fffffffff))
        info.extend(self._buffer.unpack('!16s'))
        return info

    def BLOCK_PADDING(self):
        pass

    def BLOCK_APPLICATION(self):
        pass

    def BLOCK_VORBIS_COMMENT(self):
        # FLAC tags: vorbis comment packet
        _define = ("TITLE",
                   "VERSION",
                   "ALBUM",
                   "TRACKNUMBER",
                   "ARTIST",
                   "PERFORMER",
                   "COPYRIGHT",
                   "LICENSEN",
                   "ORGANIZATION",
                   "DESCRIPTION",
                   "GENRE",
                   "DATE",
                   "LOCATION",
                   "CONTACT",
                   "ISRC",
                   "ENCODER")
        self._buffer.labelseek("VORBIS_COMMENT")
        comm = dict.fromkeys(_define)
        vendor = self._buffer.unpack('!%ss' % \
                                     self._buffer.unpack('<I')[0]\
                                     )[0].decode()
        num, = self._buffer.unpack('<I')
        for i in range(num):
            length, = self._buffer.unpack('<I')
            _vec, = self._buffer.unpack('!%ss' % length)
            vec = _vec.decode().split('=')
            if comm.setdefault(vec[0], vec[1] + " [Nondefault]") == None:
                comm[vec[0]] = vec[1]
        return comm

    def BLOCK_CUESHEET(self):
        pass

    def BLOCK_PICTURE(self):
        # <32>	The picture type according to the ID3v2 APIC frame
        # <32>	The length of the MIME type string in bytes.
        # <n*8>	The MIME type string, in printable ASCII characters 0x20-0x7e.
        # <32>	The length of the description string in bytes.
        # <n*8>	The description of the picture, in UTF-8.
        # <32>	The width of the picture in pixels.
        # <32>	The height of the picture in pixels.
        # <32>	The color depth of the picture in bits-per-pixel.
        # <32>	For indexed-color pictures (e.g. GIF), the number of colors used, or 0 for non-indexed pictures.
        # <32>	The length of the picture data in bytes.
        # <n*8>	The binary picture data.
        _define = ("Other",
                   "32x32 pixels 'file icon' (PNG only)",
                   "Other file icon",
                   "Cover (front)",
                   "Cover (back)",
                   "Leaflet page",
                   "Media (e.g. label side of CD)",
                   "Lead artist/lead performer/soloist",
                   "Artist/performer",
                   "Conductor",
                   "Band/Orchestra",
                   "Composer",
                   "Lyricist/text writer",
                   "Recording Location",
                   "During recording",
                   "During performance",
                   "Movie/video screen capture",
                   "A bright coloured fish",
                   "Illustration",
                   "Band/artist logotype",
                   "Publisher/Studio logotype")
        self._buffer.labelseek("PICTURE")
        info = []
        picType, = self._buffer.unpack('!I')
        try:
            picType = _define[picType]
        except IndexError:
            raise IndexError("unkonwn picture type: %s" % picType)
        info.append(picType)
        MIME = self._buffer.unpack('!%ss' % self._buffer.unpack('!I'))[0].decode()
        desc = self._buffer.unpack('!%ss' % self._buffer.unpack('!I'))[0].decode()
        # also include 4 4-bytes format information
        info.extend((MIME, desc) + self._buffer.unpack('!4I'))
        imageData = self._buffer.read(self._buffer.unpack('!I')[0])
        return imageData, info

    def block_copy(self, *blocks, invert=0):
        raw_block = ()
        if invert:
            blocks = [b for b in self.blocklist if b not in blocks]
        else:
            blocks = [b for b in blocks if b in self.blocklist]
        for b in blocks:
            length = self._buffer.labelseek(b) + 4
            self._buffer.seek(-4, 1)
            raw_block += self._buffer.read(length),
        return raw_block

    def _tagcheck(self):
        try:
            with open(self.path, 'rb') as f:
                flac, = struct.unpack('!4s', f.read(4))
        except Exception as e:
            raise IOError(e)
        flac = flac.decode()
        if flac != 'fLaC':
            raise TypeError("incorrect file format")
        else:
            self.tag = flac

    def _getsize(self):
        size = 4
        f = open(self.path, 'rb')
        while True:
            f.seek(size)
            block_header, = struct.unpack('!I', f.read(4))
            flag = block_header >> 31
            size += (block_header & 0xffffff) + 4
            if flag: break
        f.close()
        return size
                
    def _createlabels(self):
        table = ()
        length = 0
        self._buffer.seek(4)
        while True:
            block_header, = self._buffer.unpack('!I')
            flag = block_header >> 31
            block_type = block_header >> 24 & 0x7f
            length = block_header & 0xffffff
            try:
                block_type = self._define[block_type]
                self._buffer[block_type] = length
                table += block_type,
            except IndexError:
                raise IndexError("unknown block type: %s" % block_type)
            self._buffer.seek(length, 1)
            if flag: break
        return table

def blockPic(path, use=3, form=0):
    if not isinstance(use, int) or use < 0 or use > 20:
        raise ValueError(f"invalid picture type: {key!r}")
    with open(path, 'rb') as pic:
        imageData = pic.read()
    length = len(imageData)
    if form:
        pichead = struct.pack('!2I9s6I', use, 9, b"image/png", *(0,)*5, length)
        length += 41
    else:
        pichead = struct.pack('!2I10s6I', use, 10, b"image/jpeg", *(0,)*5, length)
        length += 42
    header = struct.pack('!I', 6 << 24 | length)
    return header + pichead + imageData

def blockInfo(comm):
    vendor = b"Lavf58.29.100"
    length = len(vendor)
    b = b''
    b += struct.pack('<I', length)
    b += struct.pack('!%ss' % length, vendor)
    b += struct.pack('<I', len(comm))
    for i in comm:
        vec = f'{i}={comm[i]}'
        length = len(vec)
        b += struct.pack('<I', length)
        b += struct.pack('!%ss' % length, vec.encode())
    header = struct.pack('!I', 4 << 24 | len(b))
    return header + b

def create_Flac_tag(*blocks):
    tag = struct.pack('!4s', b"fLaC")
    for i in range(len(blocks) - 1):
        tag += blocks[i]
    # set last metadata block
    _h = struct.pack('!B', blocks[-1][0] | 0x80)
    tag += _h + blocks[-1][1:]
    return tag


def test(path):
    s = FlacContext(path)
    print(f'Flactag size: {s.size}')
    print(f'Tagframes: {s.blocklist}')
    print(f'Stream infos: {s.BLOCK_STREAMINFO()}')
    print(f'Infos: {s.BLOCK_VORBIS_COMMENT()}')
    picData, picInfo = s.BLOCK_PICTURE()
    pic_path = path.split('.')[0] + '_outpic.jpeg'
    bytes_to_file(pic_path, picData)
    print(f'---Export picture to {pic_path!r}...')
    print(f'Picture infos: {picInfo}')

if __name__ == '__main__':
    import os
    workpath = os.getcwd()
    path1 = os.path.join(workpath, r"file\test1.flac")
    path2 = os.path.join(workpath, r"file\test2.flac")
    newpath = os.path.join(workpath, r"file\test2_new.flac")
    test(path1)
    
    s = FlacContext(path2)
    block = s.blocklist
    comment = s.BLOCK_VORBIS_COMMENT()
    print(block, comment, sep = '\n')
    info, = s.block_copy("STREAMINFO")
    comm_dict = {}
    for i in comment:
        if comment[i] != None:
            comm_dict[i] = comment[i]
    comm_dict["VERSION"] = "1"
    comm_dict["ALBUM"] = "My Favorite"
    comm = blockInfo(comm_dict)
    pic = blockPic(os.path.join(workpath, r"file\test2.jpg"))
    tag = create_Flac_tag(info, comm, pic)
    bytes_to_file(newpath, tag)
    copy_file(newpath, path2, s.size, exist_ok = True)
    print(f"---Export new flac file to {newpath!r}...")

