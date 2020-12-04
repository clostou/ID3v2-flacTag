from util import *
import struct

__all__ = ['Mp3Context', 'build_frame_info', 'build_frame_infos',
           'build_frame_APIC', 'create_ID3_tag']

def ID3_sync_safe_to_int(sync_safe_integer):
    byte0 = sync_safe_integer >> 24 & 0xff
    byte1 = sync_safe_integer >> 16 & 0xff
    byte2 = sync_safe_integer >> 8 & 0xff
    byte3 = sync_safe_integer & 0xff
    return byte0 << 21 | byte1 << 14 | byte2 << 7 | byte3

def int_to_ID3_sync_safe(integer):
    byte0 = integer >> 21 & 0x7f
    byte1 = integer >> 14 & 0x7f
    byte2 = integer >> 7 & 0x7f
    byte3 = integer & 0x7f
    return byte0 << 24 | byte1 << 16 | byte2 << 8 | byte3

class Mp3Context(AudioContext):
    def __init__(self, filepath):
        super(Mp3Context, self).__init__(filepath)
        with open(self.path, 'rb') as f:
            self._buffer = AudioContextBuffer(f.read(self.size))
        id3, ver, revision, flags, length = self._buffer.unpack('!3s3BI')
        self.ver = (ver, revision)
        self.frame, self.frame_flag = self._createlabels()

    def _tagcheck(self):
        try:
            with open(self.path, 'rb') as f:
                id3, = struct.unpack('!3s', f.read(3))
        except Exception as e:
            raise IOError(e)
        id3 = id3.decode()
        if id3 != 'ID3':
            raise TypeError("incorrect file format")
        else:
            self.tag = id3

    def _getsize(self):
        with open(self.path, 'rb') as f:
            f.seek(6)
            size, = struct.unpack('!I', f.read(4))
        size = ID3_sync_safe_to_int(size)
        return size

    def _createlabels(self):
        table = (); flag = ()
        size = self.size - 10
        self._buffer.seek(10)
        while True:
            fid, length, flags = self._buffer.unpack('!4sIH')
            fid = fid.decode()
            if length == 0: break
            if self.ver[0] == 4:
                length = ID3_sync_safe_to_int(length)
            self._buffer[fid] = length
            self._buffer.seek(length, 1)
            table += fid,; flag += flags,
            size -= length + 10
            if size <= 0: break
        return table, flag

    def frame_Info(self, frame_ID=None):
        # <Header for 'Text information frame', ID: "T000" - "TZZZ",
        # excluding "TXXX" which user defines.>
        # Text encoding    $xx
        # Information    <text string according to encoding>
        names =  []
        if frame_ID == None:
            for i in self.frame:
                if i[0] == 'T':
                    names.append(i)
        elif frame_ID.find('T') != 0:
            raise ValueError(f"{frame_ID} isn't one ID of text information frame")
        else:
            names.append(frame_ID)
        info = {}
        for i in names:
            length = self._buffer.labelseek(i)
            encoding, content = self._buffer.unpack('!B%ss' % (length - 1))
            if encoding:
                info[i] = content.decode('utf16')
            else:
                info[i] = content.decode('gbk')
        if frame_ID == None:
            return info
        else:
            return info[frame_ID]

    def frame_COMM(self):
        # <Header for 'Comment', ID: "COMM">
        # Text encoding           $xx
        # Language                $xx xx xx
        # Short content descrip.  <text string according to encoding> $00 (00)
        # The actual text         <full text string according to encoding>
        end = self._buffer.labelseek("COMM", 0)
        encoding, lan = self._buffer.unpack('!B3s')
        _desc = self._buffer.read2()
        content = self._buffer.read(end - self._buffer.tell())
        if encoding:
            return content.decode('utf16')
        else:
            return content.decode('gbk')

    def frame_APIC(self):
        # <Header for 'Attached picture', ID: "APIC">
        # Text encoding   $xx
        # MIME type       <text string> $00
        # Picture type    $xx
        # Description     <text string according to encoding> $00 (00)
        # Picture data    <binary data>
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
        end = self._buffer.labelseek("APIC", 0)
        encoding, = self._buffer.unpack('!B')
        MIME = self._buffer.read2().decode()
        picType, = self._buffer.unpack('!B')
        try:
            picType = _define[picType]
        except IndexError:
            raise IndexError("unkonwn picture type: %s" % picType)
        if encoding:
            desc = self._buffer.read2().decode('utf16')
        else:
            desc = self._buffer.read2().decode('gbk')
        info = [MIME, picType, desc]
        imageData = self._buffer.read(end - self._buffer.tell())
        return imageData, info

