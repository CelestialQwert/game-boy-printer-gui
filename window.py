import wx
import PIL.Image
import threading
import time
import logging
from serial.serialutil import SerialException
from random import randint
from pubsub import pub

import emulator
import image

log = logging.getLogger(__name__)

class MainWindow(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self, parent=None, title='GBPrinter')
        self.status_bar = self.CreateStatusBar()
        self.create_other_stuff()
        self.create_layout()
        self.update_palette('gray')
        self.update_image()
        pub.subscribe(self.from_printer_msg, 'from_printer_msg')
        pub.subscribe(self.from_printer_img, 'from_printer_img')

    def create_layout(self):

        self.main_panel = wx.Panel(self)

        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_panel.SetSizer(self.main_sizer)

        self.left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.main_sizer.Add(self.left_sizer)


        """
        SERIAL CONNECTION
        """
        self.serial_box = wx.StaticBox(self.main_panel, wx.ID_ANY, 'Dongle')
        self.serial_sizer = wx.StaticBoxSizer(self.serial_box, wx.VERTICAL)

        self.connect_button = wx.Button(self.main_panel, wx.ID_ANY, "Connect")
        self.serial_sizer.Add(self.connect_button, 0, wx.EXPAND | wx.ALL, 5)
        self.connect_button.Bind(wx.EVT_BUTTON, self.on_connect_button)

        self.disconnect_button = wx.Button(self.main_panel, wx.ID_ANY, "Disconnect")
        self.disconnect_button.Disable()
        self.serial_sizer.Add(self.disconnect_button, 0, wx.EXPAND | wx.ALL, 5)
        self.disconnect_button.Bind(wx.EVT_BUTTON, self.on_disconnect_button)

        self.serial_status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        status_lbl = wx.StaticText(self.main_panel, label="Status:")
        self.serial_status_sizer.Add(status_lbl, 0, wx.EXPAND | wx.ALL, 2)
        self.serial_status = wx.StaticText(self.main_panel, label="Not Connected")
        self.serial_status_sizer.Add(self.serial_status, 1, wx.EXPAND | wx.ALL, 2)
        self.serial_sizer.Add(self.serial_status_sizer, 0, wx.ALIGN_CENTER)

        self.left_sizer.Add(self.serial_sizer, flag=wx.EXPAND | wx.ALL, border=5)


        """
        PALLETTE SELECTOR
        """
        self.palette_box = wx.StaticBox(self.main_panel, wx.ID_ANY, 'Palette')
        self.palette_sizer = wx.StaticBoxSizer(self.palette_box, wx.VERTICAL)

        self.palette_choice = wx.Choice(self.main_panel, choices=list(image.PALETTES.keys()))
        self.palette_choice.SetSelection(0)
        self.palette_choice.Bind(wx.EVT_CHOICE, self.on_palette_choice)
        self.palette_sizer.Add(self.palette_choice, 1, wx.EXPAND | wx.ALL, 5)

        self.color_buttons = []
        for i in range(4):
            button = wx.ColourPickerCtrl(self.main_panel, style=wx.CLRP_SHOW_LABEL, name=str(i))
            # button.SetBackgroundColour(colour)
            button.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_palette_changed)
            self.color_buttons.append(button)
            self.palette_sizer.Add(button, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)

        self.left_sizer.Add(self.palette_sizer, flag=wx.EXPAND | wx.ALL, border=5)


        """
        PREVIEW OPTIONS
        """
        self.preview_box = wx.StaticBox(self.main_panel, wx.ID_ANY, 'Preview Options')
        self.preview_sizer = wx.StaticBoxSizer(self.preview_box, wx.VERTICAL)

        self.scale_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scale_buttons = []
        for scl in [1, 2, 3]:
            style = wx.RB_GROUP if scl == 1 else 0
            button = wx.RadioButton(self.main_panel, wx.ID_ANY, label=f'{scl}x', style=style)
            self.scale_buttons.append(button)
            if scl == 2:
                button.SetValue(True)
            self.scale_sizer.Add(button, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
            button.Bind(wx.EVT_RADIOBUTTON, self.on_scale)
        self.preview_sizer.Add(self.scale_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.left_sizer.Add(self.preview_sizer, flag=wx.EXPAND | wx.ALL, border=5)


        """
        SAVE PANEL
        """
        self.save_box = wx.StaticBox(self.main_panel, wx.ID_ANY, 'Save')
        self.save_sizer = wx.StaticBoxSizer(self.save_box, wx.VERTICAL)

        self.manual_save_button = wx.Button(self.main_panel, wx.ID_ANY, "Save Image")
        self.manual_save_button.Bind(wx.EVT_BUTTON, self.on_manual_save)
        self.save_sizer.Add(self.manual_save_button, 0, wx.EXPAND | wx.ALL, 5)

        self.auto_save_toggle = wx.CheckBox(self.main_panel, wx.ID_ANY, "Auto Save Images")
        self.save_sizer.Add(self.auto_save_toggle, 0, wx.EXPAND | wx.ALL, 5)

        self.auto_save_button = wx.Button(self.main_panel, wx.ID_ANY, "Auto Save Directory...")
        self.auto_save_button.Bind(wx.EVT_BUTTON, self.on_auto_save)
        self.save_sizer.Add(self.auto_save_button, 0, wx.EXPAND | wx.ALL, 5)

        self.left_sizer.Add(self.save_sizer, flag=wx.EXPAND | wx.ALL, border=5)


        """
        FILLER PANEL
        """
        self.dummy_panel = wx.Panel(self.main_panel, wx.ID_ANY, style=wx.BORDER_SUNKEN, size=(-1,50))
        self.left_sizer.Add(self.dummy_panel, flag=wx.EXPAND | wx.ALL, border=5)


        """
        IMAGE PREVIEW
        """
        #4 pixels in each dim for the sunken border, 17 px for the scrollbar
        self.scale = 2
        self.image_panel = wx.ScrolledWindow(self.main_panel, wx.ID_ANY, style=wx.BORDER_SUNKEN)
        self.image_panel.ShowScrollbars(wx.SHOW_SB_ALWAYS, wx.SHOW_SB_ALWAYS)
        self.output_bitmap = wx.StaticBitmap(self.image_panel)
        self.main_sizer.Add(self.image_panel, flag=wx.ALL, border=5)

        """
        ALL DONE
        """
        self.main_sizer.Fit(self)
        self.Show(True)

    def create_other_stuff(self):
        self.log = logging.getLogger('window')
        self.emulator = emulator.Emulator(convert_by_line=True)
        self.pil_image = PIL.Image.open('diploma.png')
        image_data = bytes([0]*160*72 + [1]*160*72 + [2]*160*72 + [3]*160*72)
        self.pil_image = PIL.Image.frombytes('P',(160,144*2), image_data)
        self.clear_status_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_clear_status, self.clear_status_timer)

    def from_printer_msg(self, msg):
        self.log.debug(f'Got message from printer: {msg}')
        if msg == 'abort':
            self.shutdown_emulator()

    def from_printer_img(self, img, status):
        self.log.info(f'Received image from printer thread with status {status}')
        self.update_image(img)
        if status == 'complete' and self.auto_save_toggle.GetValue():
            self.pil_image.save(time.strftime('gbp_out/gbp_%Y%m%d_%H%M%S.png'),'PNG')
            self.SetStatusText("Autosaved complete image!")
            self.clear_status_later()


    def update_image(self, image=None):
        if image:
            self.pil_image = image
        self.pil_image.putpalette(self.palette)
        self.output_image = self.pil_image_to_wx_bitmap(self.pil_image, self.scale)
        self.output_bitmap.SetBitmap(self.output_image)

        self.image_panel.SetVirtualSize(self.output_bitmap.GetSize())
        self.image_panel.SetScrollRate(0, 8*self.scale)

        self.preview_size = wx.Size(160*self.scale+21, 288*self.scale+4)
        self.image_panel.SetMinSize(self.preview_size)
        self.image_panel.SetMaxSize(self.preview_size)

        self.main_sizer.Fit(self)


    @staticmethod
    def pil_image_to_wx_bitmap(pil_image, scale=2):
        """Note that I don't have to worry about transparency"""
        w, h = pil_image.size
        wx_img = wx.Image(w*scale, h*scale)
        resized_img = pil_image.resize((w*scale, h*scale), PIL.Image.NEAREST)
        pil_img_data = resized_img.convert('RGB').tobytes()
        wx_img.SetData(pil_img_data)
        return wx_img.ConvertToBitmap()

    def on_manual_save(self, e):
        with wx.FileDialog(self, "Save Image", 
                           wildcard="PNG File (*.png)|*.png",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            # save the current contents in the file
            pathname = fileDialog.GetPath()
            try:
                self.pil_image.save(pathname)
                self.SetStatusText("Image saved!")
                self.clear_status_later()
            except IOError:
                wx.LogError(f"Cannot save current data in file {pathname}")

    def on_auto_save(self, e):
        pass

    def on_scale(self, e): 
        rb = e.GetEventObject() 
        self.log.debug(f'{rb.GetLabel()} is clicked from Radio Group')
        self.scale = int(rb.GetLabel()[0])
        self.update_image()

    def on_palette_changed(self, e):
        rb = e.GetEventObject()
        print(rb.GetName())
        color_slot = int(rb.GetName())
        new_color = e.GetColour()
        for i in range(3):
            self.palette[3*color_slot+i] = new_color[i]
        self.update_image()
        self.SetStatusText(f"Color {color_slot} updated to {new_color[:-1]}")
        self.clear_status_later()

    def on_palette_choice(self, e):
        self.update_palette(e.GetString())
        self.update_image()

    def update_palette(self, palette_name):
        self.palette = image.palette_convert(image.PALETTES[palette_name])
        for i in range(4):
            self.color_buttons[i].SetColour(wx.Colour(self.palette[i*3:i*3+3]))

    def on_connect_button(self, e):
        self.SetStatusText(f'Scanning serial ports for dongle...')
        self.connect_button.Disable()
        good_ports = emulator.GBSerial.find_serial_ports()
        for port in good_ports:
            try:
                self.SetStatusText(f'Checking {port} for dongle...')
                gbserial = emulator.GBSerial()
                self.emulator.init(gbserial)
                st = f'Connected to {gbserial.port}'
                self.serial_status.SetLabel(gbserial.port)
                self.SetStatusText(st)
                self.clear_status_later()
                self.connect_button.Disable()
                self.disconnect_button.Enable()
                PrinterThread(self.emulator)
                break
            except IOError:
                pass
        else:
            self.connect_button.Enable()
            self.SetStatusText("Didn't find a printer dongle!")
            self.clear_status_later()

    def on_disconnect_button(self, e):
        pub.sendMessage('to_printer', msg='abort')
        self.shutdown_emulator()

    def shutdown_emulator(self):
        time.sleep(1)
        self.emulator.shutdown()
        self.disconnect_button.Disable()
        self.connect_button.Enable()
        self.serial_status.SetLabel("Not Connected")
        self.SetStatusText("Connection closed")
        self.clear_status_later()

    def clear_status_later(self, timeout=5000):
        pass
        # self.clear_status_timer.StartOnce(timeout)

    def on_clear_status(self, e):
        self.SetStatusText('')

    def on_about(self, e):
        dlg = wx.MessageDialog( self, "WIP Game Boy Printer Emulator", "About GBPrinter GUI", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_exit(self, e):
        self.Close(True)  # Close the frame.


class PrinterThread(threading.Thread):
    def __init__(self, emulator):
        threading.Thread.__init__(self)
        self.log = logging.getLogger('printer_thread')
        self.emulator = emulator
        self.daemon = True
        pub.subscribe(self.handle_message, 'to_printer')
        self.aborting = False
        self.start()

    def run(self):
        self.log.debug('Printer thread running')
        pub.sendMessage('from_printer', msg='Hello!')
        while True:
            try:
                line = self.emulator.get_line()
            except:
                pub.sendMessage('from_printer_msg', msg='abort')
                log.info('Serial error, closing connection')
                break
            packet = self.emulator.parse_line(line)
            if packet:
                ret = self.emulator.handle_packet(packet)
                if ret:
                    ret_img, status = ret
                    pub.sendMessage('from_printer_img', img=ret_img, status=status)
            if self.aborting:
                # pub.sendMessage('from_printer_msg', msg='Goodbye!')
                break

    def handle_message(self, msg=None):
        if msg == 'abort':
            self.aborting = True