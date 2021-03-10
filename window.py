import wx

class MainWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, parent=None, title='GBPrinter')

        self.CreateStatusBar() # A Statusbar in the bottom of the window

        # Setting up the menu.
        my_menu = wx.Menu()

        # wx.ID_ABOUT and wx.ID_EXIT are standard IDs provided by wxWidgets.
        menu_change = my_menu.Append(wx.ID_ANY, "&Change", "Change something...")
        my_menu.AppendSeparator()
        menu_about = my_menu.Append(wx.ID_ABOUT, "&About", "Information about this program")
        my_menu.AppendSeparator()
        menu_exit = my_menu.Append(wx.ID_EXIT,"E&xit", "Terminate the program")

        # Creating the menubar.
        menuBar = wx.MenuBar()
        menuBar.Append(my_menu, "&Menu") # Adding the "my_menu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        self.Bind(wx.EVT_MENU, self.OnChange, menu_change)
        self.Bind(wx.EVT_MENU, self.OnAbout, menu_about)
        self.Bind(wx.EVT_MENU, self.OnExit, menu_exit)

        self.panel = wx.Panel(self, wx.ID_ANY, size=(320,-1))
        self.quote = wx.StaticText(self.panel, label="A lost quote...", pos=(10,10))

        self.image_panel = wx.Panel(self, wx.ID_ANY, style=wx.BORDER_SUNKEN)
        self.image = wx.Bitmap("diploma.png", wx.BITMAP_TYPE_ANY)
        self.image_obj = wx.StaticBitmap(self.image_panel, wx.ID_ANY, self.image, size=(320,576))

        self.button_sizer = wx.BoxSizer(wx.VERTICAL)
        self.buttons = []
        for i in range(0, 6):
            self.buttons.append(wx.Button(self, wx.ID_ANY, f"Button &{i}"))
            self.button_sizer.Add(self.buttons[i], 1, wx.EXPAND | wx.ALL, 5)

        # Use some sizers to see layout options
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.panel, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(self.image_panel, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.Add(self.button_sizer, 0, wx.EXPAND)

        #Layout sizers
        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

        self.Show(True)

    def OnChange(self, e):
        self.quote.SetLabel('wololo')

    def OnAbout(self,e):
        # A message dialog box with an OK button. wx.OK is a standard ID in wxWidgets.
        dlg = wx.MessageDialog( self, "WIP Game Boy Printer Emulator", "About GBPrinter GUI", wx.OK)
        dlg.ShowModal() # Show it
        dlg.Destroy() # finally destroy it when finished.

    def OnExit(self,e):
        self.Close(True)  # Close the frame.
        