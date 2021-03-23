import image

import serial
import time
import platform
import logging
import glob
from collections import defaultdict

CHECKSUM_ERROR = 0
PRINTING = 1
IMAGE_FULL = 2
UNPROCESSED_DATA = 3
PACKET_ERROR = 4
PAPER_JAM = 5
OTHER_ERROR = 6
LOW_BATTERY = 7

status_text = [
    'CHECKSUM_ERROR',
    'PRINTING',
    'IMAGE_FULL',
    'UNPROCESSED_DATA',
    'PACKET_ERROR',
    'PAPER_JAM',
    'OTHER_ERROR',
    'LOW_BATTERY'
]


NULL = 0
INIT = 1
PRINT = 2
DATA = 4
BREAK = 8
STATUS = 0xF

def unknown(): return 'UNKNOWN'
p_type = defaultdict(unknown)
p_type[0] = 'NULL'
p_type[1] = 'INIT'
p_type[2] = 'PRINT'
p_type[4] = 'DATA'
p_type[8] = 'BREAK'
p_type[0xF] = 'STATUS'

log = logging.getLogger(__name__)

class GBSerial:
    def __init__(self, port=None):
        self.log = logging.getLogger('gbserial')
        self.port = None
        self.serial = None

    def init(self):
        if self.serial:
            return
        if self.port is None:
            good_ports = self.find_serial_ports()
        else:
            self.log.info(f'Printer on {port} you say?')
            good_ports = [self.port]
        self.log.debug(f'Good ports are {",".join(good_ports)}')
        for port in good_ports:
            ret = self.test_port(port)
            if ret:
                self.log.info(f'Printer dongle found on {port}')
                self.serial = ret
                self.port = port
                break
        else:
            raise IOError(f'Printer dongle not found on ports {",".join(good_ports)}')
        return self

    @staticmethod
    def find_serial_ports():
        opsys = platform.system()
        if opsys == 'Windows':
            ports = ['COM%s' % (i + 1) for i in range(2,256)]
        elif opsys == 'Linux':
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif opsys == 'Darwin':
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Not Windows, Mac, or Linux, dunno ' \
                                   'where your serial ports would be')
        good_ports = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                good_ports.append(port)
            except (OSError, serial.SerialException):
                pass
        return good_ports

    @staticmethod
    def test_port(port):
        test_serial = serial.Serial(port, baudrate=115200, timeout=0)
        log.info(f'Checking port {port}')
        time.sleep(2)
        response = test_serial.read(9999)
        if b'GAMEBOY PRINTER Packet Capture' in response:
            return test_serial
        else:
            test_serial.close()
            return None

    def get_line(self, timeout=1):
        start = time.time()
        serial_buffer = bytearray()
        while True:
            from_gb = self.serial.read()
            if from_gb:
                serial_buffer.append(int.from_bytes(from_gb, 'big'))
                if from_gb == b'\n':
                    log.debug('Line received from serial')
                    break
            if time.time() - start > timeout:
                log.debug('Timeout from serial')
                break
        return serial_buffer.strip()

    def shutdown(self):
        self.serial.close()

