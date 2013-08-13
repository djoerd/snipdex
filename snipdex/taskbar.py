#!/usr/bin/env python
"""
taskbar.py: Snipdex taskbar icon (not integrated with Snipdex)

The contents of this file are subject to the PfTijah Public License 
Version 1.1 (the "License"); you may not use this file except in 
compliance with the License. You may obtain a copy of the License at 
http://dbappl.cs.utwente.nl/Legal/PfTijah-1.1.html

Software distributed under the License is distributed on an "AS IS" 
basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See 
the License for the specific language governing rights and limitations 
under the License.

The Original Code is the SnipDex system.

The Initial Developer of the Original Code is the "University of 
Twente". Portions created by the "University of Twente" are 
Copyright (C) 2012 "University of Twente". All Rights Reserved.

Authors: Almer Tigelaar
         Djoerd Hiemstra 
"""
import sys
import wx
import webbrowser  

OPEN_BROWSER = wx.NewId()  
OPEN_PREFS   = wx.NewId()  
QUIT_SNIPDEX = wx.NewId()

class SnipdexTaskBarIcon(wx.TaskBarIcon):  

    def __init__(self, parent):  
        wx.TaskBarIcon.__init__(self)  
        self.parentApp = parent
        self.CreateMenu()  
        self.SetIcon(
            wx.Icon("systray2big.png", wx.BITMAP_TYPE_PNG), 
            "Snipdex active" )  

    def CreateMenu(self):  
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.ShowMenu)  
        self.Bind(wx.EVT_TASKBAR_LEFT_UP, self.ShowMenu)  
        self.Bind(wx.EVT_MENU, self.parentApp.OpenBrowser, id=OPEN_BROWSER)  
        self.Bind(wx.EVT_MENU, self.parentApp.OpenPrefs,   id=OPEN_PREFS)  
        self.Bind(wx.EVT_MENU, self.parentApp.QuitSnipdex, id=QUIT_SNIPDEX)  
        self.menu=wx.Menu()  
        self.menu.Append(OPEN_BROWSER, "Snipdex Search", "Opens your web browser with Snipdex search")  
        self.menu.Append(OPEN_PREFS, "Preferences", "Opens your web browser with Snipdex preferences")  
        self.menu.AppendSeparator()  
        self.menu.Append(QUIT_SNIPDEX, "Quit", "Quits Snipdex")  

    def ShowMenu(self, event):  
        self.PopupMenu(self.menu)  


class SnipdexFrame(wx.Frame):  

    def __init__(self):  
        wx.Frame.__init__(self, None, -1, ' ', size = (1, 1),  
            style=wx.FRAME_NO_TASKBAR|wx.NO_FULL_REPAINT_ON_RESIZE)  

        self.tbicon = SnipdexTaskBarIcon(self)  
        self.tbicon.Bind(wx.EVT_MENU, self.exitApp, id=wx.ID_EXIT)   
        self.Show(True)  

    def exitApp(self, event):  
        self.tbicon.RemoveIcon()  
        self.tbicon.Destroy()  
        sys.exit()  

    def OpenBrowser(self, event):  
        webbrowser.open('http://127.0.0.1:8472/snipdex/')  

    def OpenPrefs(self, event):  
        webbrowser.open('http://127.0.0.1:8472/snipdex/preferences/')  

    def QuitSnipdex(self, event):
        self.exitApp(event)


#---------------- run the program -----------------------  
def main(argv=None):  
    app = wx.App(False)  
    frame = SnipdexFrame()  
    frame.Show(False)  
    app.MainLoop()  

if __name__ == '__main__':  
    main()