def build_frame_info(ID, content):
    content = content.encode('utf16')
    content = struct.pack('!B', 1) + content
    size = len(content)
    header = struct.pack('!4sIH', ID.encode(), size, 0)
    return header + content, size + 10

def build_frame_infos(infoDict):
    if not isinstance(infoDict, dict):
        raise TypeError(f"incorrect parameter type \
(dict requested but {type(infoDict)} given)")
    frame_infos = []
    for i in infoDict:
        content = infoDict[i].encode('utf16')
        content = struct.pack('!B', 1) + content
        size = len(content)
        header = struct.pack('!4sIH', i.encode(), size, 0)
        frame_infos.append((header + content, size + 10))
    return frame_infos

def build_frame_APIC(path, use=3, form=0):
    if not isinstance(use, int) or use < 0 or use > 20:
        raise ValueError(f"invalid picture type: {key!r}")
    with open(path, 'rb') as pic:
        imageData = pic.read()
    if form:
        bodyhead = struct.pack('!B10s2B', 1, b'image/png\x00', use, 0)
    else:
        bodyhead = struct.pack('!B11s2B', 1, b'image/jpeg\x00', use, 0)
    body = bodyhead + imageData
    size = len(body)
    header = struct.pack('!4sIH', b'APIC', size, 0)
    return header + body, size + 10

def create_ID3_tag(*frames):
    tag = b''
    length = 10
    for frame in frames:
        tag += frame[0]
        length += frame[-1]
    length = int_to_ID3_sync_safe(length)
    tag = struct.pack('!3s3BI', b'ID3', 3, 0, 0, length) + tag
    return tag

def test(path):
    s = Mp3Context(path)
    print(f'Mp3tag size: {s.size}')
    print(f'Tagframes: {s.frame}', f'frame flags: {s.frame_flag}', sep = '\n')
    print(f'Infos: {s.frame_Info()}')
    picData, picInfo = s.frame_APIC()
    pic_path = path.split('.')[0] + '_outpic.jpeg'
    bytes_to_file(pic_path, picData)
    print(f'---Export picture to {pic_path!r}...')
    print(f'Picture infos: {picInfo}')
    

if __name__ == '__main__':
    import os
    workpath = os.getcwd()
    path = os.path.join(workpath, r"file\test.mp3")
    newpath = os.path.join(workpath, r"file\test_new.mp3")
    test(path)
    
    s = Mp3Context(path)
    infos = s.frame_Info()
    infos["TSSE"] = "Lavf58.29.100"
    infos["TALB"] = "Outer Wilds OST"
    infos["TIT2"] = "A Terrible Fate"
    infos["TPUB"] = "Mobius Digital/Annapurna Interactive"
    del infos["TPE1"]
    frames = build_frame_infos(infos)
    frame1 = build_frame_info("TPE1", "Andrew Prahlow")
    frame2 = build_frame_APIC(os.path.join(workpath, r"file\test.jpg"))
    tag = create_ID3_tag(*frames, frame1, frame2)
    bytes_to_file(newpath, tag)
    copy_file(newpath, path, s.size, exist_ok = True)
    print(f"---Export new mp3 file to {newpath!r}...")
    
    
    
