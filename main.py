import wx
import window
import logging

logging.basicConfig(level=logging.INFO)

app = wx.App(False)
frame = window.MainWindow()
app.MainLoop()