class Emulator:
        def __init__(self, port=None, palette=image.PALETTES['gray'], 
                     convert_by_page=False, convert_by_line=False,
                     clear_after_print=True, auto_save=False):
            self.log = logging.getLogger('Emulator')
            self.palette = palette
            self.init_buffer()
            self.running = False
            self.convert_by_page = convert_by_page
            self.convert_by_line = convert_by_line
            if self.convert_by_line:
                self.convert_by_page = False
            self.clear_after_print = clear_after_print
            self.auto_save = auto_save

        def init(self, source=None):
            self.log.debug('Begin to init')          
            self.source = source if source else GBSerial()
            self.source.init()
            self._fullimage = bytearray()
            self.running = True
            self.log.debug('Emulator is init')

        def shutdown(self):
            self.source.shutdown()
            self.running = False

        def init_buffer(self):
            self._status = b'\x00'
            self._buffer = bytearray()
            self.log.debug('Buffer is init!')
            # self._fullimage = bytearray()

        @property
        def status(self):
            return [self._status[0]>>i & 0x01 for i in range(8)]

        @property
        def status_text(self):
            return [status_text[i] for i in range(8)if self._status[0]>>i & 0x01]
        
        @property
        def state(self):
            return self._state

        @property
        def pages(self):
            return len(self._buffer)//640
        
        def set_status(self, bit, new_status=True):
            num = self._status[0]
            if new_status:
                num |= 2**bit
            else:
                num ^= 2**bit
            self._status = bytes([num])

        def get_status(self,bit):
            return bool(self._status[0] & 2**bit)

        def get_line(self):
            if self.running:
                return self.source.get_line()
            else:
                print('Did not init emulator')

        def run_forever(self):
            while True:
                line = self.source.get_line()
                packet = self.parse_line(line)
                if packet:
                    self.handle_packet(packet)
                    log.debug(f'Current status: {self.status_text}')
                    log.debug(f'Status according to Arduino: {packet.status_text}')


        def parse_line(self, data):
            # log.debug('Full line from serial:')
            # log.debug(data.decode('utf-8'))
            if not data.startswith(b'88 33 '):
                log.debug('Not a proper packet')
                return
            data_split = data.split(b' ')
            data_hex = [int(x, 16) for x in data_split]
            p = GBPacket(data_hex)
            return p

        def handle_packet(self, packet):
            log.info(f'Received {packet}')
            if packet.is_valid() != 'VALID':
                log.info(f'Packet is invalid: {packet.is_valid()}')
                return  

            if packet.command == INIT:
                self.handle_init(packet)
            elif packet.command == PRINT:
                return self.handle_print(packet)
            elif packet.command == DATA:
                return self.handle_data(packet)
            elif packet.command == BREAK:
                self.handle_break(packet)
            elif packet.command == STATUS:
                self.handle_status(packet)
            else:
                log.error('How did you get here?')

        def handle_init(self, packet):
            if not self.get_status(PRINTING): #if not currently printing
                self.init_buffer()
            else:
             self.init_buffer()

        def handle_print(self, packet):
            log.debug('Print data 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x}'.format(*packet.data))
            self.set_status(PRINTING)
            self.set_status(IMAGE_FULL)
            self.set_status(UNPROCESSED_DATA, False)
            end_margin = packet.data[1] % 16
            if not self.convert_by_line: #if it is, adding the buffer is handled in data command
                self._fullimage += self._buffer
            if end_margin != 0:
                log.info('Full image received!')
                ret = image.gbtile_to_image(self._fullimage, palette=self.palette, save=self.auto_save)
                self._fullimage = bytearray()
                return ret, 'complete'

            else:
                log.info('Page received!')
                if self.convert_by_page:
                    log.info('Converting as requested!')
                    ret = image.gbtile_to_image(self._fullimage, palette=self.palette, save=self.auto_save)
                    return ret, 'partial'

        def handle_data(self, packet):
            if not self.get_status(PRINTING):
                ret = None
                if len(packet.data) == 0:
                    pass
                elif self.pages >= 9:
                    log.warning("Buffer full, data packet rejected")
                    self.set_status(PACKET_ERROR)
                else:
                    if packet.compressed:
                        packet.decompress_data()
                    data = packet.data
                    self._buffer += bytes(data)
                    if self.convert_by_line:
                        self._fullimage += bytes(data)
                        ret = image.gbtile_to_image(self._fullimage, palette=self.palette, save=self.auto_save)
                    self.set_status(UNPROCESSED_DATA)
                log.debug('Number of pages in buffer: {}'.format(self.pages))
                log.debug('Number of bytes in buffer: {}'.format(len(self._buffer)))
                return ret, 'partial'

        def handle_break(self, packet):
            if self.get_status(PRINTING):
                self.init_buffer()

        def handle_status(self, packet):
            if self.get_status(PRINTING):
                if not self.get_status(UNPROCESSED_DATA):
                    self.set_status(UNPROCESSED_DATA)
                else:
                    self.set_status(PRINTING,False)
                    self.set_status(IMAGE_FULL,False)
                    self.set_status(UNPROCESSED_DATA,False)
                    self.init_buffer()


class GBPacket:
    def __init__(self, data):
        self.raw_data = data
        self.magic = data[0:2]
        self.command = data[2]
        self.compressed = bool(data[3])
        self.data_length = data[4] + data[5]*256
        self.data = data[6:6+self.data_length]
        self.checksum = data[-4] + data[-3]*256
        self.response = data[-2]
        self._status = data[-1]
        self.valid = None
        self.calc_sum = None

    def is_valid(self):
        if self.valid is None:
            self.valid = self._check_validity()
        return self.valid

    def _check_validity(self):
        if self.magic != [0x88, 0x33]:
            return 'BAD_MAGIC_BYTES'
        if self.command_text == 'UNKNOWN':
            return 'BAD_COMMAND'
        if not self.calc_sum:
            self.calc_sum = sum(self.raw_data[2:-4])%(256**2)
        if self.calc_sum != self.checksum:
            return 'BAD_CHECKSUM'
        return 'VALID'

    @property
    def status(self):
        return [self._status>>i & 0x01 for i in range(8)]

    @property
    def status_text(self):
        return [status_text[i] for i in range(8)if self._status>>i & 0x01]

    @property
    def command_text(self):
        return p_type[self.command]
    
    # def decompress_data(self):
    #     return self.data

    def decompress_data(self):
        comp_data = self.data
        len_comp = len(comp_data)
        raw_data = [0]*640
        comp_offset = 0
        raw_offset = 0
        while comp_offset < len(comp_data):
            command_byte = comp_data[comp_offset]
            comp_offset += 1
            if command_byte & 0x80: #compressed run
                length = command_byte - 0x80 + 2
                duped_byte = comp_data[comp_offset]
                comp_offset += 1
                raw_data[raw_offset:raw_offset+length] = [duped_byte]*length
                raw_offset += length
            else: #uncompressed run
                length = command_byte + 1
                unduped_data = comp_data[comp_offset:comp_offset+length]
                comp_offset += length
                raw_data[raw_offset:raw_offset+length] = unduped_data
                raw_offset += length
        self.data = raw_data
        self.compressed = False

    def __str__(self):
        return f'GBPacket(command={self.command_text}, ' \
               f'compressed={self.compressed}, ' \
               f'data_length={self.data_length})'

    def __repr__(self):
        return f'GBPacket({self.raw_data})'